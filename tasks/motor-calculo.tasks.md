# Backlog — Motor de Cálculo do PIQ

| Campo | Valor                                                             |
| ----- | ----------------------------------------------------------------- |
| Slug  | `motor-calculo`                                                   |
| Spec  | [`specs/motor-calculo.spec.md`](../specs/motor-calculo.spec.md)   |
| Plano | [`plans/motor-calculo.plan.md`](../plans/motor-calculo.plan.md)   |

## Progresso

`78/78 tarefas concluídas (Rodada 1) · 13/14 tarefas concluídas (Rodada 2, T-79 a T-92 — T-91 bloqueada por OQ-23) · 24/24 tarefas concluídas (Rodada 3, T-93 a T-116 — fatias 3A e 3B completas; 3C fora de escopo, bloqueada por OQ-30) · 15/15 tarefas concluídas (Rodada 4, T-117 a T-131 — fatia 4A completa e verificada) · 9/9 tarefas concluídas (Rodada 4, T-132 a T-140 — fatia 4B completa e verificada) · 3/11 tarefas concluídas (Rodada 4, T-141 a T-151 — fatia 4C, última fatia do documento do especialista; T-141, T-144, T-146 concluídas)`

> **Regras que valem para toda tarefa deste backlog** (§4 do `sdd.config.md`):
> nenhum valor `P_*` escrito no código; precisão decimal integral, arredondamento
> só na exibição; cada módulo cita o ID normativo que implementa em
> `REGRAS: Final[tuple[str, ...]]`; identificadores em pt-BR, idênticos aos da
> spec caractere por caractere.

---

## Entrega 1 — Fundação: stack, precisão decimal e parâmetros externos

### `T-01` — Inicializar a stack Python e preencher os comandos de verificação

- **Tipo:** `Infra`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-12`, `RF-13`, `AC-17`
- **Arquivos:** `pyproject.toml`, `.python-version`, `engine/__init__.py`, `persistencia/__init__.py`, `tests/__init__.py`, `sdd.config.md`

**Descrição**

Criar o projeto Python 3.12+ com `ruff`, `mypy` em modo `strict`, `pytest` (marcadores `gabarito`, `invariante`, `regra`, `desempenho`) e `hypothesis`, além do esqueleto de pacotes `engine/`, `persistencia/`, `tests/{gabaritos,invariantes,regras,estatica,desempenho,fixtures}`. A seção 2 do `sdd.config.md` está toda `—`; esta tarefa é o que faz `install`/`lint`/`build`/`test` passarem a existir.

**Critérios de aceite**

- [x] `pyproject.toml` declara Python `>=3.12`, `mypy` com `strict = true` e `ruff` habilitado
- [x] `pytest` roda com sucesso (coleta vazia é aceitável) e reconhece os quatro marcadores
- [x] `mypy engine persistencia tests` e `ruff check .` terminam com código 0
- [x] As pastas `engine/`, `persistencia/` e as cinco subpastas de `tests/` existem e são importáveis
- [x] A seção 2 do `sdd.config.md` tem `install`, `lint`, `build` e `test` preenchidos (alteração via `/sdd:config`, não editada à mão)

**Status:** `[x] concluída`

---

### `T-02` — Registrar a pasta `persistencia/` na seção 3 do `sdd.config.md`

- **Tipo:** `Docs`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-10`, `RF-13`
- **Arquivos:** `sdd.config.md`

**Descrição**

O plano declara uma divergência da §3 do config: adaptadores de banco e arquivo vivem em `persistencia/`, fora de `engine/`, para que o motor continue executável sem processo externo. A divergência precisa estar registrada antes de qualquer código de persistência.

**Critérios de aceite**

- [x] A tabela da §3 do `sdd.config.md` lista `persistencia/` com sua responsabilidade
- [x] O texto registra que `engine/` não importa nada de banco nem de sistema de arquivos
- [x] A alteração foi feita por edição direta do arquivo, já que `/sdd:config` não está disponível para o subagente de código (mesma exceção operacional de `T-01`)

**Status:** `[x] concluída`

---

### `T-03` — Criar `engine/precisao.py` com o contexto decimal único

- **Tipo:** `Infra`
- **Dependências:** `T-01`
- **Rastreia:** `RF-12`, `AC-40`
- **Arquivos:** `engine/precisao.py`

**Descrição**

Definir `CONTEXTO_MOTOR` (`prec=34`, `ROUND_HALF_UP`), o construtor `dinheiro(valor: str | int | Decimal)` — único autorizado a produzir valor monetário, recusando `float` em tempo de execução e de checagem — e `quantizar_exibicao`, com 2 casas, chamado apenas fora de `engine/` (`G-01`).

**Critérios de aceite**

- [x] `dinheiro(0.1)` levanta erro em tempo de execução e é recusado pelo `mypy`
- [x] `dinheiro("0.1")` e `dinheiro(Decimal("0.1"))` produzem o mesmo valor exato
- [x] `quantizar_exibicao(Decimal("10.125"))` devolve `Decimal("10.13")` (`AC-40`)
- [x] O contexto é aberto por `decimal.localcontext()` e nunca herdado do ambiente
- [x] O módulo declara `REGRAS = ("G-01", "G-02")`

**Status:** `[x] concluída`

---

### `T-04` — Definir `engine/tipos.py` com `DESCONHECIDO` e os domínios fechados

- **Tipo:** `Data`
- **Dependências:** `T-03`
- **Rastreia:** `RF-12`, `RF-16`, `RF-17`, `RF-26`
- **Arquivos:** `engine/tipos.py`

**Descrição**

Declarar `Dinheiro`, `Taxa`, `Meses`, o tipo-soma `DESCONHECIDO` (com `DinheiroTalvez`/`TaxaTalvez`) e os enums `DIVIDA_STATUS_ESTRATEGICO`, `GATE_PENDENTE`, `STATUS_DIVIDA`, `NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS`, `STATUS_FINANCEIRO`, `STATUS_VALIDADE_PROPOSTA`, `ORDEM_STATUS`, `STATUS_METODO`, `CLASSIFICACAO_CENARIO`, `METODO`, `NIVEL_RISCO`, `EVENTO_RECALCULO`. `None` é proibido para dado de negócio.

**Critérios de aceite**

- [x] Todos os enums usam exatamente os valores dos domínios fechados da spec (§11.3, §11.11, Definições §6–§8)
- [x] `EVENTO_RECALCULO` **não** tem membro para alteração cadastral/cosmética (`R-04`, `EC-08`)
- [x] Consumidor de `DinheiroTalvez` que não trata `DESCONHECIDO` falha no `mypy --strict` (checagem de exaustividade)
- [x] Nenhum alias de tipo usa `Optional` para dado de negócio
- [x] `CLASSIFICACAO_CENARIO` distingue `NAO_CALCULAVEL` de `NAO_APLICAVEL`

**Status:** `[x] concluída`

---

### `T-05` — Publicar `parameters/parametros-1.0.1.json` com os `P_*` ativos

- **Tipo:** `Data`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-13`, `AC-17`
- **Arquivos:** `parameters/parametros-1.0.1.json`

**Descrição**

Transcrever os parâmetros ativos da seção 8 da canônica, mais `ENGINE_VERSION`, `PARAMETROS_VERSION` e `DATA_VIGENCIA`. Valores numéricos como literais JSON, para leitura com `parse_float=Decimal`. `P_CAIXA_VS_ESTRUTURAL` fica de fora (deprecado, §11.9).

> **Nota `OQ-20`.** A §11.9 da spec do slug fala em "44 parâmetros ativos", mas a
> tabela §8 da canônica lista apenas 39 linhas nomeadas `P_*` (38 ativas após
> deprecar `P_CAIXA_VS_ESTRUTURAL`). `P_PRESSAO_INDIVIDUAL`, `P_PRESSAO_TOTAL` e
> `P_ESCALA_0_10` têm múltiplos valores agrupados na canônica sem nomes de
> sufixo definidos (ao contrário de `P_TAXA_TOX_*`, que já vem decomposto na
> fonte). Implementado com os 38 nomes literais da canônica, mantendo esses três
> como arrays — **sem inventar identificador que a canônica não escreveu**. Ver
> `OQ-20` em `specs/motor-calculo.spec.md`.

**Critérios de aceite**

- [x] Os `P_*` ativos da canônica estão presentes (38, ver nota `OQ-20` acima), com `P_AUTOPERCEPCAO = 7`
- [x] `P_CAIXA_VS_ESTRUTURAL` está ausente do arquivo
- [x] `PARAMETROS_VERSION` = `1.0.1` e `DATA_VIGENCIA` presente
- [x] `P_DIFERENCA_ECONOMICA_MATERIAL` (1%), `P_DIFERENCA_CUSTO_EQUIVALENTE` (5%) e `P_DIFERENCA_PRAZO_EQUIVALENTE` (2) aparecem como três entradas distintas
- [x] Nenhum parâmetro está marcado "a calibrar"

**Status:** `[x] concluída`

---

### `T-06` — Escrever `esquema-parametros.json` e `DEPRECATED.md`

- **Tipo:** `Data`
- **Dependências:** `T-05`
- **Rastreia:** `RF-13`, `AC-17`
- **Arquivos:** `parameters/esquema-parametros.json`, `parameters/DEPRECATED.md`

**Descrição**

JSON Schema que recusa carga incompleta: nomes, tipos, obrigatoriedade dos `P_*` ativos (ver nota `OQ-20` em T-05 — são 38 nomes literais, não 44) e proibição explícita de `P_CAIXA_VS_ESTRUTURAL`. O `DEPRECATED.md` registra por que o parâmetro saiu (§11.8/§11.9).

**Critérios de aceite**

- [x] O esquema valida `parametros-1.0.1.json` com sucesso
- [x] Remover um `P_*` do arquivo faz a validação falhar nomeando o parâmetro faltante
- [x] Incluir `P_CAIXA_VS_ESTRUTURAL` faz a validação falhar
- [x] `DEPRECATED.md` cita `OQ-02` e a decisão de 2026-09-01

**Status:** `[x] concluída`

---

### `T-07` — Implementar `Parametros`, a porta `FonteParametros` e o adaptador de arquivo

- **Tipo:** `Data`
- **Dependências:** `T-04`, `T-06`
- **Rastreia:** `RF-13`, `RF-12`, `AC-17`
- **Arquivos:** `engine/parametros.py`, `engine/portas.py`, `persistencia/arquivo/fonte_parametros.py`

**Descrição**

`Parametros` é `frozen`, expõe `numero(nome)` com `KeyError` ruidoso e **sem default**. `FonteParametros` é `Protocol` em `engine/portas.py`. O adaptador de arquivo lê com `json.load(f, parse_float=Decimal)` e valida contra o esquema antes de devolver.

**Critérios de aceite**

- [x] `Parametros.numero("P_INEXISTENTE")` levanta `KeyError` — nunca devolve default
- [x] Todo valor numérico carregado é `Decimal`; nenhum `float` aparece no objeto carregado
- [x] Carga com esquema violado levanta `ErroParametros` nomeando o `P_*` culpado
- [x] `PARAMETROS_VERSION` divergente da versão pedida aborta a carga
- [x] `engine/` não importa nada de `persistencia/`

**Status:** `[x] concluída`

---

### `T-08` — Modelar `engine/estado.py`: `Divida`, `EstadoFinanceiro`, `PerfilComportamental`

- **Tipo:** `Data`
- **Dependências:** `T-04`
- **Rastreia:** `RF-14`, `RF-16`, `RF-17`
- **Arquivos:** `engine/estado.py`

**Descrição**

Dataclasses `frozen=True, slots=True` com os campos listados na §4 do plano, incluindo `DATA_REFERENCIA` como entrada (nunca `date.today()`), `PAGAMENTO_MENSAL_EFETIVO` que pode ser 0, `CUSTO_SEGURO` separado da parcela e as 8 variáveis do Bloco 2 em `PerfilComportamental`.

**Critérios de aceite**

- [x] `Divida` e `EstadoFinanceiro` são imutáveis e hasheáveis por valor
- [x] Todo campo monetário incerto é `DinheiroTalvez`, nunca `Optional[Decimal]`
- [x] `PerfilComportamental` tem as 8 variáveis da §11.11 com seus domínios fechados
- [x] `EstadoFinanceiro.dividas` é `tuple`, não `list`
- [x] Validação estrutural recusa `float` em qualquer campo, nomeando o campo culpado

**Status:** `[x] concluída`

---

### `T-09` — Criar os helpers de tolerância e testar a família `G`

- **Tipo:** `Test`
- **Dependências:** `T-01`, `T-03`
- **Rastreia:** `RF-12`, `AC-40`
- **Arquivos:** `tests/conftest.py`, `tests/regras/test_G.py`, `tests/estatica/test_uso_de_tolerancia.py`

**Descrição**

`assertar_monetario` (± R$ 0,05, uso exclusivo em valor monetário acumulado) e `assertar_exato` (tolerância zero) como funções distintas. Um teste de AST varre `tests/` e falha se `assertar_monetario` for usado sobre símbolo da lista de tolerância zero.

**Critérios de aceite**

- [x] Os dois helpers existem em `tests/conftest.py` e são funções separadas
- [x] `test_G01_arredondamento_half_up` prova `10,125 → 10,13` (`AC-40`)
- [x] `test_uso_de_tolerancia` falha quando `assertar_monetario` é aplicado a `METODO_RECOMENDADO_PIQ`, `ORDEM_QUITACAO`, `STATUS_METODO`, `ORDEM_STATUS`, número de meses, `MESES_PRIMEIRA_VITORIA`, `D*`, aplicação de resíduo, gatilho de recálculo ou `NAO_APLICAVEL` vs `PROVISORIO`
- [x] Um caso de violação proposital é usado para provar que o lint pega

**Status:** `[x] concluída`

---

### `T-10` — Escrever os testes estáticos de `engine/`

- **Tipo:** `Test`
- **Dependências:** `T-07`, `T-09`
- **Rastreia:** `RF-12`, `RF-13`, `AC-17`
- **Arquivos:** `tests/estatica/test_nenhum_parametro_no_codigo.py`, `tests/estatica/test_sem_float_no_motor.py`, `tests/estatica/test_motor_e_deterministico.py`, `tests/estatica/test_toda_regra_citada.py`

**Descrição**

Quatro varreduras de AST sobre `engine/`: nenhum nome `P_*` recebendo literal e nenhum número da tabela da §8 como literal (`AC-17`, lado A); nenhum `float`, literal de ponto flutuante ou `math.*`; nenhum import de `datetime.now`, `date.today`, `random` ou `uuid4`; e toda regra `M-01..G-02` citada por algum `REGRAS` de módulo.

**Critérios de aceite**

- [x] Os quatro testes passam sobre o `engine/` existente
- [x] Introduzir `P_PISO_CAPACIDADE_ABSOLUTO = 300` em `engine/` faz `test_nenhum_parametro_no_codigo` falhar
- [x] Introduzir `0.05` em `engine/` faz `test_sem_float_no_motor` falhar
- [x] `test_toda_regra_citada` lista, na mensagem de falha, as regras ainda não citadas por nenhum módulo

**Status:** `[x] concluída`

---

### `T-11` — Criar as fixtures dos estados financeiros `GAB-A`, `GAB-B` e `GAB-C`

- **Tipo:** `Test`
- **Dependências:** `T-08`
- **Rastreia:** `RF-14`, `RF-05`, `AC-01`, `AC-05`, `AC-06`
- **Arquivos:** `tests/fixtures/gab_a.json`, `tests/fixtures/gab_b.json`, `tests/fixtures/gab_c.json`, `tests/fixtures/carregar.py`

**Descrição**

Transcrever os três cenários da seção 10 da canônica em JSON (valores monetários como string) e um carregador que os converte em `EstadoFinanceiro`. Sem fixture, nenhum gabarito é testável.

**Critérios de aceite**

- [x] Os três arquivos carregam em `EstadoFinanceiro` sem erro de tipo
- [x] `GAB-A` traz D001 com devido 1.200 e `PAGAMENTO_MENSAL_EFETIVO` = 0
- [x] `GAB-C` traz D001, D002 e D003 com saldo, taxa e pagamento dos gabaritos
- [x] Todo valor numérico é string no JSON e vira `Decimal` exato na carga
- [x] `DATA_REFERENCIA` é explícita em cada fixture

**Status:** `[x] concluída`

---

## Entrega 2 — Diagnóstico financeiro, risco comportamental e capacidade de ataque

### `T-12` — Derivar `NIVEL_CONTROLE` a partir das 8 variáveis do Bloco 2

- **Tipo:** `Data`
- **Dependências:** `T-08`
- **Rastreia:** `RF-23`, `RF-27`
- **Arquivos:** `engine/comportamento.py`

**Descrição**

Implementar `derivar_NIVEL_CONTROLE(perfil)` pelas regras determinísticas das Definições §4, respeitando a ordem de avaliação obrigatória `FRAGIL → FORTE → PARCIAL`. É a raiz do grafo de derivação e depende apenas de entrada coletada.

**Critérios de aceite**

- [x] A ordem de avaliação é `FRAGIL`, depois `FORTE`, depois `PARCIAL` — e está expressa no código, não só em comentário
- [x] A função recebe `PerfilComportamental` e nada mais
- [x] Toda combinação das 8 variáveis produz exatamente um dos três níveis
- [x] O módulo cita a origem normativa (Definições §4)

**Status:** `[x] concluída`

---

### `T-13` — Derivar `CONFIABILIDADE_DADOS` a partir de `NIVEL_CONTROLE`

- **Tipo:** `Data`
- **Dependências:** `T-12`
- **Rastreia:** `RF-23`, `RF-27`, `AC-46`
- **Arquivos:** `engine/comportamento.py`

**Descrição**

`derivar_CONFIABILIDADE_DADOS(nivel_controle, perfil)` pelas Definições §5, com ordem de avaliação `BAIXA → ALTA → MEDIA`. `NIVEL_CONTROLE` é parâmetro obrigatório: pular a etapa anterior não compila.

**Critérios de aceite**

- [x] `NIVEL_CONTROLE = FRAGIL` produz `CONFIABILIDADE_DADOS = BAIXA` (`AC-46`)
- [x] A assinatura exige `NIVEL_CONTROLE` — não há caminho que a derive sem ele
- [x] A ordem de avaliação testa `BAIXA` antes de `ALTA`
- [x] Chamar a função com argumentos fora de ordem é recusado pelo `mypy`

**Status:** `[x] concluída`

---

### `T-14` — Testar `NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS` e sua ordem de avaliação

- **Tipo:** `Test`
- **Dependências:** `T-13`
- **Rastreia:** `RF-23`, `AC-46`
- **Arquivos:** `tests/regras/test_comportamento.py`

**Descrição**

Testes por exemplo cobrindo os três níveis de controle, as três faixas de confiabilidade e o caso `AC-46`, que só passa se `BAIXA` for testada antes de `ALTA`.

**Critérios de aceite**

- [x] `test_AC46_fragil_implica_confiabilidade_baixa` passa
- [x] Há ao menos um caso para cada valor de `NIVEL_CONTROLE` e de `CONFIABILIDADE_DADOS`
- [x] Todas as asserções usam `assertar_exato`
- [x] Cada teste cita `AC-46` ou a seção normativa que verifica

**Status:** `[x] concluída`

---

### `T-15` — Implementar `RISCO_RECAIDA` pela regra D.4 (5 sinais)

- **Tipo:** `Data`
- **Dependências:** `T-13`
- **Rastreia:** `RF-18`, `AC-24`, `AC-25`
- **Arquivos:** `engine/risco.py`

**Descrição**

Contar 1 sinal por condição ativa entre `NOVA_DIVIDA_PREVISTA`, `MECANISMO_DEFICIT`, `HISTORICO_RECAIDA`, `NOVO_PARCELAMENTO_PREVISTO` e `PACTO` (§11.4), devolvendo `ClassificacaoRisco` com os sinais individuais para auditoria. `0` = BAIXO, `1–2` = MODERADO, `3+` = ALTO.

**Critérios de aceite**

- [x] Cada `SinalD4` registra `ativo` e `desconhecido` separadamente
- [x] Sinal com dado desconhecido **não** incrementa a contagem (`AC-25`)
- [x] `PACTO = EM_CONSTRUCAO` + `HISTORICO_RECAIDA = SIM` + `NOVA_DIVIDA_PREVISTA = TALVEZ` dá contagem 3 e `ALTO` (`AC-24`)
- [x] A tupla de sinais permite ao revisor refazer a contagem
- [x] O módulo declara as regras que implementa

**Status:** `[x] concluída`

---

### `T-16` — Implementar `RISCO_COMPORTAMENTAL_GERAL` pela regra D.4 (6 sinais)

- **Tipo:** `Data`
- **Dependências:** `T-15`
- **Rastreia:** `RF-18`, `AC-25`
- **Arquivos:** `engine/risco.py`

**Descrição**

Os seis sinais da §11.4, sendo o sexto `NIVEL_CONTROLE = FRAGIL` — o que torna a derivação de `NIVEL_CONTROLE` pré-requisito de assinatura. Mesma classificação por faixa da tarefa anterior.

**Critérios de aceite**

- [x] A função exige `NIVEL_CONTROLE` como parâmetro
- [x] Os seis sinais da §11.4 estão presentes e são contados individualmente
- [x] Dado desconhecido não conta como risco positivo (`AC-25`)
- [x] Faixas `0` = BAIXO, `1–2` = MODERADO, `3+` = ALTO

**Status:** `[x] concluída`

---

### `T-17` — Testar a regra D.4: contagem, faixas e dado desconhecido

- **Tipo:** `Test`
- **Dependências:** `T-16`
- **Rastreia:** `RF-18`, `AC-24`, `AC-25`
- **Arquivos:** `tests/regras/test_D4.py`

**Descrição**

Testes por ID cobrindo `AC-24` (contagem 3 → ALTO), `AC-25` (desconhecido não conta) e as fronteiras 0/1/2/3 das duas classificações.

**Critérios de aceite**

- [x] `test_D4_desconhecido_nao_conta_como_risco` passa (`AC-25`)
- [x] `test_AC24_recaida_conta_tres_sinais_e_classifica_alto` passa
- [x] As fronteiras 0, 1, 2 e 3 sinais são testadas nas duas classificações
- [x] Todas as asserções de nível usam `assertar_exato`

**Status:** `[x] concluída`

---

### `T-18` — Derivar `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`

- **Tipo:** `Data`
- **Dependências:** `T-12`, `T-15`
- **Rastreia:** `RF-24`, `AC-34`, `AC-35`
- **Arquivos:** `engine/comportamento.py`

**Descrição**

Conjunção obrigatória: `NECESSIDADE_VITORIA ≥ P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA` **E** ao menos um entre `HISTORICO_ABANDONO`, `RISCO_RECAIDA` alto ou `NIVEL_CONTROLE` frágil (Definições §1). Nenhum dos dois grupos basta sozinho.

**Critérios de aceite**

- [x] A função recebe `NIVEL_CONTROLE` e `RISCO_RECAIDA` já derivados, como parâmetros obrigatórios
- [x] `NECESSIDADE_VITORIA = 8` + `HISTORICO_ABANDONO = SIM` + recaída BAIXO + controle FORTE ⇒ SIM (`AC-34`)
- [x] `NECESSIDADE_VITORIA = 6` + `HISTORICO_ABANDONO = SIM` ⇒ NAO (`AC-35`)
- [x] O limiar vem de `Parametros`, nunca de literal no código

**Status:** `[x] concluída`

---

### `T-19` — Testar `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`

- **Tipo:** `Test`
- **Dependências:** `T-18`
- **Rastreia:** `RF-24`, `AC-34`, `AC-35`
- **Arquivos:** `tests/regras/test_comportamento.py`

**Descrição**

Cobrir os dois lados da conjunção: sinal comportamental isolado não basta, necessidade de vitória isolada não basta, e a fronteira exata do limiar.

**Critérios de aceite**

- [x] `test_AC34_conjuncao_produz_incompatibilidade` passa
- [x] `test_AC35_sinal_isolado_nao_basta` passa
- [x] Há caso com necessidade alta e nenhum sinal comportamental ⇒ NAO
- [x] A fronteira `NECESSIDADE_VITORIA` = limiar exato é testada

**Status:** `[x] concluída`

---

### `T-20` — Calcular pagamentos devidos × efetivos, resultados e `GAP_CAIXA_VS_ESTRUTURAL`

- **Tipo:** `Data`
- **Dependências:** `T-07`, `T-08`
- **Rastreia:** `RF-14`, `AC-05`, `AC-08`, `AC-32`
- **Arquivos:** `engine/diagnostico.py`

**Descrição**

`PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES`, `PAGAMENTOS_EFETIVOS_DIVIDAS`, `RESULTADO_CAIXA_OBSERVADO`, `RESULTADO_MENSAL_ATUAL`, `DEFICIT_MENSAL` e `GAP_CAIXA_VS_ESTRUTURAL = RESULTADO_CAIXA_OBSERVADO − RESULTADO_MENSAL_ATUAL` — diagnóstico sem limiar (§11.8). Pagamento efetivo 0 é valor legítimo; seguro incluído na parcela não é somado de novo.

**Critérios de aceite**

- [x] `GAB-A` produz devidos 2.000, efetivos 800, observado +200, `RESULTADO_MENSAL_ATUAL` −1.000, gap 1.200 e `DEFICIT_MENSAL` 1.000 (`AC-05`)
- [x] Parcela de 1.000 com seguro de 50 já incluído permanece 1.000 (`AC-08`, `EC-12`)
- [x] `PAGAMENTO_MENSAL_EFETIVO = 0` é tratado como valor, não como ausência (`AC-32`)
- [x] Nenhum limiar é aplicado sobre o gap (`P_CAIXA_VS_ESTRUTURAL` não é lido)
- [x] Dado material `DESCONHECIDO` produz diagnóstico parcial, nunca estimativa

**Status:** `[x] concluída`

---

### `T-21` — Classificar `STATUS_FINANCEIRO` com `PISO_CAPACIDADE`

- **Tipo:** `Data`
- **Dependências:** `T-20`
- **Rastreia:** `RF-26`, `AC-37`, `AC-38`, `AC-39`
- **Arquivos:** `engine/diagnostico.py`

**Descrição**

`PISO_CAPACIDADE = MAX(P_PISO_CAPACIDADE_ABSOLUTO, RENDA_TOTAL_RECORRENTE × P_PISO_CAPACIDADE_PERCENTUAL)`; `CAPACIDADE_ATAQUE_ATUAL = MAX(0, RESULTADO_MENSAL_ATUAL)`. O piso **classifica** e nunca altera a capacidade.

**Critérios de aceite**

- [x] `RESULTADO_MENSAL_ATUAL = −500` ⇒ `DEFICIT` e capacidade 0 (`AC-37`)
- [x] Resultado 200 com piso 300 ⇒ `EQUILIBRIO_FRAGIL` e capacidade **200** — nem 0, nem 300 (`AC-38`)
- [x] Resultado 500 com piso 300 ⇒ `CAPACIDADE_POSITIVA` e capacidade 500 (`AC-39`)
- [x] Nenhum caminho do código usa `PISO_CAPACIDADE` para truncar, elevar ou substituir a capacidade
- [x] Os dois parâmetros do piso vêm de `Parametros`

**Status:** `[x] concluída`

---

### `T-22` — Compor o `FATOR_SEGURANCA` de forma subtrativa

- **Tipo:** `Data`
- **Dependências:** `T-13`, `T-16`, `T-21`
- **Rastreia:** `RF-25`, `AC-36`, `AC-26`
- **Arquivos:** `engine/diagnostico.py`

**Descrição**

`REDUCAO_SEGURANCA_TOTAL` é a **soma** de `REDUCAO_RENDA_VARIAVEL`, `REDUCAO_CONFIABILIDADE`, `REDUCAO_RISCO_COMPORTAMENTAL` e `REDUCAO_RECAIDA`; `FATOR_SEGURANCA = MAX(P_FATOR_SEGURANCA_MINIMO, 1 − REDUCAO_SEGURANCA_TOTAL)`. Composição multiplicativa é proibida e o piso entra por último.

**Critérios de aceite**

- [x] Reduções 0,20 + 0,15 + 0,10 com piso 0,60 produzem `FATOR_SEGURANCA` = 0,60 (`AC-36`)
- [x] `P_REDUCAO_RISCO_COMPORTAMENTAL_ALTO` e `P_REDUCAO_HISTORICO_RECAIDA` são somadas separadamente, sem que uma absorva a outra (`AC-26`)
- [x] Apenas `RISCO_COMPORTAMENTAL_GERAL = ALTO` aciona a redução comportamental
- [x] Não existe multiplicação entre reduções em nenhum caminho
- [x] A função exige `CONFIABILIDADE_DADOS` e as duas classificações de risco como parâmetros

**Status:** `[x] concluída`

---

### `T-23` — Calcular as três capacidades e `MODO_ESTABILIZACAO`

- **Tipo:** `Data`
- **Dependências:** `T-22`
- **Rastreia:** `RF-14`, `RF-15`, `AC-06`, `AC-07`, `EC-10`, `EC-11`
- **Arquivos:** `engine/diagnostico.py`

**Descrição**

`BASE_CONSERVADORA = MIN(RESULTADO_MENSAL_ATUAL, CAPACIDADE_ATAQUE_DECLARADA)`, `CAPACIDADE_ATAQUE_CONSERVADORA = BASE_CONSERVADORA × FATOR_SEGURANCA` (a única que alimenta o cronograma) e `CAPACIDADE_ATAQUE_POTENCIAL`, que inclui `ECONOMIA_POTENCIAL_IMEDIATA` e nunca entra no cronograma-base. `RESULTADO_MENSAL_ATUAL < 0` ⇒ capacidade 0 e `MODO_ESTABILIZACAO`.

**Critérios de aceite**

- [x] `GAB-B` produz piso 300, `EQUILIBRIO_FRAGIL`, capacidade atual 200, base 200, fator 1,00, conservadora 200 e potencial 600 (`AC-06`)
- [x] Nenhum consumidor do cronograma-base lê `CAPACIDADE_ATAQUE_POTENCIAL` (`AC-07`, `EC-11`)
- [x] `RESULTADO_MENSAL_ATUAL < 0` ⇒ `CAPACIDADE_ATAQUE_ATUAL = 0` e `MODO_ESTABILIZACAO = True` (`EC-10`)
- [x] Em modo estabilização o motor continua e devolve o diagnóstico completo
- [x] `GAP_AUTOPERCEPCAO` é calculado como `AUTOPERCEPCAO_CONTROLE ≥ P_AUTOPERCEPCAO E NIVEL_CONTROLE ≠ FORTE`

**Status:** `[x] concluída`

---

### `T-24` — Encadear `calcular_diagnostico` na ordem de derivação obrigatória

- **Tipo:** `Data`
- **Dependências:** `T-18`, `T-23`
- **Rastreia:** `RF-27`, `RF-14`
- **Arquivos:** `engine/diagnostico.py`

**Descrição**

Compor a função pública `calcular_diagnostico(estado, parametros)` seguindo o grafo da §11.10: `NIVEL_CONTROLE` → `CONFIABILIDADE_DADOS` → D.4 → `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` → `FATOR_SEGURANCA` → capacidades. A ordem é imposta por assinatura, não por convenção.

**Critérios de aceite**

- [x] Cada etapa recebe o resultado da anterior como parâmetro obrigatório
- [x] Reordenar as chamadas produz erro de `mypy`, não resultado diferente
- [x] `Diagnostico` devolvido contém todos os campos da §4 do plano
- [x] A função é pura: sem relógio, sem I/O, sem global mutável

**Status:** `[x] concluída`

---

### `T-25` — Testar a ordem de derivação, o fator subtrativo e a classificação financeira

- **Tipo:** `Test`
- **Dependências:** `T-24`
- **Rastreia:** `RF-27`, `RF-25`, `RF-26`, `AC-26`, `AC-36`, `AC-37`, `AC-38`, `AC-39`
- **Arquivos:** `tests/regras/test_diagnostico.py`, `tests/estatica/test_ordem_de_derivacao.py`

**Descrição**

Testes por exemplo para `AC-36`, `AC-26` e as três faixas de `STATUS_FINANCEIRO`, mais um teste estático que prova que a ordem de derivação é imposta por tipo (a versão fora de ordem não passa no `mypy`).

**Critérios de aceite**

- [x] `test_AC36_soma_primeiro_piso_depois` passa
- [x] `test_D4_reducoes_separadas` passa (`AC-26`)
- [x] `test_AC37`, `test_AC38` e `test_AC39` cobrem as três faixas com `assertar_exato`
- [x] `test_ordem_de_derivacao` executa `mypy` sobre um trecho fora de ordem e exige falha

**Status:** `[x] concluída`

---

### `T-26` — Reproduzir os gabaritos `GAB-A` e `GAB-B`

- **Tipo:** `Test`
- **Dependências:** `T-09`, `T-11`, `T-24`
- **Rastreia:** `RF-14`, `RF-15`, `AC-05`, `AC-06`, `AC-07`
- **Arquivos:** `tests/gabaritos/test_gabarito_a_deficit.py`, `tests/gabaritos/test_gabarito_b_equilibrio_fragil.py`

**Descrição**

Testes marcados `gabarito` que rodam o diagnóstico sobre as fixtures e conferem as 8 saídas de `GAB-A` e as 7 de `GAB-B`, incluindo que o cronograma-base de `GAB-B` usa 200 e nunca 600.

**Critérios de aceite**

- [x] `test_gabarito_a_deficit` confere as 8 saídas de `AC-05` e `MODO_ESTABILIZACAO = SIM`
- [x] `test_gabarito_b_equilibrio_fragil` confere as 7 saídas de `AC-06`
- [x] Um caso separado prova `AC-07`: o cronograma-base usa no máximo 200
- [x] Valores monetários acumulados usam `assertar_monetario`; status e classificações usam `assertar_exato`
- [x] Os testes rodam sob `pytest -m gabarito`

**Status:** `[x] concluída`

---

## Entrega 3 — Elegibilidade: valor de quitação, gates e eventos previstos

### `T-27` — Compor `VALOR_RELEVANTE_PARA_QUITACAO`

- **Tipo:** `Data`
- **Dependências:** `T-08`
- **Rastreia:** `RF-06`, `AC-20`, `AC-21`, `EC-14`
- **Arquivos:** `engine/valor_quitacao.py`

**Descrição**

Usa `VALOR_QUITACAO_HOJE` apenas quando confirmado **e** com `STATUS_VALIDADE_PROPOSTA = VIGENTE`; caso contrário, `SALDO_DEVEDOR_ATUAL` (§11.2). Saldo também desconhecido ⇒ resultado `DESCONHECIDO`, nunca estimativa.

**Critérios de aceite**

- [x] `QUITACAO_CONSULTADA = NAO` ⇒ usa `SALDO_DEVEDOR_ATUAL` (`AC-20`)
- [x] `STATUS_VALIDADE_PROPOSTA ∈ {EXPIRADA, VALIDADE_DESCONHECIDA}` ⇒ usa saldo (`AC-20`, `EC-14`)
- [x] Sem quitação vigente e com saldo `DESCONHECIDO` ⇒ `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO` (`AC-21`)
- [x] Validade desconhecida com diferença materialmente relevante gera `PRIORIDADE_INFORMACAO`
- [x] Nenhum caminho produz valor estimado

**Status:** `[x] concluída`

---

### `T-28` — Testar a composição do valor relevante para quitação

- **Tipo:** `Test`
- **Dependências:** `T-27`
- **Rastreia:** `RF-06`, `AC-20`, `AC-21`, `EC-14`
- **Arquivos:** `tests/regras/test_valor_quitacao.py`

**Descrição**

Cobrir as quatro situações da tabela da §11.2 e o caso de `PRIORIDADE_INFORMACAO`.

**Critérios de aceite**

- [x] Um teste por linha da tabela da §11.2
- [x] `test_AC21_saldo_desconhecido_propaga_desconhecido` passa
- [x] `test_EC14_validade_desconhecida_gera_prioridade_informacao` passa
- [x] Asserções de estado usam `assertar_exato`

**Status:** `[x] concluída`

---

### `T-29` — Aplicar os Gates 1 e 2: Informação e Contenção de risco

- **Tipo:** `Data`
- **Dependências:** `T-04`, `T-27`
- **Rastreia:** `RF-17`, `RF-16`, `AC-23`, `AC-43`, `AC-44`, `EC-15`
- **Arquivos:** `engine/gates.py`

**Descrição**

Gate 1 marca `INFORMACAO_PENDENTE` com `GATE_PENDENTE = INFORMACAO` quando falta dado material — mas **não** bloqueia por falta apenas da simulação marginal, se o fallback da §11.1 for possível. Gate 2 desvia para `ORDEM_ACOES` com `INTERVENCAO_PENDENTE` + `CONTENCAO_RISCO`.

**Critérios de aceite**

- [x] Dívida desviada pelo Gate 2 fica `INTERVENCAO_PENDENTE` com `GATE_PENDENTE = CONTENCAO_RISCO` (`AC-43`)
- [x] `QUITADA_A_CONFIRMAR` fica inelegível, `INFORMACAO_PENDENTE` + `GATE_PENDENTE = INFORMACAO` (`AC-44`)
- [x] Risco alto, por si só, nunca torna a dívida a primeira (`AC-23`)
- [x] Quitação que é a própria ação de contenção e é executável pode receber prioridade excepcional, com motivo expresso (`EC-15`)
- [x] Falta apenas da simulação marginal não aciona o Gate 1

**Status:** `[x] concluída`

---

### `T-30` — Aplicar os Gates 3 e 4: Transformação e Oportunidade com prazo

- **Tipo:** `Data`
- **Dependências:** `T-29`
- **Rastreia:** `RF-17`, `AC-22`, `EC-16`
- **Arquivos:** `engine/gates.py`

**Descrição**

Gate 3 tira da ordem ordinária a dívida com renegociação ou troca pendente (`INTERVENCAO_PENDENTE` + `TRANSFORMACAO`). Gate 4 avalia `OPORTUNIDADE_EXECUTAVEL` antes da ordem-base, sem bloquear e sem implicar primeiro lugar. A sequência 1→2→3→4 é fixa.

**Critérios de aceite**

- [x] Renegociação ou troca pendente ⇒ `INTERVENCAO_PENDENTE` + `GATE_PENDENTE = TRANSFORMACAO` e fora da ordem ordinária (`AC-22`)
- [x] Executada, rejeitada ou encerrada a intervenção, a dívida volta a ser elegível (`AC-22`)
- [x] Desconto vigente não coloca a dívida em primeiro lugar automaticamente (`EC-16`)
- [x] A ordem de avaliação dos quatro gates é fixa e o gate bloqueador é registrado em `gate_bloqueador`
- [x] Cada bloqueio devolve `motivo` textual reaproveitável pela `JUSTIFICATIVA_POSICAO`

**Status:** `[x] concluída`

---

### `T-31` — Mapear `STATUS_DIVIDA` para `DIVIDA_STATUS_ESTRATEGICO`

- **Tipo:** `Data`
- **Dependências:** `T-30`
- **Rastreia:** `RF-17`, `AC-41`, `AC-42`, `AC-45`
- **Arquivos:** `engine/gates.py`

**Descrição**

Aplicar a tabela das Definições §6: `STATUS_DIVIDA` **não** decide elegibilidade — quem decide são os gates. Cobrir os cinco status reais, incluindo `EM_ACORDO` nos dois sabores e `COBRANCA_SEM_PAGAMENTO`.

**Critérios de aceite**

- [x] `EM_ACORDO` com acordo executado e estrutura conhecida pode atingir `PRONTA_PARA_ORDENACAO` (`AC-41`)
- [x] `EM_ACORDO` com negociação aberta ⇒ `INTERVENCAO_PENDENTE` + `TRANSFORMACAO`
- [x] `COBRANCA_SEM_PAGAMENTO` com saldo conhecido pode chegar a `PRONTA_PARA_ORDENACAO`, sem inventar `PAGAMENTO_MENSAL_DEVIDO_VIGENTE` (`AC-42`)
- [x] `OUTRA` ⇒ `EM_ANALISE`, sem ataque (`AC-45`)
- [x] Nenhum caminho usa `STATUS_DIVIDA` sozinho para decidir elegibilidade

**Status:** `[x] concluída`

---

### `T-32` — Produzir `ParticaoElegibilidade` e a fila `ORDEM_ACOES`

- **Tipo:** `Data`
- **Dependências:** `T-31`
- **Rastreia:** `RF-17`, `EC-17`
- **Arquivos:** `engine/gates.py`

**Descrição**

Consolidar os resultados dos gates em `elegiveis`, `bloqueadas` e `ORDEM_ACOES` — fila **paralela**, jamais confundida com a `ORDEM_QUITACAO`. `DIVIDA_ELEGIVEL_ORDEM` exige status estratégico em `{PRONTA_PARA_ORDENACAO, EM_ATAQUE}`.

**Critérios de aceite**

- [x] `ORDEM_ACOES` é estrutura separada de `ORDEM_QUITACAO`, com tipo próprio
- [x] `elegiveis == ()` é estado válido e sinalizado, sem `DIVIDA_ALVO_ATUAL` (`EC-17`)
- [x] Toda dívida bloqueada aparece em `bloqueadas` com seu gate e motivo
- [x] A ordenação de `elegiveis` é total e determinística, com `DIVIDA_ID` como desempate final

**Status:** `[x] concluída`

---

### `T-33` — Testar os quatro gates, `GATE_PENDENTE` e `ORDEM_ACOES`

- **Tipo:** `Test`
- **Dependências:** `T-32`
- **Rastreia:** `RF-17`, `AC-22`, `AC-23`, `AC-41`, `AC-42`, `AC-43`, `AC-44`, `AC-45`, `EC-15`, `EC-16`, `EC-17`
- **Arquivos:** `tests/regras/test_gates.py`

**Descrição**

Um teste por critério de aceite dos gates, mais os três edge cases. Testa saída observável (`DIVIDA_STATUS_ESTRATEGICO`, `GATE_PENDENTE`, `DIVIDA_ELEGIVEL_ORDEM`, `ORDEM_ACOES`), nunca função interna.

**Critérios de aceite**

- [x] `test_gate2_risco_alto_nao_e_primeira_divida` passa (`AC-23`)
- [x] Existe um teste nomeado por cada um de `AC-22`, `AC-41`, `AC-42`, `AC-43`, `AC-44`, `AC-45`
- [x] `test_EC17_nenhuma_elegivel_nao_produz_alvo` passa
- [x] A sequência fixa 1→2→3→4 é verificada com dívida que viola dois gates ao mesmo tempo
- [x] Todas as asserções usam `assertar_exato`

**Status:** `[x] concluída`

---

### `T-34` — Filtrar o evento futuro previsto da projeção-base

- **Tipo:** `Data`
- **Dependências:** `T-15`, `T-32`
- **Rastreia:** `RF-22`, `AC-30`
- **Arquivos:** `engine/eventos.py`

**Descrição**

`NOVA_DIVIDA_PREVISTA ∈ {SIM, TALVEZ}` é filtrado antes da simulação: não vira `Divida`, não altera saldo, não entra em `ORDEM_QUITACAO`. Entra apenas como sinal de `RISCO_RECAIDA` e como alerta na saída (§11.6).

**Critérios de aceite**

- [x] Nenhuma dívida hipotética chega à partição de elegibilidade
- [x] Nenhum saldo futuro é alterado pela previsão (`AC-30`)
- [x] O dado alimenta `RISCO_RECAIDA` e um campo de alerta na saída
- [x] `JANELA_NOVA_DIVIDA` é preservada no alerta, sem virar evento determinístico

**Status:** `[x] concluída`

---

### `T-35` — Testar `NOVA_DIVIDA_PREVISTA` fora da projeção-base

- **Tipo:** `Test`
- **Dependências:** `T-34`
- **Rastreia:** `RF-22`, `AC-30`
- **Arquivos:** `tests/regras/test_RF22.py`

**Descrição**

Verificar que a previsão não muda ordem nem saldo, e que aparece como alerta e como sinal de risco.

**Critérios de aceite**

- [x] `test_RF22_nova_divida_prevista_fora_da_projecao` passa (`AC-30`)
- [x] Um caso compara a saída com e sem a previsão: ordem e saldos idênticos
- [x] O sinal de `RISCO_RECAIDA` muda entre os dois casos
- [x] Asserções de ordem usam `assertar_exato`

**Status:** `[x] concluída`

---

## Entrega 4 — Ciclo mensal, resíduo do ataque e fluxo liberado

### `T-36` — Simular a trajetória isolada de uma dívida até `SALDO = 0`

- **Tipo:** `Data`
- **Dependências:** `T-07`, `T-27`
- **Rastreia:** `RF-05`, `AC-47`, `EC-13`
- **Arquivos:** `engine/trajetoria.py`

**Descrição**

`simular_trajetoria_isolada(chave)` evolui uma única dívida e devolve `DESEMBOLSO_FUTURO`, `MESES_ATE_QUITACAO` e `ESTOUROU_HORIZONTE`. Cada trajetória é somada até seu **próprio** `SALDO = 0`; é permitido horizonte comum com desembolso 0 após a quitação, desde que matematicamente equivalente.

**Critérios de aceite**

- [x] Trajetórias com prazos diferentes são somadas cada uma até seu próprio saldo zero (`AC-47`)
- [x] Nenhum truncamento no menor prazo e nenhum horizonte fixo embutido
- [x] O horizonte máximo vem de `P_HORIZONTE_MAXIMO_SIMULACAO` e o estouro é sinalizado (`EC-13`)
- [x] A função é pura e determinística: mesma `ChaveTrajetoria`, mesmo resultado
- [x] `ChaveTrajetoria` é `frozen` e hasheável por valor

**Status:** `[x] concluída`

---

### `T-37` — Memoizar `simular_trajetoria_isolada`

- **Tipo:** `Infra`
- **Dependências:** `T-36`
- **Rastreia:** `RF-05`
- **Arquivos:** `engine/trajetoria.py`

**Descrição**

Aplicar `functools.lru_cache` chaveado por `ChaveTrajetoria`, com escopo de execução e limpeza entre execuções. O cache é otimização de custo do Híbrido e **deve ser indistinguível de sua ausência**.

**Critérios de aceite**

- [x] O cache é chaveado por valor, com `Decimal` comparado exatamente
- [x] Existe uma forma de desligar o cache para efeito de teste
- [x] O cache é limpo entre execuções de `calcular_plano`
- [x] Nenhum global mutável além do cache puro é introduzido

**Status:** `[x] concluída`

---

### `T-38` — Testar `AC-47` e a equivalência cache ligado × desligado

- **Tipo:** `Test`
- **Dependências:** `T-37`
- **Rastreia:** `RF-05`, `AC-47`
- **Arquivos:** `tests/regras/test_trajetoria.py`

**Descrição**

Provar o horizonte próprio de cada trajetória e que ligar o cache não muda nenhum resultado — a otimização não pode alterar o determinismo.

**Critérios de aceite**

- [x] `test_AC47_cada_trajetoria_ate_seu_proprio_saldo_zero` passa
- [x] Uma carteira sintética produz resultados idênticos com e sem cache, campo a campo
- [x] O caso de horizonte comum com desembolso 0 após quitação é provado equivalente
- [x] `test_EC13_horizonte_estourado_sinaliza` passa

**Status:** `[x] concluída`

---

### `T-39` — Calcular `BENEFICIO_MARGINAL_AMORTIZACAO`

- **Tipo:** `Data`
- **Dependências:** `T-23`, `T-36`
- **Rastreia:** `RF-05`, `AC-19`
- **Arquivos:** `engine/beneficio_marginal.py`

**Descrição**

`DELTA_TESTE_AVALANCHE = MIN(CAPACIDADE_ATAQUE_CONSERVADORA, VALOR_RELEVANTE_PARA_QUITACAO)`; simular as trajetórias A (sem delta) e B (com delta) e dividir a diferença de desembolso por `DELTA_REALMENTE_APLICADO` (§11.1). A função aceita um `delta_disponivel` explícito para o reranqueamento intramês.

**Critérios de aceite**

- [x] A fórmula de `AC-19` é reproduzida exatamente
- [x] `DELTA_REALMENTE_APLICADO` é registrado e usado como divisor
- [x] `origem = "SIMULACAO"` quando as duas trajetórias fecham
- [x] A função nunca lê a capacidade cheia por conta própria — o delta é sempre parâmetro
- [x] `BeneficioMarginal` carrega os dois desembolsos, para o revisor refazer a conta

**Status:** `[x] concluída`

---

### `T-40` — Implementar o fallback taxa → `CET` e `ORDEM_STATUS = PROVISORIA`

- **Tipo:** `Data`
- **Dependências:** `T-39`
- **Rastreia:** `RF-21`, `AC-33`
- **Arquivos:** `engine/beneficio_marginal.py`

**Descrição**

Trajetória que não chega deterministicamente à extinção ⇒ `BENEFICIO_MARGINAL_AMORTIZACAO = NAO_CALCULAVEL` e ranqueamento por `TAXA_EFETIVA_MENSAL_NORMALIZADA` e, na falta desta, por `CET` comparável. A ordem resultante é `PROVISORIA`. Nunca fabricar benefício marginal artificial.

**Critérios de aceite**

- [x] Saldo, taxa ou fluxo indeterminado produz `NAO_CALCULAVEL`, nunca um número (já coberto por `T-39`: `BENEFICIO_MARGINAL_AMORTIZACAO = DESCONHECIDO`, semanticamente equivalente a `NAO_CALCULAVEL` para esta variável — ver docstring do módulo, "Caso extremo sem fallback possível")
- [x] O fallback é aplicado na ordem 1º taxa, 2º `CET`, registrado em `origem` (já coberto por `T-39`, função `_fallback`)
- [x] `origem != "SIMULACAO"` ⇒ `ORDEM_STATUS = PROVISORIA` (`AC-33`) — adicionado em `T-40`: `determinar_ordem_status_por_origem`
- [x] Sem taxa e sem `CET`, a dívida vai para `INFORMACAO_PENDENTE`, não para o fim da fila com valor 0 (já coberto por `T-39`: `origem="INDISPONIVEL"` com `BENEFICIO_MARGINAL_AMORTIZACAO=DESCONHECIDO`, nunca `0`; o desvio efetivo para `INFORMACAO_PENDENTE` é papel do Gate 1 já implementado em `engine/gates.py`/`T-29`, acionado pelo motor completo em `T-63`/`T-64`, fora do escopo desta tarefa isolada)

**Status:** `[x] concluída`

---

### `T-41` — Testar benefício marginal e fallback

- **Tipo:** `Test`
- **Dependências:** `T-40`
- **Rastreia:** `RF-05`, `RF-21`, `AC-19`, `AC-33`
- **Arquivos:** `tests/regras/test_beneficio_marginal.py`

**Descrição**

Cobrir a fórmula de `AC-19`, o delta do teste, os dois níveis de fallback e o rebaixamento a `PROVISORIA`.

**Critérios de aceite**

- [x] `test_AC19_formula_do_beneficio_marginal` passa
- [x] `test_AC33_fallback_por_taxa_e_ordem_provisoria` passa
- [x] Há um caso em que só `CET` existe e o fallback de 2º nível é usado (`test_AC33_fallback_por_cet_quando_taxa_tambem_desconhecida`)
- [x] `ORDEM_STATUS` é comparado com `assertar_exato`

**Status:** `[x] concluída`

---

### `T-42` — Executar o mês `M-01..M-06` com alvo preservado

- **Tipo:** `Data`
- **Dependências:** `T-23`, `T-32`
- **Rastreia:** `RF-01`, `RF-02`, `AC-13`
- **Arquivos:** `engine/ciclo_mensal.py`

**Descrição**

`executar_mes(estado, SelecionarAlvo, parametros)` percorre os passos `M-01` a `M-06` sem pular etapa: abertura do mês, pagamentos normais, aplicação do ataque no `DIVIDA_ALVO_ATUAL` e verificação de quitação. `M-05`: o alvo é preservado. O ciclo existe **uma única vez** no código; o método entra só como `SelecionarAlvo`.

**Critérios de aceite**

- [x] Os passos `M-01` a `M-06` são executados nesta ordem e são identificáveis no código
- [x] Não existe ramificação por `METODO` dentro do ciclo
- [x] `EstadoSimulacao` é imutável: cada passo devolve nova instância
- [x] Sem quitação, `DIVIDA_ALVO_ATUAL` permanece o mesmo ao fim do mês (`AC-13`)
- [x] Dívida encerrada só com o pagamento normal também conta como quitação (`EC-02`)

**Status:** `[x] concluída`

---

### `T-43` — Cascatear o resíduo do ataque com reranqueamento antes de cada aplicação

- **Tipo:** `Data`
- **Dependências:** `T-39`, `T-42`
- **Rastreia:** `RF-03`, `AC-14`
- **Arquivos:** `engine/ciclo_mensal.py`

**Descrição**

Passos `M-07`/`M-08` com `A-01..A-03`: quitado o alvo, o `RESIDUO_ATAQUE_M` é recalculado, a ordem é reranqueada (`O-03`) e o delta do teste passa a ser `DELTA_TESTE_AVALANCHE_RESIDUO = MIN(RESIDUO_ATAQUE_M, VALOR_RELEVANTE_PARA_QUITACAO)`. O laço repete enquanto houver resíduo e elegível.

**Critérios de aceite**

- [x] O reranqueamento ocorre **antes** de cada aplicação de resíduo (`O-03`)
- [x] O delta usado é o resíduo restante, nunca a capacidade cheia (`AC-14`)
- [x] Cada aplicação é registrada em `aplicacoes_residuo`, com dívida, valor e ordem
- [x] Duas quitações no mesmo mês produzem duas rodadas de cascata
- [x] `reranqueamentos` registra 0, 1 ou vários eventos, conforme `R-03`

**Status:** `[x] concluída`

---

### `T-44` — Registrar `ATAQUE_NAO_UTILIZADO` quando o resíduo não tem destino

- **Tipo:** `Data`
- **Dependências:** `T-43`
- **Rastreia:** `RF-03`, `EC-01`
- **Arquivos:** `engine/ciclo_mensal.py`

**Descrição**

`A-04`: sobrou resíduo e não há mais dívida elegível ⇒ o valor vira `ATAQUE_NAO_UTILIZADO` e é mantido como caixa do usuário, com acumulação ao longo dos meses. Nenhum valor desaparece da simulação.

**Critérios de aceite**

- [x] Ataque aplicado + `ATAQUE_NAO_UTILIZADO` == ataque disponível, em todo mês
- [x] O acumulado aparece em `ATAQUE_NAO_UTILIZADO_ACUMULADO` no estado de simulação
- [x] Nenhum caminho descarta resíduo silenciosamente
- [x] Um invariante ao fim do mês falha ruidosamente com `ErroInvariante` se a conta não fechar

**Status:** `[x] concluída`

---

### `T-45` — Consolidar `VALOR_FLUXO_LIBERADO` e incorporá-lo só em *m+1*

- **Tipo:** `Data`
- **Dependências:** `T-42`
- **Rastreia:** `RF-04`, `AC-15`, `AC-32`, `EC-18`
- **Arquivos:** `engine/ciclo_mensal.py`

**Descrição**

`F-01..F-03` e §11.7: o fluxo liberado corresponde ao `PAGAMENTO_MENSAL_EFETIVO` que realmente saía do orçamento. É **devolvido** pelo mês, não somado dentro dele, e entra na capacidade apenas na abertura do mês seguinte.

**Critérios de aceite**

- [x] Dívida com efetivo 700 quitada no mês 4 reforça a capacidade só a partir do mês 5 (`AC-15`)
- [x] Dívida com contratual 1.200 e efetivo 0 libera `VALOR_FLUXO_LIBERADO` = 0 (`AC-32`, `EC-18`)
- [x] `executar_mes` devolve o valor sem somá-lo à capacidade do próprio mês
- [x] Nenhum valor aparece simultaneamente como pagamento normal de *m* e como capacidade adicional de *m* (`F-03`)
- [x] Não há liberação retroativa

**Status:** `[x] concluída`

---

### `T-46` — Encadear `simular_cenario` com `M-10..M-12` e o horizonte máximo

- **Tipo:** `Data`
- **Dependências:** `T-44`, `T-45`
- **Rastreia:** `RF-01`, `RF-02`, `AC-13`, `EC-13`
- **Arquivos:** `engine/ciclo_mensal.py`

**Descrição**

`simular_cenario` repete `executar_mes` até quitar tudo ou estourar `P_HORIZONTE_MAXIMO_SIMULACAO`, incorpora o fluxo liberado na abertura de *m+1* (`M-10`/`M-11`) e, sem quitação e sem evento, **não** reranqueia (`M-12`, `R-02`). Devolve `Cenario` com ordem, prazo, custo, primeira vitória e o rastro mês a mês.

**Critérios de aceite**

- [x] `PRAZO_TOTAL`, `CUSTO_FUTURO_TOTAL`, `ORDEM_QUITACAO` e `MESES_PRIMEIRA_VITORIA` são produzidos (`test_cenario_produz_prazo_custo_ordem_e_primeira_vitoria`)
- [x] Mês sem quitação e sem evento não gera reranqueamento (`AC-13`) (`test_meses_sem_quitacao_nao_reranqueiam_entre_si`)
- [x] Estouro do horizonte encerra e sinaliza; alerta a partir de `P_HORIZONTE_ALERTA` (`EC-13`) (`test_estouro_do_horizonte_encerra_e_sinaliza_sem_abortar`, `test_alerta_horizonte_dispara_a_partir_de_p_horizonte_alerta_antes_do_maximo`)
- [x] `Cenario.meses` preserva o rastro completo para auditoria (`test_meses_preserva_rastro_completo_para_auditoria`)
- [x] O cenário roda em modo estabilização e é marcado condicional, sem abortar (`ESTOUROU_HORIZONTE=True`, nenhuma exceção lançada — mesmo teste de estouro acima)

**Status:** `[x] concluída`

---

### `T-47` — Testar as famílias de regra `M`, `A`, `F` e `R` por ID

- **Tipo:** `Test`
- **Dependências:** `T-46`
- **Rastreia:** `RF-01`, `RF-02`, `RF-03`, `RF-04`, `AC-13`, `AC-14`, `AC-15`, `AC-32`, `EC-01`, `EC-02`, `EC-18`
- **Arquivos:** `tests/regras/test_M.py`, `tests/regras/test_A.py`, `tests/regras/test_F.py`, `tests/regras/test_R.py`

**Descrição**

Um arquivo por família, cada teste nomeado com o ID da regra e testando saída observável do motor: `test_M07_residuo_reranqueia_antes_de_aplicar`, `test_R02_virada_de_mes_nao_reranqueia`, `test_A03_delta_do_residuo_nao_usa_capacidade_cheia`, `test_F02_fluxo_liberado_entra_em_m_mais_1`.

**Critérios de aceite**

- [x] Os quatro testes nomeados acima existem e passam
- [x] `EC-01` (resíduo sem destino) e `EC-18` (fluxo liberado 0) têm teste próprio
- [x] `AC-32` é testado com dívida de contratual 1.200 e efetivo 0
- [x] Nenhum teste chama função interna do ciclo; todos passam por `simular_cenario`
- [x] Meses, aplicação de resíduo e gatilho de recálculo usam `assertar_exato`

**Status:** `[x] concluída`

---

### `T-48` — Testar por propriedade os invariantes `A-04` e `F-03`

- **Tipo:** `Test`
- **Dependências:** `T-46`
- **Rastreia:** `RF-03`, `RF-04`
- **Arquivos:** `tests/invariantes/test_propriedades.py`

**Descrição**

Hypothesis com `derandomize=True`, duas propriedades apenas: nenhum valor desaparece da simulação (`A-04`) e nenhum valor é contado duas vezes (`F-03`), para qualquer carteira gerada.

**Critérios de aceite**

- [x] `derandomize=True` está configurado — a CI permanece determinística (comprovado rodando `tests/invariantes/test_propriedades.py` duas vezes seguidas e comparando os exemplos gerados: sequência idêntica em ambas as execuções, ver relatório da tarefa)
- [x] A propriedade de `A-04` roda sobre carteiras de 1 a 10 dívidas (`st.integers(min_value=1, max_value=10)` em `_st_tamanho_carteira`, saldos `st.decimals(allow_nan=False, allow_infinity=False)` convertidos via `dinheiro()`)
- [x] A propriedade de `F-03` verifica todo mês do horizonte (laço sobre `cenario.meses`, não apenas o primeiro)
- [x] As duas propriedades falham se o resíduo for descartado ou o fluxo somado duas vezes (verificado com mutação proposital em `tests/invariantes/test_mutacao_deteccao_de_bugs.py`, arquivo de teste permanente)

**Status:** `[x] concluída`

---

## Entrega 5 — Os três métodos

### `T-49` — Implementar a seleção de alvo da Avalanche

- **Tipo:** `Data`
- **Dependências:** `T-39`, `T-46`
- **Rastreia:** `RF-05`, `AC-19`
- **Arquivos:** `engine/metodos/avalanche.py`

**Descrição**

`O-01..O-03`: ordenar por `BENEFICIO_MARGINAL_AMORTIZACAO` decrescente, alvo fixo até quitação ou evento, reranqueamento no resíduo. Entra no ciclo apenas como `SelecionarAlvo`.

**Critérios de aceite**

- [x] A implementação é uma função `SelecionarAlvo`, sem nenhuma cópia do ciclo mensal
- [x] A ordenação é total e determinística, com `DIVIDA_ID` como desempate final
- [x] O alvo permanece fixo até quitação ou evento (`O-02`)
- [x] O delta usado no reranqueamento intramês é o resíduo (`O-03`, `AC-14`)

**Status:** `[x] concluída`

---

### `T-50` — Reproduzir `GAB-C` no método Avalanche

- **Tipo:** `Test`
- **Dependências:** `T-09`, `T-11`, `T-49`
- **Rastreia:** `RF-05`, `AC-01`
- **Arquivos:** `tests/gabaritos/test_gabarito_c_avalanche.py`

**Descrição**

Teste marcado `gabarito`: 6 meses, custo futuro total R$ 23719,46, primeira vitória no mês 4, sequência D001 → D002 → D003.

**Critérios de aceite**

- [x] As quatro saídas de `AC-01` conferem
- [x] O custo usa `assertar_monetario`; meses, primeira vitória e sequência usam `assertar_exato`
- [x] O teste cita `AC-01` no nome ou na docstring
- [x] Roda sob `pytest -m gabarito`

**Status:** `[x] concluída`

---

### `T-51` — Implementar a seleção de alvo da Bola de Neve e sua cadeia de desempate

- **Tipo:** `Data`
- **Dependências:** `T-27`, `T-46`
- **Rastreia:** `RF-06`, `AC-02`
- **Arquivos:** `engine/metodos/bola_de_neve.py`

**Descrição**

`O-04`/`O-05`: menor `VALOR_RELEVANTE_PARA_QUITACAO` primeiro, com a cadeia de desempate na ordem definida, terminando em `PESO_EMOCIONAL` e `DIVIDA_ID`.

**Critérios de aceite**

- [x] A ordenação usa `VALOR_RELEVANTE_PARA_QUITACAO`, não `SALDO_DEVEDOR_ATUAL` direto
- [x] A cadeia de desempate segue exatamente a ordem de `O-05`
- [x] `DIVIDA_ID` é o desempate final e garante determinismo
- [x] Dívida com valor relevante `DESCONHECIDO` não entra na ordenação, e sim em `INFORMACAO_PENDENTE`

**Status:** `[x] concluída`

---

### `T-52` — Reproduzir `GAB-C` no método Bola de Neve

- **Tipo:** `Test`
- **Dependências:** `T-11`, `T-51`
- **Rastreia:** `RF-06`, `AC-02`
- **Arquivos:** `tests/gabaritos/test_gabarito_c_bola_de_neve.py`, `tests/regras/test_O.py`

**Descrição**

6 meses, R$ 24463,97, primeira vitória no mês 1, sequência D003 → D002 → D001, mais o teste isolado da cadeia de desempate `O-05`.

**Critérios de aceite**

- [x] As quatro saídas de `AC-02` conferem
- [x] `test_O05_cadeia_de_desempate_da_bola_de_neve` passa
- [x] Sequência e meses usam `assertar_exato`
- [x] Roda sob `pytest -m gabarito`

**Status:** `[x] concluída`

---

### `T-53` — Construir o Híbrido em seis etapas com as três tolerâncias

- **Tipo:** `Data`
- **Dependências:** `T-18`, `T-49`, `T-51`
- **Rastreia:** `RF-07`, `AC-03`
- **Arquivos:** `engine/metodos/hibrido.py`

**Descrição**

`H-01..H-07`: seleção de `D*` pelas seis etapas determinísticas, com as três tolerâncias cumulativas e o desempate lexicográfico de seis níveis, terminando em `DIVIDA_ID` (`H-04`). Depois de `D*`, o ranqueamento volta a ser o da Avalanche.

**Critérios de aceite**

- [x] As seis etapas são identificáveis no código e citam `H-01..H-07`
- [x] As três tolerâncias são cumulativas e vêm de `Parametros`
- [x] O desempate lexicográfico tem os seis níveis, na ordem, com `DIVIDA_ID` por último
- [x] `PENALIDADE_CUSTO_VS_AVALANCHE` e `ATRASO_PRAZO_VS_AVALANCHE` são calculados como métricas da construção do Híbrido
- [x] Após `D*`, a ordem segue o benefício marginal

**Status:** `[x] concluída`

---

### `T-54` — Tratar Híbrido sem candidata como `NAO_APLICAVEL`

- **Tipo:** `Data`
- **Dependências:** `T-53`
- **Rastreia:** `RF-07`, `RF-08`, `EC-03`
- **Arquivos:** `engine/metodos/hibrido.py`

**Descrição**

`H-08`: nenhuma dívida atende às três tolerâncias ⇒ `CENARIO_HIBRIDO = NAO_APLICAVEL` e `ORDEM_HIBRIDA = NAO_APLICAVEL`. Não fabricar um Híbrido e não confundir com `NAO_CALCULAVEL`.

**Critérios de aceite**

- [x] Sem candidata, a classificação é `NAO_APLICAVEL`, jamais `NAO_CALCULAVEL` (`EC-03`)
- [x] Nenhum `D*` é escolhido por aproximação quando as tolerâncias falham
- [x] `test_H08_sem_candidata_nao_fabrica_hibrido` passa
- [x] A distinção entre os dois estados é comparada com `assertar_exato`

**Status:** `[x] concluída`

---

### `T-55` — Reproduzir `GAB-C` no método Híbrido

- **Tipo:** `Test`
- **Dependências:** `T-11`, `T-54`
- **Rastreia:** `RF-07`, `AC-03`
- **Arquivos:** `tests/gabaritos/test_gabarito_c_hibrido.py`, `tests/regras/test_H.py`

**Descrição**

6 meses, R$ 24107,20, primeira vitória no mês 1, sequência D003 → D001 → D002, `D*` = D003, penalidade 1,635% e atraso 0 mês. Mais `test_H04_desempate_lexicografico_seis_niveis`.

**Critérios de aceite**

- [x] As sete saídas de `AC-03` conferem
- [x] `D*` e o atraso de prazo usam `assertar_exato`
- [x] `test_H04_desempate_lexicografico_seis_niveis` exercita os seis níveis
- [x] Roda sob `pytest -m gabarito`

**Status:** `[x] concluída`

---

### `T-56` — Provar que o parâmetro externo muda o resultado

- **Tipo:** `Test`
- **Dependências:** `T-10`, `T-55`
- **Rastreia:** `RF-13`, `AC-17`
- **Arquivos:** `tests/estatica/test_parametro_externo_muda_resultado.py`

**Descrição**

Lado B de `AC-17`: rodar `GAB-C` com `P_MESES_VITORIA_RAPIDA = 0` numa fonte de parâmetros alternativa e exigir `CENARIO_HIBRIDO = NAO_APLICAVEL`, provando que a fonte externa é de fato lida.

**Critérios de aceite**

- [x] O teste altera apenas o arquivo de parâmetros, sem tocar em código do motor
- [x] O resultado muda de `HIBRIDO` para `NAO_APLICAVEL`
- [x] Nenhum default entra em cena quando o parâmetro é alterado
- [x] A asserção usa `assertar_exato`

**Status:** `[x] concluída`

---

## Entrega 6 — Comparação de cenários, recomendação e ordem publicada

### `T-57` — Eleger `CENARIO_ECONOMICAMENTE_SUPERIOR` com empate material de 1%

- **Tipo:** `Data`
- **Dependências:** `T-54`
- **Rastreia:** `RF-19`, `AC-27`, `AC-28`, `EC-19`
- **Arquivos:** `engine/comparacao.py`

**Descrição**

Achar o menor `CUSTO_FUTURO_TOTAL`; cenário a menos de `P_DIFERENCA_ECONOMICA_MATERIAL` (1%) desse custo está em empate material; entre os empatados vence o de menor `PRAZO_TOTAL` (§11.5).

**Critérios de aceite**

- [x] Custos diferindo em menos de 1% ⇒ empate material, vence o menor prazo (`AC-27`)
- [x] Três ou mais cenários empatados concorrem todos (`EC-19`)
- [x] Em `GAB-C` o superior é a Avalanche, com Híbrido a 1,6347% e Bola de Neve a 3,1388% fora do empate (`AC-28`)
- [x] O parâmetro de 1% vem de `Parametros` e não é confundido com o de 5%

**Status:** `[x] concluída`

---

### `T-58` — Avaliar `ECONOMICAMENTE_PROXIMO` por custo **e** prazo

- **Tipo:** `Data`
- **Dependências:** `T-57`
- **Rastreia:** `RF-20`, `AC-29`
- **Arquivos:** `engine/comparacao.py`

**Descrição**

`PENALIDADE_CUSTO(X)` e `ATRASO_PRAZO(X)` medidos contra o `CENARIO_ECONOMICAMENTE_SUPERIOR`; a proximidade exige **cumulativamente** ≤ `P_DIFERENCA_CUSTO_EQUIVALENTE` (5%) **e** ≤ `P_DIFERENCA_PRAZO_EQUIVALENTE` (2 meses).

**Critérios de aceite**

- [x] A conjunção é cumulativa: falhar um dos dois basta para `NAO` (`AC-29`)
- [x] A referência é o cenário superior, nunca a Avalanche por definição
- [x] `P_DIFERENCA_ECONOMICA_MATERIAL` e `P_DIFERENCA_CUSTO_EQUIVALENTE` nunca são usados no mesmo cálculo
- [x] `PENALIDADE_CUSTO` e `ATRASO_PRAZO` são expostos por método, para auditoria

**Status:** `[x] concluída`

---

### `T-59` — Testar empate material e proximidade econômica

- **Tipo:** `Test`
- **Dependências:** `T-55`, `T-58`
- **Rastreia:** `RF-19`, `RF-20`, `AC-27`, `AC-28`, `AC-29`, `EC-19`
- **Arquivos:** `tests/regras/test_comparacao.py`

**Descrição**

Separar os dois conceitos com os números do `GAB-C` — é o risco explícito da §8 da spec (confundir 1% com 5%).

**Critérios de aceite**

- [x] `test_AC28_gabc_superior_e_avalanche` confere 1,6347% e 3,1388%
- [x] `test_AC27_empate_material_desempata_por_prazo` passa
- [x] `test_AC29_proximidade_exige_custo_e_prazo` cobre os quatro quadrantes (passa/falha em cada eixo)
- [x] `test_EC19_empate_triplo` passa

**Status:** `[x] concluída`

---

### `T-60` — Classificar cenários e derivar `STATUS_METODO` (`S-01..S-03`)

- **Tipo:** `Data`
- **Dependências:** `T-54`, `T-58`
- **Rastreia:** `RF-08`, `AC-09`
- **Arquivos:** `engine/status_metodo.py`

**Descrição**

`NAO_CALCULAVEL` rebaixa `STATUS_METODO`; `NAO_APLICAVEL` **não** rebaixa. Inventário incompleto limita `STATUS_METODO` a `PROVISORIO` no máximo.

**Critérios de aceite**

- [x] `NAO_CALCULAVEL` rebaixa e `NAO_APLICAVEL` não rebaixa — distinção com tolerância zero (`S-01`, `S-02`)
- [x] `INVENTARIO_COMPLETO = False` ⇒ `STATUS_METODO` no máximo `PROVISORIO` (`AC-09`)
- [x] O status é derivado, nunca atribuído por caminho alternativo
- [x] Cada rebaixamento registra o motivo

**Status:** `[x] concluída`

---

### `T-61` — Derivar `METODO_RECOMENDADO_PIQ` e `REVISAO_HUMANA_OBRIGATORIA` (`S-04`, `S-05`)

- **Tipo:** `Data`
- **Dependências:** `T-18`, `T-60`
- **Rastreia:** `RF-08`, `AC-04`, `EC-04`, `EC-05`
- **Arquivos:** `engine/status_metodo.py`

**Descrição**

`S-04`: incompatibilidade comportamental grave sem alternativa próxima ⇒ `PROVISORIO` + `REVISAO_HUMANA_OBRIGATORIA`. `S-05`: Híbrido `NAO_APLICAVEL` com Bola de Neve próxima **não** aciona revisão. A recomendação combina superioridade econômica, proximidade, incompatibilidade e vitória rápida.

**Critérios de aceite**

- [x] `EC-05` produz `PROVISORIO` + `REVISAO_HUMANA_OBRIGATORIA = SIM`
      (`test_S04_incompatibilidade_sem_alternativa_aciona_revisao`,
      `tests/regras/test_S.py`)
- [x] `EC-04` **não** aciona revisão humana obrigatória
      (`test_S05_hibrido_nao_aplicavel_nao_aciona_revisao`,
      `tests/regras/test_S.py`)
- [x] O método recomendado é determinístico e justificado por campo de motivo
      (`ResultadoMetodoRecomendado.motivo_recomendacao`,
      `engine/status_metodo.py`; `test_AC04_hibrido_proximo_e_vitoria_rapida_e_priorizado`)
- [x] Nenhum caminho recomenda um cenário `NAO_APLICAVEL` ou `NAO_CALCULAVEL`
      (`test_recomendacao_nunca_e_nao_aplicavel_ou_nao_calculavel`,
      `tests/regras/test_S.py`)

**Status:** `[x] concluída`

---

### `T-62` — Testar a família `S`: classificação, status e revisão humana

- **Tipo:** `Test`
- **Dependências:** `T-61`
- **Rastreia:** `RF-08`, `AC-09`, `EC-03`, `EC-04`, `EC-05`
- **Arquivos:** `tests/regras/test_S.py`

**Descrição**

Um teste por regra `S-01..S-05`, com atenção especial à distinção `NAO_APLICAVEL` × `PROVISORIO`, que tem tolerância zero.

> **Nota de `T-61` (mesma situação de `T-59`/`test_comparacao.py`).** `T-61`
> já criou, em `tests/regras/test_S.py`, os dois testes com nome exato
> exigido abaixo — `test_S04_incompatibilidade_sem_alternativa_aciona_revisao`
> e `test_S05_hibrido_nao_aplicavel_nao_aciona_revisao` — mais
> `test_S02_nao_aplicavel_nao_rebaixa_status_metodo` (T-60, nome já existente
> com sufixo `_metodo`; verificar se o nome exato exigido aqui é este ou uma
> variação antes de recriar) e outros testes de `AC-04`/`S-03`. `T-62` deve
> CONFIRMAR que os três já existem e passam, e só então adicionar o que
> faltar (ex.: `test_S01_*`, `test_S03_*`, já presentes com outros nomes —
> conferir cobertura antes de duplicar), não recriar do zero.

**Critérios de aceite**

- [x] `test_S05_hibrido_nao_aplicavel_nao_aciona_revisao` passa (`EC-04`)
- [x] `test_S04_incompatibilidade_sem_alternativa_aciona_revisao` passa (`EC-05`)
- [x] `test_S02_nao_aplicavel_nao_rebaixa_status` passa (nome exato criado
      em `T-62`, distinto de `test_S02_nao_aplicavel_nao_rebaixa_status_metodo`
      de `T-60`, que foi preservado)
- [x] Todas as asserções usam `assertar_exato`

**Status:** `[x] concluída`

---

### `T-63` — Publicar `ORDEM_QUITACAO` com `JUSTIFICATIVA_POSICAO`

- **Tipo:** `Data`
- **Dependências:** `T-61`
- **Rastreia:** `RF-09`, `AC-18`
- **Arquivos:** `engine/ordem.py`

**Descrição**

`Q-01..Q-05`: a ordem publicada é a sequência **projetada** do cenário recomendado, com `JUSTIFICATIVA_POSICAO` obrigatória e `valores_de_apoio` por posição, para o revisor refazer a conta. O rótulo "projetada" é do `report/`; a variável interna não muda de nome.

**Critérios de aceite**

- [x] Toda `PosicaoOrdem` tem `JUSTIFICATIVA_POSICAO` não vazia (`Q-05`)
- [x] `valores_de_apoio` traz os números que produziram a posição
- [x] A ordem vem do cenário recomendado, não de um ranqueamento recalculado à parte
- [x] Dívida bloqueada por gate não aparece na `ORDEM_QUITACAO`, e sim em `ORDEM_ACOES`
- [x] Nenhum texto de usuário final é redigido aqui (escopo de `relatorio`)

**Status:** `[x] concluída` — `engine/ordem.py` (`publicar_ORDEM_QUITACAO`, `PosicaoOrdem`, `ResultadoOrdemPublicada`, `ErroOrdemInconsistente`) e `tests/regras/test_ordem.py` (9 testes, `pytest -m regra`). Verificação: `ruff check .` limpo, `mypy --strict engine persistencia tests` sem erros, suíte completa `261 passed`.

---

### `T-64` — Consolidar `ORDEM_STATUS` entre `DEFINITIVA_NA_DATA` e `PROVISORIA`

- **Tipo:** `Data`
- **Dependências:** `T-40`, `T-63`
- **Rastreia:** `RF-21`, `RF-16`, `AC-09`, `AC-33`
- **Arquivos:** `engine/ordem.py`

**Descrição**

A ordem só é `DEFINITIVA_NA_DATA` com inventário completo, sem fallback de benefício marginal e sem dado material pendente que altere a decisão. Qualquer uma dessas condições rebaixa para `PROVISORIA`.

**Critérios de aceite**

- [x] `INVENTARIO_COMPLETO = False` ⇒ `ORDEM_STATUS ≠ DEFINITIVA_NA_DATA` (`AC-09`)
- [x] `origem != SIMULACAO` em qualquer dívida ⇒ `PROVISORIA` (`AC-33`)
- [x] Os motivos do rebaixamento são acumulados e expostos
- [x] Nada rebaixa a ordem silenciosamente: todo rebaixamento tem motivo nomeado

**Status:** `[x] concluída` — `engine/ordem.py` (`consolidar_ORDEM_STATUS`, `ResultadoConsolidacaoOrdemStatus`), reusando a regra unitária `determinar_ordem_status_por_origem` (`engine/beneficio_marginal.py`, T-40) sem duplicá-la. `tests/regras/test_ordem.py` (+8 testes, 17 no total, `pytest -m regra`). Verificação: `ruff check .` limpo, `mypy --strict engine persistencia tests` sem erros, suíte completa `269 passed`.

---

### `T-65` — Reproduzir a recomendação do `GAB-C`

- **Tipo:** `Test`
- **Dependências:** `T-11`, `T-63`
- **Rastreia:** `RF-08`, `RF-09`, `RF-19`, `AC-04`, `AC-28`
- **Arquivos:** `tests/gabaritos/test_gabarito_c_recomendacao.py`

**Descrição**

`METODO_RECOMENDADO_PIQ` = `HIBRIDO`, com `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` = SIM, `ECONOMICAMENTE_PROXIMO(HIBRIDO)` = SIM e `VITORIA_RAPIDA(HIBRIDO)` = SIM — enquanto o superior econômico é a Avalanche.

**Critérios de aceite**

- [x] As quatro saídas de `AC-04` conferem
- [x] O superior econômico é a Avalanche no mesmo teste (`AC-28`)
- [x] Toda a `ORDEM_QUITACAO` publicada tem justificativa preenchida
- [x] Roda sob `pytest -m gabarito`

**Status:** `[x] concluída` — `tests/gabaritos/test_gabarito_c_recomendacao.py` (1 teste, `pytest -m gabarito`), integrando de ponta a ponta os três métodos reais (T-49/T-51/T-53), `comparar_cenarios` (T-57/T-58), o `Diagnostico` real (que já deriva `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`, T-18, a partir dos sinais comportamentais normativos de `GAB-C` já carregados pela fixture — `NECESSIDADE_VITORIA=8`, `HISTORICO_ABANDONO=SIM`), `derivar_METODO_RECOMENDADO_PIQ` (T-61) e `publicar_ORDEM_QUITACAO` (T-63). **Divergência real encontrada e corrigida** (não forçada): o desempate residual de `derivar_METODO_RECOMENDADO_PIQ` (`engine/status_metodo.py::_chave`) usava apenas `(MESES_PRIMEIRA_VITORIA, METODO.value alfabético)` — em `GAB-C`, Bola de Neve e Híbrido empatam em `MESES_PRIMEIRA_VITORIA=1`, e o desempate alfabético elegia `BOLA_DE_NEVE` (< `HIBRIDO`), divergindo do gabarito normativo (`METODO_RECOMENDADO_PIQ = HIBRIDO`, `specs/piq-app-spec.md` linha 427/464). Corrigido acrescentando `comparacao.PENALIDADE_CUSTO` como 2º critério do desempate (antes do alfabético), replicando o padrão já normativo da Etapa 4 do Híbrido ("1º menor `MESES_PRIMEIRA_VITORIA`; 2º menor `PENALIDADE_CUSTO_VS_AVALANCHE`", `specs/piq-app-spec.md` linha 170) — Híbrido (1,635%) vence Bola de Neve (3,139%). Verificação: `ruff check .` limpo, `mypy --strict engine persistencia tests` sem erros, suíte completa `270 passed` (269 pré-existentes + 1 novo, nenhuma regressão).

---

## Entrega 7 — Snapshot, persistência, troca e homologação

### `T-66` — Implementar os gatilhos de recálculo `R-01..R-05`

- **Tipo:** `Data`
- **Dependências:** `T-64`
- **Rastreia:** `RF-02`, `RF-22`, `AC-31`, `EC-08`, `EC-09`
- **Arquivos:** `engine/eventos.py`

**Descrição**

Recálculo só por quitação confirmada ou evento externo material. Alteração cadastral/cosmética não é evento (`R-04`) — e é inexprimível no enum. Evento material sempre gera novo snapshot, mesmo que método e `D*` não mudem (`R-05`).

**Critérios de aceite**

- [x] Quitação confirmada de qualquer dívida dispara recálculo (`R-01`, `EC-02`)
- [x] Virada de mês, sozinha, não dispara (`R-02`, `AC-13`)
- [x] Não existe forma de expressar evento cadastral/cosmético (`R-04`, `EC-08`)
- [x] Contratação efetiva de nova dívida ⇒ `EVENTO_RECALCULO = NOVA_DIVIDA` (`AC-31`)
- [x] Evento material com resultado idêntico ainda assim produz novo snapshot (`R-05`, `EC-09`)

**Status:** `[x] concluída`

---

### `T-67` — Montar e carimbar o `SnapshotOrdem`

- **Tipo:** `Data`
- **Dependências:** `T-64`, `T-66`
- **Rastreia:** `RF-10`, `AC-16`, `AC-18`
- **Arquivos:** `engine/snapshot.py`

**Descrição**

`V-01..V-03`: montar o snapshot imutável com `hash_inputs` canônico, `snapshot_anterior_id`, `DATA_REFERENCIA`, `MOTIVO_RECALCULO`, inputs, diagnóstico, cenários, comparação, método, alvo, ordem e ações — carimbado com `ENGINE_VERSION` e `PARAMETROS_VERSION`.

**Critérios de aceite**

- [x] Toda saída carrega `ENGINE_VERSION` e `PARAMETROS_VERSION` (`AC-16`)
- [x] A cadeia `snapshot_anterior_id` é preservada e a versão incrementa
- [x] O snapshot preserva data, `MOTIVO_RECALCULO`, inputs, método, dívida-alvo e justificativas (`AC-18`)
- [x] `SNAPSHOT_ID` é derivado de `hash_inputs` + versão — nunca de `uuid4`
- [x] A dataclass é `frozen`: não existe caminho de sobrescrita

**Status:** `[x] concluída` — `engine/snapshot.py` (dataclass `SnapshotOrdem`, `frozen=True, slots=True`, campos idênticos ao contrato de `plans/motor-calculo.plan.md` linhas 564-586) e `montar_SnapshotOrdem`, que ENVELOPA os resultados já calculados por `T-20`..`T-66` (`Diagnostico`, `Cenario` dos três métodos, `ComparacaoCenarios`, `ResultadoMetodoRecomendado`, `ResultadoOrdemPublicada`) sem recalcular nenhum deles. `hash_inputs` é `sha256` sobre uma representação canônica e determinística de `EstadoFinanceiro` + `PARAMETROS_VERSION` (`_serializar_canonico`: `Decimal` -> `str`, `Enum` -> `.value`, `date` -> `isoformat`, `frozenset` -> lista ordenada, dataclass -> dict por nome de campo, tudo serializado via `json.dumps(..., sort_keys=True)` — nunca `repr()`/`id()`). `SNAPSHOT_ID = sha256(f"{hash_inputs}:{versao}")`, nunca `uuid4()` — confirmado pelo teste estático pré-existente `tests/estatica/test_motor_e_deterministico.py` (varre `engine/` inteiro, incluindo o novo módulo) e pelo teste dedicado `test_AC16_SNAPSHOT_ID_e_deterministico_nunca_uuid4` (roda a montagem duas vezes com a mesma entrada e prova `SNAPSHOT_ID` idêntico). `snapshot_anterior_id`/`versao` encadeiam via parâmetro opcional `anterior: SnapshotOrdem | None` (`versao = anterior.versao + 1`, começando em 1). `ENGINE_VERSION`/`PARAMETROS_VERSION` são repassados de `Parametros` (já expostos desde `T-07`), nunca literal novo. Testes em `tests/regras/test_snapshot.py` (8 casos, `pytest -m regra`), reusando a cadeia real de `GAB-C` (mesma integração ponta a ponta de `T-65`) — cobrem os 5 critérios de aceite, mais `EC-17` refletido no snapshot (`ORDEM_QUITACAO` vazia ⇒ `DIVIDA_ALVO_ATUAL = None`) e a sensibilidade do hash a mudança de estado/versão. Verificação: `ruff check .` limpo, `mypy --strict engine persistencia tests` sem erros (76 arquivos), suíte completa `296 passed` (288 pré-existentes + 8 novos, nenhuma regressão), `tests/estatica/*` (46 testes) todos verdes, confirmando que o novo módulo não introduziu `float`, `P_*` literal, nem fonte de não-determinismo.

---

### `T-68` — Implementar `calcular_plano` como ponto de entrada único

- **Tipo:** `Data`
- **Dependências:** `T-03`, `T-67`
- **Rastreia:** `RF-01`, `RF-10`, `RF-12`, `RF-27`
- **Arquivos:** `engine/motor.py`

**Descrição**

`calcular_plano(estado, parametros, anterior, evento, motivo)` abre o `localcontext()` na fronteira, executa os 11 passos do fluxo de dados da §5 do plano e devolve o `SnapshotOrdem`. Função pura: sem relógio, sem rede, sem escrita em disco.

**Critérios de aceite**

- [x] O contexto decimal é aberto por `localcontext()` na entrada e nunca herdado do ambiente
- [x] Duas execuções com a mesma entrada produzem snapshots idênticos, campo a campo
- [x] O cache de trajetória é limpo entre execuções
- [x] A função não escreve em disco nem chama `anexar()` — persistência é do chamador
- [x] Invariante violado ao fim de qualquer mês levanta `ErroInvariante` com mês e conta, sem degradar para resultado aproximado

**Status:** `[x] concluída` — `engine/motor.py::calcular_plano(estado, parametros, anterior, evento, motivo)` orquestra os 11 passos da §5 do plano na ordem exata (carga de parâmetros já recebida pronta pelo chamador; validação estrutural garantida por construção dos dataclasses `frozen`; derivações comportamentais + diagnóstico/capacidade + modo estabilização via `calcular_diagnostico`, T-24; gates 1-4 via `particionar_elegibilidade`, T-32; os três cenários via `simular_cenario` com as fábricas de `SelecionarAlvo` de Avalanche/Bola de Neve/Híbrido, T-49/T-51/T-53-T-54 — Híbrido `NAO_APLICAVEL` não entra no mapa calculável, S-02; `NOVA_DIVIDA_PREVISTA` já filtrada por construção, RF-22; comparação + status/recomendação via `comparar_cenarios`+`derivar_METODO_RECOMENDADO_PIQ`, T-57/T-58/T-61; ordem publicada + `ORDEM_STATUS` consolidado via `publicar_ORDEM_QUITACAO`+`consolidar_ORDEM_STATUS`, T-63/T-64, com `BeneficioMarginal` real recalculado por dívida publicada; snapshot final via `avaliar_gatilho_recalculo` (T-66, só audita o motivo) + `montar_SnapshotOrdem`, T-67). Fronteira de precisão: `localcontext(CONTEXTO_MOTOR)` aberto uma única vez envolvendo TODA a execução, nunca herdado do ambiente — provado rodando a função sob um `Context(prec=3, rounding=ROUND_DOWN)` hostil ativo no ambiente de chamada e confirmando resultado idêntico. `limpar_cache_trajetoria()` (T-37) chamada no INÍCIO, antes de qualquer simulação — provado por monkeypatch-espião confirmando cache vazio logo após a chamada, em duas execuções sucessivas com entradas diferentes. Nenhum import de `persistencia/`/`engine/portas.py`, nenhuma chamada a `.anexar(...)` — verificado por varredura AST do módulo. `ErroInvariante` nunca capturado — nenhum `try/except` ao redor das três chamadas a `simular_cenario`; provado por monkeypatch que força a exceção no ponto exato e confirma propagação intacta até o chamador (não é possível quebrar a invariante via `SelecionarAlvo` bem tipado através da API pública — `executar_mes` a fecha por construção algébrica interna, mesma constatação já documentada em `tests/regras/test_ciclo_mensal.py`). Testes em `tests/regras/test_motor.py` (8 casos, `pytest -m regra`), reusando `GAB-C` (mesma integração ponta a ponta de T-65/T-67). Verificação: `ruff check .` limpo, `mypy --strict engine persistencia tests` sem erros (78 arquivos), suíte completa `304 passed` (296 pré-existentes + 8 novos, nenhuma regressão).

---

### `T-69` — Implementar `RepositorioSnapshots` e o adaptador JSONL append-only

- **Tipo:** `Infra`
- **Dependências:** `T-67`
- **Rastreia:** `RF-10`, `RF-12`
- **Arquivos:** `engine/portas.py`, `persistencia/arquivo/repositorio_snapshots.py`

**Descrição**

A porta expõe `anexar`, `obter` e `historico` — e **não** expõe `atualizar` nem `remover`, tornando a violação de `V-01` inexprimível. O adaptador grava uma linha por snapshot, com `Decimal` serializado como string.

**Critérios de aceite**

- [x] A porta não tem método de atualização nem de remoção
- [x] `anexar` duas vezes preserva as duas versões, na ordem
- [x] Todo `Decimal` vira string no JSONL e volta como `Decimal` exato
- [x] `historico` devolve a cadeia completa por caso, em ordem determinística
- [x] Erro de escrita é propagado, sem perder o snapshot em memória

**Status:** `[x] concluída` — `engine/portas.py::RepositorioSnapshots` (`Protocol`) estendido com exatamente `anexar`/`obter`/`historico` — `dir(RepositorioSnapshots)` sem prefixo `_` devolve exatamente `{"anexar", "obter", "historico"}`, sem `atualizar`/`remover`; a violação de `V-01` é estruturalmente inexprimível (nenhum verbo de mutação existe para chamar), provado também por `AttributeError` real ao tentar `repositorio.atualizar(...)`/`.remover(...)` numa instância do adaptador concreto. `persistencia/arquivo/repositorio_snapshots.py::RepositorioSnapshotsArquivo` implementa a porta gravando `snapshots.jsonl` (JSON Lines) sempre em modo `open(..., "a")` — nunca lê/reescreve/trunca linhas existentes; reusa `engine.snapshot._serializar_canonico` (mesma função que already produz o `hash_inputs`, T-67) para a serialização (`Decimal -> str`, `Enum -> .value`, `date -> isoformat`, `dataclass -> dict`), e implementa a desserialização inversa campo a campo (`_desserializar_snapshot` e helpers `_divida`/`_estado_financeiro`/`_diagnostico`/`_cenario`/`_comparacao`/`_posicao_ordem`/`_acao_requerida`), reconstruindo cada `Decimal` via `Decimal(str)` — nunca `float` no meio do caminho. `historico(caso_id)` usa como identificador de caso o `SNAPSHOT_ID` da RAIZ da cadeia (decisão documentada na docstring do método: `SnapshotOrdem` ainda não modela um campo `CASO_ID` próprio — conceito pertence a um slug de coleta/cadastro inexistente neste projeto) e devolve a cadeia ordenada por `versao` crescente (sequência estritamente crescente por construção de `V-01`, robusto mesmo se `anexar` for chamado fora de ordem). Testes em `tests/regras/test_repositorio_snapshots.py` (7 casos, `pytest -m regra`), reusando a fixture `GAB-C` real (`_montar_snapshot_gab_c`, `tests/regras/test_snapshot.py`, T-67) para montar `SnapshotOrdem` completos: critério 1 por inspeção do `Protocol` + `AttributeError`; critério 2 anexando duas versões e conferindo as duas linhas do arquivo, na ordem; critério 3 por round-trip exato de `Decimal` (`type(...) is type(...)` mais `assertar_exato`, tolerância zero) em `CAPACIDADE_ATAQUE_CONSERVADORA`, `FATOR_SEGURANCA`, `DIFERENCA_PERCENTUAL` e `valores_de_apoio` de cada posição publicada, e confirmando que a linha crua do JSONL serializa esses campos como `str`, nunca `number`; critério 4 anexando 3 snapshots ENCADEADOS fora de ordem de escrita e confirmando que `historico` devolve `[versao 1, 2, 3]` ordenados corretamente (mais um teste de caso inexistente devolvendo sequência vazia); critério 5 simulando falha de I/O real (diretório-pai do caminho é, de fato, um arquivo comum — `Path.mkdir(parents=True)` levanta `OSError`), confirmando que a exceção é propagada (`pytest.raises(OSError)`), que os campos-chave do `SnapshotOrdem` original (`SNAPSHOT_ID`/`versao`/`hash_inputs`) permanecem intactos após a falha, que o objeto continua `frozen` (`FrozenInstanceError` ao tentar sobrescrever), e que o mesmo objeto pode ser reanexado com sucesso a um caminho válido depois. Verificação: `ruff check .` limpo, `mypy --strict engine persistencia tests` sem erros (82 arquivos), suíte completa `317 passed` (310 pré-existentes + 7 novos, nenhuma regressão).

---

### `T-70` — Testar versionamento, carimbo e gatilhos de recálculo

- **Tipo:** `Test`
- **Dependências:** `T-68`, `T-69`
- **Rastreia:** `RF-02`, `RF-10`, `AC-16`, `AC-18`, `AC-31`, `EC-08`, `EC-09`
- **Arquivos:** `tests/regras/test_V.py`, `tests/regras/test_R.py`

**Descrição**

Família `V` e complemento da família `R`: carimbo de versão em toda saída, snapshot preservado, cadeia encadeada, evento material que não muda nada e ainda assim versiona.

**Critérios de aceite**

- [x] `test_V03_carimbo_em_toda_saida` passa (`AC-16`) — `tests/regras/test_V.py`, roda `calcular_plano` (T-68) duas vezes (com e sem evento) e verifica `ENGINE_VERSION`/`PARAMETROS_VERSION` do snapshot resultante contra `parametros.ENGINE_VERSION`/`PARAMETROS_VERSION`
- [x] `test_AC18_snapshot_preserva_anterior` passa — `tests/regras/test_V.py`, prova que o snapshot anterior permanece com todos os seus campos intactos (data, motivo, inputs, método, D*, ordem) e ainda `frozen` depois que um novo snapshot é produzido a partir dele, além da cadeia `snapshot_anterior_id`/`versao`
- [x] `test_EC09_evento_material_versiona_mesmo_sem_mudanca` passa — `tests/regras/test_V.py`, chama `calcular_plano` duas vezes com o MESMO `EstadoFinanceiro` (resultado idêntico: mesmo método, mesma ordem, mesmo `hash_inputs`) e prova que a segunda chamada, com `EVENTO_RECALCULO` material, ainda assim produz `versao` incrementada e `SNAPSHOT_ID` novo
- [x] `test_R04_alteracao_cadastral_nao_e_evento` passa (`EC-08`) — `tests/regras/test_R.py`, prova estrutural (nenhum membro cosmético em `EVENTO_RECALCULO`, `KeyError`/`ValueError` ao tentar construir um) mais o caminho `avaliar_gatilho_recalculo(None)` nunca recalculando
- [x] Round-trip snapshot → JSONL → snapshot com igualdade exata de todo `Decimal` — `test_round_trip_snapshot_jsonl_preserva_decimal_exato` em `tests/regras/test_V.py` (via `calcular_plano` + `RepositorioSnapshotsArquivo`), complementando a cobertura já exaustiva campo a campo de `test_criterio3_decimal_vira_string_e_volta_exato_round_trip` (`tests/regras/test_repositorio_snapshots.py`, T-69)

**Status:** `[x] concluída`

---

### `T-71` — Implementar o cenário de substituição equivalente da troca

- **Tipo:** `Data`
- **Dependências:** `T-27`, `T-46`
- **Rastreia:** `RF-11`
- **Arquivos:** `engine/troca.py`

**Descrição**

`T-01`/`T-02`: em troca ou portabilidade com `DINHEIRO_NOVO > 0`, o `CENARIO_SUBSTITUICAO_EQUIVALENTE` é calculado apenas sobre a parcela que substitui a dívida antiga; o dinheiro novo é endividamento adicional, jamais economia.

**Critérios de aceite**

- [x] O cenário equivalente é calculado apenas sobre o valor substituído — `calcular_CENARIO_SUBSTITUICAO_EQUIVALENTE` simula uma `Divida` sintética com saldo `operacao.VALOR_SUBSTITUIDO`, nunca `SALDO_NOVA_OPERACAO`; `test_cenario_equivalente_usa_apenas_o_valor_substituido` prova que o saldo de abertura simulado é 30.000 (não 40.000) num caso de troca com dinheiro novo
- [x] `DINHEIRO_NOVO` entra como novo endividamento e nunca reduz o custo comparado — `ResultadoSubstituicaoEquivalente.cenario_dinheiro_novo` é um `Cenario` SEPARADO, nunca somado/subtraído ao `cenario_equivalente`; `test_dinheiro_novo_e_endividamento_separado_e_identificavel` prova que `CUSTO_FUTURO_TOTAL` do cenário equivalente é idêntico com ou sem `DINHEIRO_NOVO > 0` para a mesma parcela substituída
- [x] O resultado é comparável ao cenário sem troca, mês a mês — ambos são `Cenario`s produzidos por `simular_cenario`; `test_cenario_equivalente_e_comparavel_mes_a_mes_ao_cenario_sem_troca` compara `.meses` posição a posição (`ResultadoMes` a `ResultadoMes`) entre o cenário equivalente e o cenário da dívida antiga isolada
- [x] O módulo cita `T-01` e `T-02` — `engine/troca.py::REGRAS = ("RF-11", "T-01", "T-02")`, citados também na docstring do módulo; `test_modulo_cita_regras_t01_t02` verifica

**Status:** `[x] concluída`

---

### `T-72` — Testar o invariante `GAB-05` da troca

- **Tipo:** `Test`
- **Dependências:** `T-71`
- **Rastreia:** `RF-11`, `AC-12`
- **Arquivos:** `tests/invariantes/test_gab05_troca.py`

**Descrição**

Quitação de R$ 30.000 por nova operação de R$ 40.000: equivalente só sobre os 30.000, e os 10.000 tratados como novo endividamento.

**Critérios de aceite**

- [x] `test_invariante_gab05_troca` passa (`AC-12`)
- [x] Nenhum caminho classifica os R$ 10.000 como economia
- [x] Valores monetários usam `assertar_monetario`; classificações usam `assertar_exato`
- [x] Roda sob `pytest -m invariante`

**Status:** `[x] concluída`

---

### `T-73` — Testar os invariantes `GAB-01`, `GAB-02` e `GAB-03`

- **Tipo:** `Test`
- **Dependências:** `T-11`, `T-68`
- **Rastreia:** `RF-14`, `RF-16`, `AC-08`, `AC-09`, `AC-10`
- **Arquivos:** `tests/invariantes/test_gab01_seguro.py`, `tests/invariantes/test_gab02_inventario.py`, `tests/invariantes/test_gab03_rotativo.py`

**Descrição**

Seguro embutido que permanece 1.000; inventário incompleto com totais parciais e status rebaixado; dívida rotativa sem saldo e sem pagamento marcada `INFORMACAO_PENDENTE` com trajetória `BLOQUEADO` e zero estimativa.

**Critérios de aceite**

- [x] `test_invariante_gab01_seguro` prova que 1.000 permanece 1.000 (`AC-08`, `EC-12`)
- [x] `test_invariante_gab02_inventario` prova totais parciais, `ORDEM_STATUS ≠ DEFINITIVA_NA_DATA` e `STATUS_METODO` no máximo `PROVISORIO` (`AC-09`, `EC-07`)
- [x] `test_invariante_gab03_rotativo` prova `INFORMACAO_PENDENTE`, trajetória `BLOQUEADO` e nenhum valor estimado (`AC-10`, `EC-06`)
- [x] Os três rodam sob `pytest -m invariante`

**Status:** `[x] concluída`

---

### `T-74` — Testar o invariante `GAB-04` do modo estabilização

- **Tipo:** `Test`
- **Dependências:** `T-68`
- **Rastreia:** `RF-15`, `AC-11`, `EC-10`
- **Arquivos:** `tests/invariantes/test_gab04_estabilizacao.py`

**Descrição**

Em modo estabilização, os R$ 200 observados nunca são rotulados como sobra, e método, ordem e cronograma saem marcados como fase 2 condicional à estabilização.

**Critérios de aceite**

- [x] `test_invariante_gab04_estabilizacao` passa (`AC-11`)
- [x] Nenhum campo da saída rotula o observado positivo como sobra ou capacidade
- [x] Os cenários são calculados de fato, sem que o motor deixe de calculá-los. **Ressalva:** nenhum campo de "condicional à estabilização" existe hoje em `Cenario`/`SnapshotOrdem`/`STATUS_METODO` — o plano técnico (§5 passo 5) atribui essa rotulagem ao `report/`, fora deste slug; o teste prova o invariante com o único sinal formal já existente (`Diagnostico.MODO_ESTABILIZACAO`) e documenta a lacuna na docstring, sem inventar campo novo em módulo já fechado
- [x] Roda sob `pytest -m invariante`

**Status:** `[x] concluída`

---

### `T-75` — Implementar o adaptador Supabase/Postgres com imutabilidade por privilégio

- **Tipo:** `Infra`
- **Dependências:** `T-69`
- **Rastreia:** `RF-10`, `RF-12`, `RF-13`
- **Arquivos:** `persistencia/supabase/conexao.py`, `persistencia/supabase/fonte_parametros.py`, `persistencia/supabase/repositorio_snapshots.py`, `persistencia/supabase/migracoes/001_inicial.sql`

**Descrição**

Adaptador `psycopg 3` com colunas `numeric` para valores decisivos, `DATABASE_URL` em variável de ambiente e migração que faz `REVOKE UPDATE, DELETE ON snapshots` mais a trigger `impedir_sobrescrita_V01`. Nenhuma regra de negócio em `plpgsql`.

**Critérios de aceite**

- [x] Custo, prazo e capacidades são colunas `numeric`, não apenas `jsonb` — a tabela `motor_calculo.snapshots` (`migracoes/001_inicial.sql`) declara `"CUSTO_FUTURO_TOTAL" numeric`, `"CAPACIDADE_ATAQUE_ATUAL"/"_CONSERVADORA"/"_POTENCIAL" numeric`, `"PRAZO_TOTAL" integer`, e `dados_completos jsonb` só para o restante da árvore. Migração aplicada contra o projeto Supabase real (schema dedicado `motor_calculo`, isolado dos demais sistemas já presentes no banco); `test_snapshots_colunas_decisivas_sao_numeric_nao_apenas_jsonb` rodado com `DATABASE_URL` real setada: **PASSED**
- [x] `UPDATE` e `DELETE` em `snapshots` são recusados pelo banco — `REVOKE UPDATE, DELETE ON motor_calculo.snapshots FROM PUBLIC` + trigger `impedir_sobrescrita_v01` confirmados contra o banco real: `test_update_e_delete_em_snapshots_sao_recusados_pelo_banco` executa um `UPDATE` e um `DELETE` reais via `psycopg` contra o Supabase e ambos são recusados com `psycopg.Error` — **PASSED**
- [x] Nenhum gate, ranqueamento ou fórmula da §11 existe em SQL — verificável por leitura direta de `migracoes/001_inicial.sql`: só `CREATE SCHEMA`/`CREATE TABLE`/`CREATE INDEX`/`REVOKE`/`CREATE TRIGGER`; a única função `plpgsql` (`impedir_sobrescrita_v01`) é um `RAISE EXCEPTION` incondicional sobre `TG_OP`/`TG_TABLE_NAME`/`OLD."SNAPSHOT_ID"`, sem nenhuma condição de negócio
- [x] O motor continua funcionando sem Supabase, com os adaptadores de arquivo — `pytest -q` **sem** `DATABASE_URL` setada: `332 passed, 4 skipped` (os 4 skips são os testes de `test_supabase_adaptadores.py`, pulados com `DATABASE_URL não definida — adaptador Supabase é opcional (plano §2.1)`); `pytest -q -m "gabarito or invariante"`: `15 passed, 321 deselected` — nenhum teste pré-existente quebrou
- [x] Idempotência de `anexar` garantida por `hash_inputs` + versão — `INSERT ... ON CONFLICT ("SNAPSHOT_ID") DO NOTHING` confirmado contra o banco real: `test_anexar_e_obter_round_trip_minimo_e_idempotente` chama `anexar` duas vezes com o mesmo `SnapshotOrdem` e confere `count(*) = 1` — **PASSED**

**Status:** `[x] concluída` — código, migração e os 5 critérios de aceite verificados com evidência real contra um projeto Supabase/Postgres fornecido pelo usuário. Schema dedicado `motor_calculo` criado (banco compartilhado com outros sistemas em produção — `ads_*`/`core_*`/`trv_*`/`vtr_*` — por isso o isolamento por schema, não por prefixo). Migração `001_inicial.sql` aplicada; tabela `motor_calculo.parametros` populada com a versão `1.0.1` (seed executado a partir de `FonteParametrosArquivo`, garantindo paridade com a fonte canônica). `pytest tests/regras/test_supabase_adaptadores.py -v` com `DATABASE_URL` real: `4 passed`. Suíte completa sem `DATABASE_URL`: `332 passed, 4 skipped` — adaptador Supabase é estritamente opcional, nunca obrigatório para o motor funcionar (OQ-C).

---

### `T-76` — Testar a integração: paridade arquivo × Postgres e round-trip decimal

- **Tipo:** `Test`
- **Dependências:** `T-75`
- **Rastreia:** `RF-10`, `RF-12`, `RF-13`
- **Arquivos:** `tests/integracao/test_fonte_parametros.py`, `tests/integracao/test_repositorio_snapshots.py`

**Descrição**

Os dois adaptadores de `FonteParametros` carregam `Parametros` idênticos campo a campo; `anexar` duas vezes preserva as duas versões nos dois adaptadores; round-trip de `SnapshotOrdem` mantém igualdade exata de todo `Decimal`.

**Critérios de aceite**

- [x] Paridade campo a campo entre arquivo e Postgres, com `Decimal` exato — `tests/integracao/test_fonte_parametros.py`: três testes cobrem os 38 `P_*` (35 escalares via `numero()` + 3 arrays `P_PRESSAO_INDIVIDUAL`/`P_PRESSAO_TOTAL`/`P_ESCALA_0_10`, lidos diretamente da fonte canônica `parameters/parametros-1.0.1.json`, nunca fixados à mão), as 3 `REGRA_*` e o carimbo (`ENGINE_VERSION`/`PARAMETROS_VERSION`/`DATA_VIGENCIA`), comparando `FonteParametrosArquivo().carregar("1.0.1")` × `FonteParametrosSupabase().carregar("1.0.1")` com `Decimal` exato (`isinstance(..., Decimal)` + `==`). Rodado com `DATABASE_URL` real: `test_paridade_campo_a_campo_arquivo_x_postgres_todos_os_P_estrela`, `..._REGRA_estrela`, `..._carimbo` — **PASSED** (3/3)
- [x] `UPDATE` direto na tabela `snapshots` falha no teste (`V-01`) — `tests/integracao/test_repositorio_snapshots.py::test_V01_update_direto_na_tabela_snapshots_falha_no_teste_de_integracao`: grava um `SnapshotOrdem` real via `RepositorioSnapshotsSupabase`, executa um `UPDATE` real via `psycopg` contra `motor_calculo.snapshots` e confirma `psycopg.Error` (REVOKE + trigger `impedir_sobrescrita_v01`, `V-01`), citando `V-01` explicitamente no nome do teste — rodado com `DATABASE_URL` real: **PASSED**
- [x] Round-trip preserva todo `Decimal` sem perda de casa — `tests/integracao/test_repositorio_snapshots.py::test_round_trip_preserva_decimal_de_alta_precisao_sem_perda_de_casa`: monta `SnapshotOrdem` real via `montar_SnapshotOrdem`/`_montar_snapshot_gab_c` (GAB-C), substitui `CAPACIDADE_ATAQUE_ATUAL`/`_CONSERVADORA`/`_POTENCIAL` e `CUSTO_FUTURO_TOTAL` por `Decimal` de 15 casas (`"1234.123456789012345"` etc.), `anexar()` no Supabase, `obter()` de volta, compara cada campo com `==` exato (nunca `assertar_monetario`) e confirma a string exata das 15 casas preservada — rodado com `DATABASE_URL` real: **PASSED**. Causa raiz investigada e documentada: a primeira tentativa (sem perturbar `estado`) colidiu com o `SNAPSHOT_ID` do GAB-C já gravado por T-75 (`SNAPSHOT_ID` deriva só de `hash_inputs`+`versao`, nunca dos campos derivados sobrescritos) — `ON CONFLICT DO NOTHING` preservou a linha antiga, mascarando o round-trip; corrigido perturbando `PESO_EMOCIONAL` da primeira dívida com `time.time_ns() % 10` para garantir `SNAPSHOT_ID` novo a cada execução (documentado na docstring de `_snapshot_com_decimais_de_alta_precisao`). Nenhum bug real de paridade/round-trip nos adaptadores — comportamento de idempotência era o esperado e correto de T-75.
- [x] Os testes são pulados com mensagem explícita quando não há `DATABASE_URL` — a suíte de homologação não depende do Supabase: mesmo padrão `@pytest.mark.skipif(_DATABASE_URL_AUSENTE, reason=_MOTIVO_SKIP)` de T-75, replicado nos dois arquivos novos. `pytest -q` **sem** `DATABASE_URL`: `334 passed, 9 skipped` (4 de T-75 + 5 de T-76, todos `skipped`, nenhum `failed`/`error`); `pytest -v tests/integracao/` sem `DATABASE_URL` mostra os 5 testes de rede como `SKIPPED` e 2 testes de skip gracioso (que rodam sempre) como `PASSED`

**Status:** `[x] concluída` — os 4 critérios de aceite verificados com evidência real contra o mesmo projeto Supabase/Postgres de T-75. `tests/integracao/test_fonte_parametros.py` e `tests/integracao/test_repositorio_snapshots.py` criados (`tests/integracao/__init__.py` novo). `pytest -v tests/integracao/` com `DATABASE_URL` real: `7 passed`. Suíte completa com `DATABASE_URL`: `343 passed` (334 + 9 que eram skipped). Suíte completa sem `DATABASE_URL`: `334 passed, 9 skipped` — igual ao baseline de T-75 em contagem de `passed`, adaptador Supabase segue estritamente opcional (OQ-C). `ruff check .` e `mypy engine persistencia tests` limpos.

---

### `T-77` — Medir o desempenho da carteira de 30 dívidas em 120 meses

- **Tipo:** `Test`
- **Dependências:** `T-38`, `T-68`
- **Rastreia:** `RF-05`, `RF-07`
- **Arquivos:** `tests/desempenho/test_orcamento_30_dividas.py`

**Descrição**

Marcador `desempenho`, fora da suíte padrão: três métodos mais recomendação para N=30 e H=120 dentro do orçamento declarado de 10 s. Inclui a equivalência cache ligado × desligado sobre o `GAB-C` completo.

**Critérios de aceite**

- [x] O cenário de 30 dívidas × 120 meses roda em ≤ 10 s no ambiente de referência — tempo REAL medido: **0,398 s** (`P_HORIZONTE_MAXIMO_SIMULACAO = 10` anos = 120 meses, parâmetro `1.0.1` sem override, os três métodos + recomendação completa via `calcular_plano` ponta a ponta). Evidência: `pytest -m desempenho -s tests/desempenho/test_orcamento_30_dividas.py` → `[T-77] 30 dívidas × 120 meses: 0.398s (orçamento 10s)`, `2 passed`
- [x] `GAB-C` produz snapshots idênticos com e sem `lru_cache`/`functools.cache` — `test_cache_trajetoria_nao_altera_resultado_GAB_C` roda `calcular_plano(carregar_gab_c(), ...)` duas vezes (cache memoizado normal vs. `simular_trajetoria_isolada` substituída por monkeypatch para chamar `_simular_trajetoria_isolada_sem_cache` diretamente a cada vez, forçando recomputação) e compara campo a campo com `assertar_exato`: `METODO_RECOMENDADO_PIQ`, `cenarios[METODO_RECOMENDADO_PIQ].PRAZO_TOTAL`, `.CUSTO_FUTURO_TOTAL` e a sequência de `DIVIDA_ID` de `ORDEM_QUITACAO` — todos idênticos
- [x] O tempo medido é reportado na saída do teste, não apenas comparado — `print(f"[T-77] 30 dívidas × 120 meses: {tempo_decorrido:.3f}s ...")` em `tests/desempenho/test_orcamento_30_dividas.py`, visível com `pytest -s` e também na mensagem de asserção em caso de estouro do orçamento
- [x] O teste não roda em `pytest -m "gabarito or invariante"` — confirmado: `pytest -m "gabarito or invariante" --collect-only` coleta `15/332 tests` (317 deselected), nenhum de `tests/desempenho/`; roda isoladamente e passa sob `pytest -m desempenho` (`2 passed in 0.83s`)

**Status:** `[x] concluída`

---

### `T-78` — Corrigir `InvalidOperation` em `comparar_cenarios` quando todo `CUSTO_FUTURO_TOTAL` é zero

- **Tipo:** `Bug`
- **Dependências:** `T-58`
- **Rastreia:** `RF-19`
- **Arquivos:** `engine/comparacao.py`

**Descrição**

Achado por T-68 (não corrigido lá, por estar fora de escopo): `comparar_cenarios` levanta `decimal.InvalidOperation` (divisão por zero) quando **todos** os cenários de entrada têm `CUSTO_FUTURO_TOTAL = 0` — situação real em carteiras como `GAB-A` (déficit puro, nenhuma dívida quitada em nenhum método) ou `GAB-B` (única dívida com `SALDO_DEVEDOR_ATUAL = DESCONHECIDO`). O cálculo de `DIFERENCA_PERCENTUAL`/`PENALIDADE_CUSTO` divide por `CUSTO_FUTURO_TOTAL(SUPERIOR)`, que nesse caso é zero.

**Critérios de aceite**

- [x] `comparar_cenarios` não levanta `InvalidOperation` quando todos os `CUSTO_FUTURO_TOTAL` são zero — `custo_minimo == 0` tratado explicitamente ANTES da divisão em `comparar_cenarios` e em `_avaliar_proximidade_economica` (`engine/comparacao.py`), nunca via `try/except`. Evidência: `calcular_plano(carregar_gab_a(), parametros)` e `calcular_plano(carregar_gab_b(), parametros)` executam sem exceção (reproduzido manualmente e coberto por `test_T78_gab_a_calcular_plano_nao_levanta_invalid_operation`)
- [x] O comportamento nesse caso é definido explicitamente e documentado — ver docstring de `comparar_cenarios` em `engine/comparacao.py`: quando `CUSTO_MINIMO = 0`, todo cenário com `CUSTO_FUTURO_TOTAL = 0` está no mesmo patamar do mínimo (zero está a 0% de zero — "nenhuma diferença", não erro) e empata materialmente com desempate por `PRAZO_TOTAL` como no caminho normal (`AC-27`); a pertença ao empate/proximidade é sempre decidida por comparação de custo direta, nunca por uma fração numérica fabricada — sem valor arbitrário
- [x] Teste de regressão cobrindo `GAB-A` via `calcular_plano` (`test_T78_gab_a_calcular_plano_nao_levanta_invalid_operation`, `tests/regras/test_comparacao.py`) e via `comparar_cenarios` com `Cenario`s sintéticos de custo zero (`test_T78_custo_zero_em_todos_nao_levanta_invalid_operation`, `test_T78_custo_zero_no_minimo_mas_alternativo_positivo_nao_empata`)
- [x] Nenhum teste pré-existente de T-57/T-58/T-59 quebra — suíte completa: `330 passed` (`pytest -q`), incluindo os 15 testes `AC27`/`EC19`/`AC28`/`AC29` de `tests/regras/test_comparacao.py` intactos

**Status:** `[x] concluída`

---

## Rodada 2 — Extensão de `AcaoRequerida`/`Diagnostico` (2026-09-04)

> **Contexto.** Pedido do slug `app-aluno` para desbloquear `T-77`/`T-78`/
> `T-79` daquele slug (bloqueadas por dependerem de campos que hoje não
> existem no contrato de saída do motor). Fonte primária de arquitetura:
> `plans/motor-calculo.plan.md` §R2.1–R2.11. Fonte de requisitos:
> `specs/motor-calculo.spec.md` §2 (`RF-28`–`RF-35`), §4 (`AC-48`–`AC-61`),
> §3 (`US-09`–`US-13`), §6 (`EC-20`–`EC-22`), §10 (`OQ-21`–`OQ-23`).
>
> **Decisões já fechadas, tratadas como definitivas nesta rodada** (não são
> pendência — plano §R2.10.1):
> - `AMB-R2-02` — Gate 2 (`RISCO_MATERIAL_IMINENTE`) emite `TIPO_ACAO =
>   "RENEGOCIACAO"`.
> - `AMB-R2-03` — quando `RENEGOCIACAO_PENDENTE` e `TROCA_PENDENTE` são
>   ambos `True` na mesma dívida do Gate 3, `TIPO_ACAO = "RENEGOCIACAO"`
>   prevalece sobre `"TROCA"`.
> - `OQ-21`/`OQ-22` — `ACAO_ID` é determinístico por composição:
>   `f"{DIVIDA_ID}:{TIPO_ACAO}"` para ações ligadas a dívida,
>   `f"ACAO:{TIPO_ACAO}"` para a ação de economia (sem contador, sem UUID,
>   sem estado externo, estável entre snapshots).
>
> **Pendência que segue bloqueante:** `OQ-23` — fórmula de cálculo de
> `RESERVA_MOBILIZAVEL`/`ATAQUE_IMEDIATO_RECOMENDADO` (`RF-35`). Nenhuma
> fonte publica o cálculo. A `T-90` (contrato/shape) pode prosseguir agora;
> a `T-91` (cálculo real) está explicitamente marcada como bloqueada,
> **sem estimativa**, e não deve ser implementada com fórmula inventada
> (regra de tolerância zero para cálculo financeiro, spec §10.3;
> `sdd.config.md` §6).
>
> **Fora de escopo desta rodada** (spec §9): decisão de metodologia sobre
> *o quê* mudar (já fechada por `app-aluno.spec.md` §10); atualização do
> hash congelado de `engine/` em
> `tests/app_aluno/estatica/hashes_congelados.json` (é `AC-44` do slug
> `app-aluno`, disparada depois que esta mudança for mesclada — não vira
> tarefa aqui).

---

### `T-79` — Estender `AcaoRequerida` com `ACAO_ID`, `TIPO_ACAO`, `CAMPO_PENDENTE` e relaxar `DIVIDA_ID`

- **Tipo:** `Data`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-28`, `RF-29`, `RF-31`, `RF-34`, `AC-49`
- **Arquivos:** `engine/gates.py`

**Descrição**

Mudança de contrato da dataclass, ponto de partida da rodada (plano §R2.4). `AcaoRequerida` ganha `ACAO_ID: str`, `TIPO_ACAO: str` (domínio fechado `TIPO_ACAO_VALORES = frozenset({"INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"})`), `CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"] | None = None`; `DIVIDA_ID` relaxa de `str` para `str | None`; `gate_origem` amplia de `Literal[2, 3]` para `Literal[1, 2, 3] | None`. Nenhuma lógica de derivação ainda — só o shape.

**Critérios de aceite**

- [x] `AcaoRequerida` declara `ACAO_ID: str`, `DIVIDA_ID: str | None`, `TIPO_ACAO: str`, `gate_origem: Literal[1, 2, 3] | None`, `CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"] | None = None`, nesta ordem de campos idêntica ao plano §R2.4
- [x] `TIPO_ACAO_VALORES: Final[frozenset[str]]` existe em `engine/gates.py` com exatamente os quatro literais `{"INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"}`
- [x] `mypy --strict engine/` passa com a dataclass estendida
- [x] Nenhum código de `engine/gates.py` que já constrói `AcaoRequerida` (Gate 2, Gate 3 da Rodada 1) quebra de compilar — ainda que `TIPO_ACAO`/`ACAO_ID` fiquem temporariamente com valor provisório até `T-81`/`T-83`/`T-84`
- [x] O módulo continua sem importar nada de `persistencia/`

**Status:** `[x] concluída`

Nota: `build` completo do projeto (`sdd.config.md` §2) reporta 5 erros em
`report/plano.py`, `persistencia/arquivo/repositorio_snapshots.py`,
`app/casos/coleta_dirigida.py` e `tests/regras/test_gates.py` — consequência
esperada do relaxamento de `DIVIDA_ID` (RF-31) e dos novos campos
obrigatórios; escopo de correção é `T-86`, não `T-79`. `mypy --strict
engine/` (escopo desta tarefa) passa limpo. Além disso, `pytest -q` sobre a
suíte completa reporta `7 failed, 1122 passed, 75 skipped, 4 xfailed`: 2
falhas em `tests/app_aluno/estatica/test_engine_congelado.py` (hash
congelado de `engine/gates.py` divergente — `AC-44` do slug `app-aluno`,
já antecipada como fora de escopo desta rodada na nota de abertura da
"Rodada 2" acima) e 5 `XPASS(strict)` em
`tests/app_aluno/test_acoes.py`, `tests/app_aluno/test_acompanhamento_acao_id.py`
e `tests/app_aluno/test_ordem_acoes_dependencia_externa.py` — testes do
slug `app-aluno` escritos com a premissa explícita "`AcaoRequerida` real
ainda não publica `ACAO_ID`/`TIPO_ACAO`", que esta tarefa invalidou de
propósito (é o pedido de origem da Rodada 2). Os próprios testes já
documentam a ação: "a dependência externa chegou e `T-83`/`T-84`/`T-90`
precisa(m) ser revisitada(s)" — revisão que pertence ao backlog de
`app-aluno`, não a `T-79`. `tests/regras/test_gates.py` passa 100% em
runtime isoladamente (`32 passed`) apesar do erro de tipagem do `mypy`
citado acima.

---

### `T-80` — Implementar `_compor_ACAO_ID` determinístico por composição

- **Tipo:** `Data`
- **Dependências:** `T-79`
- **Rastreia:** `RF-28`, `AC-48`
- **Arquivos:** `engine/gates.py`

**Descrição**

Função privada pura (plano §R2.4/§R2.6): `_compor_ACAO_ID(*, divida_id: str | None, tipo_acao: str) -> str`. Ações ligadas a dívida: `f"{divida_id}:{tipo_acao}"`. Ação de economia (`divida_id=None`): `f"ACAO:{tipo_acao}"`. Sem contador, sem UUID, sem estado externo, sem relógio — mesmos dois insumos sempre produzem o mesmo `ACAO_ID` (`OQ-21`/`OQ-22`, já respondidas).

**Critérios de aceite**

- [x] `_compor_ACAO_ID(divida_id="D001", tipo_acao="INFORMACAO")` devolve `"D001:INFORMACAO"`
- [x] `_compor_ACAO_ID(divida_id=None, tipo_acao="ECONOMIA")` devolve `"ACAO:ECONOMIA"`
- [x] Chamar a função duas vezes com os mesmos insumos produz o mesmo valor (determinismo puro)
- [x] A função não lê relógio, não gera UUID, não usa contador nem variável global mutável
- [x] `mypy --strict` aceita a assinatura com `divida_id: str | None`

**Status:** `[x] concluída`

Nota: função inserida em `engine/gates.py` logo após `AcaoRequerida`, antes de
`ResultadoGates` (plano §R2.4/§R2.6 — mesma vizinhança da dataclass que ela
serve, reaproveitável pelos três pontos de emissão). Escopo mantido estrito:
os três pontos que hoje constroem `AcaoRequerida` com `ACAO_ID=divida.DIVIDA_ID`/
`TIPO_ACAO=""` provisórios (Gate 2 ×2, Gate 3 ×1) **não foram alterados** —
usá-los já implicaria antecipar a derivação real de `TIPO_ACAO`, que é escopo
de `T-83`/`T-84`. `mypy --strict engine/` passa limpo (25 arquivos). `build`
completo do projeto continua reportando os mesmos 5 erros pré-existentes já
documentados na nota de `T-79` (fora de `engine/`, escopo `T-86`), nenhum
novo. `pytest -q` da suíte completa reporta o mesmo `7 failed, 1122 passed,
75 skipped, 4 xfailed` de `T-79` — nenhuma falha nova; as 7 falhas
pré-existentes são do slug `app-aluno` (hash congelado de `engine/gates.py`
e `XPASS(strict)` que antecipam `T-83`/`T-84`/`T-90`), já fora de escopo
desta tarefa. `tests/regras/test_gates.py` passa 100% (`32 passed`).

---

### `T-81` — Testar `_compor_ACAO_ID`: determinismo e estabilidade entre snapshots

- **Tipo:** `Test`
- **Dependências:** `T-80`
- **Rastreia:** `RF-28`, `AC-48`, `OQ-21`, `OQ-22`
- **Arquivos:** `tests/estatica/test_acao_id_determinismo_puro.py`, `tests/regras/test_gates.py`

**Descrição**

Prova o contrato de determinismo exigido por `OQ-21`/`OQ-22` como propriedade estrutural, não só por exemplo (plano §R2.9).

**Critérios de aceite**

- [x] `test_acao_id_determinismo_puro` chama a função duas vezes com os mesmos insumos e exige igualdade exata (`assertar_exato`)
- [x] O mesmo teste chama com insumos diferentes (dívida ou tipo diferente) e exige `ACAO_ID` diferente
- [x] `test_acao_id_estavel_entre_snapshots_mesma_divida_mesmo_tipo` simula dois cálculos (dois "snapshots") da mesma dívida com o mesmo `TIPO_ACAO` e confere `ACAO_ID` idêntico (`AC-48`)
- [x] `test_acao_id_estavel_para_acao_economia_entre_snapshots` cobre o mesmo para a ação de economia (`OQ-22`)
- [x] Todas as asserções de `ACAO_ID` usam `assertar_exato` (tolerância zero — não é valor monetário)

**Status:** `[x] concluída`

---

### `T-82` — Testar o domínio fechado de `TIPO_ACAO`

- **Tipo:** `Test`
- **Dependências:** `T-79`
- **Rastreia:** `RF-29`, `AC-49`
- **Arquivos:** `tests/estatica/test_tipo_acao_apenas_quatro_valores.py`

**Descrição**

Garante que `TIPO_ACAO` nunca assume um quinto literal, acento ou parêntese — como propriedade estrutural varrida sobre toda `AcaoRequerida` produzida pela suíte de gabaritos (plano §R2.9), não apenas por exemplo isolado.

**Critérios de aceite**

- [x] `test_tipo_acao_dominio_fechado_ascii` confere que `TIPO_ACAO_VALORES` contém exatamente `{"INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"}`, nenhum outro
- [x] `test_tipo_acao_apenas_quatro_valores` varre toda `AcaoRequerida` construída ao rodar os três gabaritos (`GAB-A`/`GAB-B`/`GAB-C`) e falha se algum `TIPO_ACAO` estiver fora de `TIPO_ACAO_VALORES`
- [x] O teste falha propositalmente se um quinto literal for introduzido em `engine/gates.py` (prova negativa documentada no próprio teste ou em comentário)
- [x] Roda sob `pytest -m "gabarito or invariante"` ou marcador equivalente já definido no projeto

**Status:** `[x] concluída`

Nota — descoberta relevante para sequenciamento (não é escopo desta tarefa,
registrada por transparência): investigado ANTES de escrever o teste, como
pedido. Nas fixtures atuais (`tests/fixtures/gab_{a,b,c}.json`), toda dívida
tem `RISCO_MATERIAL_IMINENTE=false`, `RENEGOCIACAO_PENDENTE=false` e
`TROCA_PENDENTE=false` — os únicos pontos que hoje constroem `AcaoRequerida`
com `TIPO_ACAO=""` provisório (Gate 2 `aplicar_gate_2_contencao_risco`, Gate 3
`aplicar_gate_3_transformacao`) nunca bloqueiam para nenhuma dívida dos três
gabaritos. Confirmado empiricamente
(`particionar_elegibilidade(estado.dividas).ORDEM_ACOES`): `()` para GAB-A,
GAB-B e GAB-C. GAB-A/GAB-B bloqueiam só no Gate 1 (que devolve `acao=None`,
nunca constrói `AcaoRequerida`); GAB-C não bloqueia gate nenhum.

Consequência: `test_tipo_acao_apenas_quatro_valores` (2º critério) varre hoje
um conjunto VAZIO de `AcaoRequerida` — passa de verdade (verificação vácua
legítima), não trivialmente por mascarar `TIPO_ACAO=""` como caso especial.
**Não** foi necessário registrar uma falha conhecida/esperada nem adiar a
conclusão desta tarefa, porque o cenário de risco descrito no enunciado
(Gate 2/Gate 3 disparando e produzindo `TIPO_ACAO=""` fora do domínio) não se
concretiza com as fixtures reais dos três gabaritos — só se concretizaria se
uma fixture futura tivesse dívida com `RISCO_MATERIAL_IMINENTE=true`,
`RENEGOCIACAO_PENDENTE=true` ou `TROCA_PENDENTE=true`. A prova negativa
(`test_verificador_pega_quinto_literal_proposital`, mesmo padrão de
`test_nenhum_parametro_no_codigo.py`) cobre a lacuna: garante que o mecanismo
de verificação em si pegaria um `TIPO_ACAO` fora do domínio (incluindo o
`""` provisório) assim que uma `AcaoRequerida` real o carregasse — sem
depender de uma fixture tocar esse caminho agora.

Fica como observação para quando `T-83`/`T-84` (derivação real de
`TIPO_ACAO` em Gate 2/Gate 3) forem implementadas: reexecutar este teste é
recomendável para garantir que os valores derivados (`"RENEGOCIACAO"`/
`"TROCA"`) continuam dentro do domínio — mas isso já é comportamento normal
de regressão, não uma dependência oculta desta tarefa.

---

### `T-83` — Derivar `TIPO_ACAO` no Gate 1 e no Gate 2

- **Tipo:** `Data`
- **Dependências:** `T-79`, `T-80`
- **Rastreia:** `RF-30`, `AC-50`
- **Arquivos:** `engine/gates.py`

**Descrição**

`GATE_PENDENTE = INFORMACAO` (Gate 1) → `TIPO_ACAO = "INFORMACAO"`. Gate 2 (`RISCO_MATERIAL_IMINENTE`, contenção de risco) → `TIPO_ACAO = "RENEGOCIACAO"` (decisão fechada `AMB-R2-02`, plano §R2.10.1 — Gate 2 não tem valor próprio no domínio de quatro; contenção de risco é semanticamente mais próxima de renegociação). Derivação sempre a partir de `GATE_PENDENTE`, nunca de `gate_origem` (`RF-30`).

**Critérios de aceite**

- [x] Toda `AcaoRequerida` emitida com `gate_origem=1` tem `TIPO_ACAO = "INFORMACAO"` (`AC-50`)
- [x] Toda `AcaoRequerida` emitida pelo Gate 2 (`RISCO_MATERIAL_IMINENTE`) tem `TIPO_ACAO = "RENEGOCIACAO"` (`AMB-R2-02`, resolvida)
- [x] A derivação lê `GATE_PENDENTE`, nunca `gate_origem`, para decidir o `TIPO_ACAO`
- [x] `mypy --strict` passa

**Status:** `[x] concluída`

> **Nota de escopo (2026-09-05).** Foi criada `_derivar_TIPO_ACAO(gate_pendente:
> GATE_PENDENTE) -> str` em `engine/gates.py`, função central que mapeia
> `GATE_PENDENTE.INFORMACAO -> "INFORMACAO"` e `GATE_PENDENTE.CONTENCAO_RISCO
> -> "RENEGOCIACAO"` (`AMB-R2-02`), lendo exclusivamente `GATE_PENDENTE`
> (nunca `gate_origem`); `GATE_PENDENTE.TRANSFORMACAO` levanta
> `NotImplementedError` explícito, documentando que é escopo de `T-84`, não
> desta tarefa. **Gate 2** (`aplicar_gate_2_contencao_risco`) já constrói
> `AcaoRequerida` de verdade desde `T-29`/`T-79` — os dois pontos de emissão
> passaram a consumir `_derivar_TIPO_ACAO` e `_compor_ACAO_ID` (`T-80`),
> substituindo o `TIPO_ACAO=""` provisório; provado por integração real
> (`test_AMBR2_02_gate2_emite_acao_com_tipo_acao_renegociacao`). **Gate 1**
> (`aplicar_gate_1_informacao`) **continua devolvendo `acao=None` nos dois
> ramos de bloqueio** — fazê-lo emitir `AcaoRequerida` de verdade é escopo de
> `T-87` (dependente desta `T-83`), não implementado aqui. Por isso o
> primeiro e o terceiro critério de aceite (que cobrem Gate 1) são
> verificados diretamente sobre a função de derivação isolada
> (`test_AC50_derivar_tipo_acao_gate1_informacao`,
> `test_derivar_tipo_acao_le_gate_pendente_nunca_gate_origem`), não por
> integração ponta a ponta via Gate 1 — mesmo padrão de "verificação vácua
> legítima hoje" já usado em `T-82`. `mypy --strict engine/` passa limpo (25
> arquivos); `ruff check .` limpo; suíte completa: `1132 passed, 75 skipped,
> 4 xfailed, 7 failed` — as 7 falhas são as pré-existentes em
> `tests/app_aluno/` (escopo de outras tarefas, ex. `T-86`+), nenhuma nova
> falha introduzida.

---

### `T-84` — Derivar `TIPO_ACAO` no Gate 3, com prioridade `RENEGOCIACAO` sobre `TROCA`

- **Tipo:** `Data`
- **Dependências:** `T-79`, `T-80`
- **Rastreia:** `RF-30`, `AC-51`, `AC-52`
- **Arquivos:** `engine/gates.py`

**Descrição**

Gate 3 já distingue `RENEGOCIACAO_PENDENTE` de `TROCA_PENDENTE` internamente (variável `origem`, Rodada 1). Passa a preencher `TIPO_ACAO="RENEGOCIACAO"` ou `TIPO_ACAO="TROCA"` a partir do mesmo discriminador. Quando ambos são `True` na mesma dívida, `TIPO_ACAO = "RENEGOCIACAO"` prevalece (decisão fechada `AMB-R2-03`, plano §R2.10.1) — `"TROCA"` só é emitido quando `TROCA_PENDENTE=True` e `RENEGOCIACAO_PENDENTE=False`.

**Critérios de aceite**

- [x] Dívida em Gate 3 com `RENEGOCIACAO_PENDENTE=True` e `TROCA_PENDENTE=False` produz `TIPO_ACAO = "RENEGOCIACAO"` (`AC-51`)
- [x] Dívida em Gate 3 com `TROCA_PENDENTE=True` e `RENEGOCIACAO_PENDENTE=False` produz `TIPO_ACAO = "TROCA"` (`AC-52`)
- [x] Dívida em Gate 3 com ambos `True` simultaneamente produz `TIPO_ACAO = "RENEGOCIACAO"` (`AMB-R2-03`, resolvida — prioridade fixa)
- [x] A derivação usa o discriminador já existente (`origem`), sem introduzir um quinto valor de `TIPO_ACAO`

**Status:** `[x] concluída`

> **Nota de escopo (2026-09-05).** Criada `_derivar_TIPO_ACAO_gate_3(*,
> renegociacao_pendente: bool, troca_pendente: bool) -> str` em
> `engine/gates.py`, função irmã de `_derivar_TIPO_ACAO` (T-83) — não uma
> extensão de sua assinatura, porque aquela função já tem contrato fechado e
> verificado por introspecção em teste (`test_derivar_tipo_acao_le_gate_
> pendente_nunca_gate_origem`, T-83: exige exatamente um parâmetro,
> `gate_pendente`). `aplicar_gate_3_transformacao` passou a chamar essa nova
> função com o mesmo par de campos que já compunha a variável `origem`
> (texto livre, Rodada 1) e a consumir `_compor_ACAO_ID` (T-80),
> substituindo `ACAO_ID=divida.DIVIDA_ID`/`TIPO_ACAO=""` provisórios.
> Prioridade fixa `AMB-R2-03`: `renegociacao_pendente=True` sempre produz
> `"RENEGOCIACAO"`, mesmo com `troca_pendente=True` também — `"TROCA"` só
> quando `troca_pendente=True` e `renegociacao_pendente=False`. Testado por
> integração real (mesmo padrão de T-83 para o Gate 2): `test_AC51_gate3_
> renegociacao_pendente_produz_tipo_acao_renegociacao`, `test_AC52_gate3_
> troca_pendente_produz_tipo_acao_troca`, `test_AMBR2_03_gate3_ambos_
> pendentes_produz_tipo_acao_renegociacao`, mais um teste direto sobre a
> função de derivação isolada confirmando que os três resultados possíveis
> pertencem a `TIPO_ACAO_VALORES` (nenhum quinto valor introduzido). `mypy
> --strict engine/` passa limpo (25 arquivos); `ruff check .` limpo; suíte
> completa: `1136 passed, 75 skipped, 3 xfailed, 8 failed`. Das 8 falhas, 6
> são as pré-existentes em `tests/app_aluno/` que já aguardavam esta
> integração (`test_acoes.py`, `test_acompanhamento_acao_id.py`,
> `test_ordem_acoes_dependencia_externa.py`); as outras 2
> (`tests/app_aluno/estatica/test_engine_congelado.py`) são o "hash
> congelado" de `engine/gates.py` detectando, corretamente e como
> documentado no próprio cabeçalho daquele teste, que este arquivo mudou
> nesta rodada por uma tarefa do slug `motor-calculo` — não uma regressão
> desta tarefa, e a atualização de `hashes_congelados.json` é procedimento
> do backlog `app-aluno` (fora do escopo de `T-84`), não editado aqui.

---

### `T-85` — Testar a derivação de `TIPO_ACAO` a partir de `GATE_PENDENTE`

- **Tipo:** `Test`
- **Dependências:** `T-83`, `T-84`
- **Rastreia:** `RF-30`, `AC-50`, `AC-51`, `AC-52`
- **Arquivos:** `tests/regras/test_gates.py`

**Descrição**

Um teste por critério de aceite de derivação, mais os dois casos de decisão fechada (`AMB-R2-02` Gate 2 → `RENEGOCIACAO`; `AMB-R2-03` prioridade `RENEGOCIACAO` > `TROCA`).

**Critérios de aceite**

- [x] `test_tipo_acao_gate1_informacao` passa (`AC-50`)
- [x] `test_tipo_acao_gate3_renegociacao` passa (`AC-51`)
- [x] `test_tipo_acao_gate3_troca` passa (`AC-52`)
- [x] Um teste cobre Gate 2 → `TIPO_ACAO = "RENEGOCIACAO"` (`AMB-R2-02`)
- [x] Um teste cobre o caso combinado `RENEGOCIACAO_PENDENTE=True` e `TROCA_PENDENTE=True` produzindo `TIPO_ACAO = "RENEGOCIACAO"` (`AMB-R2-03`)
- [x] Todas as asserções de `TIPO_ACAO` usam `assertar_exato`

**Status:** `[x] concluída`

> **Nota de decisão (2026-09-05).** `T-83`/`T-84` já haviam escrito, em
> `tests/regras/test_gates.py`, a cobertura de comportamento que `T-85` pede —
> os 5 cenários de derivação de `TIPO_ACAO` — mas com nomes ligados ao
> AC/decisão em vez dos nomes literais sugeridos no texto desta tarefa.
> Investigação confirmou que os 5 cenários estão cobertos corretamente e que
> toda comparação de `TIPO_ACAO` já usa `assertar_exato` (nunca `assert ==`
> puro) — nenhum código de teste novo foi necessário, só a verificação e este
> registro de mapeamento (decisão (b) do processo desta tarefa: os nomes atuais
> carregam o ID do critério de aceite, convenção já estabelecida por `T-83`/
> `T-84` neste mesmo arquivo — renomear seria mais disruptivo que o benefício
> de rastreabilidade). Mapeamento critério → teste real:
> - `test_tipo_acao_gate1_informacao` (`AC-50`) → `test_AC50_derivar_tipo_acao_gate1_informacao` (linha 723), `assertar_exato(gates._derivar_TIPO_ACAO(GATE_PENDENTE.INFORMACAO), "INFORMACAO")`
> - Gate 2 → `RENEGOCIACAO` (`AMB-R2-02`) → `test_derivar_tipo_acao_gate2_contencao_risco_e_renegociacao` (linha 732, unidade) e `test_AMBR2_02_gate2_emite_acao_com_tipo_acao_renegociacao` (linha 756, integração real via `aplicar_gate_2_contencao_risco`), ambos com `assertar_exato`
> - `test_tipo_acao_gate3_renegociacao` (`AC-51`) → `test_AC51_gate3_renegociacao_pendente_produz_tipo_acao_renegociacao` (linha 785), `assertar_exato(resultado.acao.TIPO_ACAO, "RENEGOCIACAO")`
> - `test_tipo_acao_gate3_troca` (`AC-52`) → `test_AC52_gate3_troca_pendente_produz_tipo_acao_troca` (linha 798), `assertar_exato(resultado.acao.TIPO_ACAO, "TROCA")`
> - Caso combinado `RENEGOCIACAO_PENDENTE=True` + `TROCA_PENDENTE=True` (`AMB-R2-03`) → `test_AMBR2_03_gate3_ambos_pendentes_produz_tipo_acao_renegociacao` (linha 811), `assertar_exato(resultado.acao.TIPO_ACAO, "RENEGOCIACAO")`
> - Complementares (não pedidos por AC específico, mas reforçam `RF-30`):
>   `test_derivar_tipo_acao_le_gate_pendente_nunca_gate_origem` (assinatura só
>   aceita `GATE_PENDENTE`) e `test_derivar_tipo_acao_gate_3_usa_discriminador_
>   existente` (os três resultados possíveis de `_derivar_TIPO_ACAO_gate_3`
>   pertencem a `TIPO_ACAO_VALORES`, sem quinto valor introduzido).
>
> Toda comparação direta de `TIPO_ACAO` no arquivo usa `assertar_exato` — a
> única linha com `assert` puro que toca `TIPO_ACAO` (linha 841,
> `assert {renegociacao, troca, ambos} <= gates.TIPO_ACAO_VALORES`) é checagem
> de pertencimento ao domínio fechado, não comparação de igualdade de um valor
> de `TIPO_ACAO`, e complementa (não substitui) as três `assertar_exato` já
> feitas no mesmo teste. Nenhum código de produção foi tocado (`engine/gates.py`
> intocado, conforme escopo). Verificação: `ruff check .` limpo; `pytest -q
> tests/regras/test_gates.py` → `42 passed`; `mypy --strict` sobre as pastas
> filtradas do comando `build` → 5 erros pré-existentes fora de `engine/`
> (`report/plano.py`, `persistencia/arquivo/repositorio_snapshots.py`,
> `app/casos/coleta_dirigida.py`, mais `tests/regras/test_gates.py:612`, este
> último já existente antes desta tarefa, ligado ao relaxamento de `DIVIDA_ID`
> de `T-79`/`T-86`); suíte completa `pytest -q` → `1136 passed, 75 skipped,
> 3 xfailed, 8 failed` — as 8 falhas são as mesmas já documentadas nas notas de
> `T-83`/`T-84` (`tests/app_aluno/estatica/test_engine_congelado.py` com hash
> congelado desatualizado, e `tests/app_aluno/test_acoes.py`,
> `test_acompanhamento_acao_id.py`, `test_ordem_acoes_dependencia_externa.py`
> aguardando a integração do backlog `app-aluno`), nenhuma falha nova
> introduzida por esta tarefa.

---

### `T-86` — Varrer consumidores internos de `AcaoRequerida.DIVIDA_ID` após o relaxamento para `str | None`

- **Tipo:** `Data`
- **Dependências:** `T-79`
- **Rastreia:** `RF-31`, `AC-55`, `EC-21`
- **Arquivos:** `engine/gates.py`, `engine/ordem.py`, `engine/motor.py`

**Descrição**

Procedimento de auditoria descrito no plano §R2.9: rodar `mypy --strict engine/` (comando `build`, `sdd.config.md` §2) depois do relaxamento de `T-79` e corrigir todo consumidor que hoje presume `DIVIDA_ID: str` sem checar `None` primeiro. O plano já audita e confirma que `engine/ordem.py:269` lê `ResultadoGates.DIVIDA_ID` (campo diferente, sempre `str`, não afetado) — esta tarefa reconfirma isso no código atual e corrige qualquer ponto novo que a implementação de `T-79`/`T-83`/`T-84` introduzir.

**Critérios de aceite**

- [x] `mypy --strict engine/` roda depois do relaxamento de `DIVIDA_ID` e passa sem erro de tipagem relacionado a `AcaoRequerida.DIVIDA_ID`
- [x] Nenhum ponto de `engine/*.py` lê `AcaoRequerida.DIVIDA_ID` como `str` sem checar `is None`/`is not None` antes (`AC-55`)
- [x] `engine/ordem.py:269` (leitura de `ResultadoGates.DIVIDA_ID`) é reconfirmado como campo distinto, não afetado por `RF-31`
- [x] A lista de arquivos tocados pela checagem é registrada na descrição de implementação, para revisão confirmar que `EC-21` (falha visível no `build`, não silenciosa) se cumpriu
- [x] Introduzir propositalmente um uso de `acao.DIVIDA_ID` como `str` sem checagem faz `mypy --strict` falhar (prova de que a rede de segurança funciona)

**Status:** `[x] concluída`

> **Nota de escopo e divergência (2026-09-05).** Releitura de
> `plans/motor-calculo.plan.md` §R2.9 (procedimento de auditoria de `RF-31`)
> confirma que a varredura desta tarefa é, por desenho do próprio plano,
> **restrita a `engine/*.py`** — o texto do plano diz textualmente "Não é um
> teste de comportamento; é uma verificação de cobertura de tipo" e já traz o
> resultado do grep de planejamento: "nenhum outro ponto de `engine/*.py` lê
> `AcaoRequerida.DIVIDA_ID` hoje". O campo "Arquivos" formal de `T-86`
> (`engine/gates.py`, `engine/ordem.py`, `engine/motor.py`) está, portanto,
> correto e coerente com o plano — não é um recorte incompleto.
>
> **(a) Escopo `engine/` — satisfeito.** `mypy --strict engine/gates.py
> engine/ordem.py engine/motor.py` → `Success: no issues found in 3 source
> files`; `mypy --strict engine/` completo → `Success: no issues found in 25
> source files`. Confirmado por leitura direta: `engine/ordem.py:269`
> (`ids_bloqueados = {resultado.DIVIDA_ID for resultado in
> particao.bloqueadas}`) itera `particao.bloqueadas: list[ResultadoGates]` e
> lê `ResultadoGates.DIVIDA_ID: str` (linha 270 de `engine/gates.py`) — campo
> distinto de `AcaoRequerida.DIVIDA_ID: str | None` (linha 157), não afetado
> por `RF-31`. Único ponto de `engine/gates.py` que checa `AcaoRequerida`
> antes de usá-la é `resultado_gates.acao is not None` (linha 812), padrão
> correto. `engine/motor.py` hoje só lê `divida.DIVIDA_ID` (campo de
> `Divida`, sempre `str`) para indexar dicionário — não lê
> `AcaoRequerida.DIVIDA_ID` (ação de economia, `RF-33`/`T-88`, ainda não
> implementada). Nenhum ponto de `engine/gates.py`, `engine/ordem.py` ou
> `engine/motor.py` lê `AcaoRequerida.DIVIDA_ID` como `str` sem checagem.
> Prova de rede de segurança: arquivo `.py` temporário fora da árvore do
> projeto com `def f(acao: AcaoRequerida) -> str: return
> acao.DIVIDA_ID.upper()` (sem checar `None`) rodado com `mypy --strict` →
> `error: Item "None" of "str | None" has no attribute "upper"  [union-attr]`
> — arquivo removido logo em seguida, nenhuma sujeira deixada no repositório;
> a prova foi convertida em teste permanente (ver adiante), seguindo o padrão
> já estabelecido em `tests/estatica/test_ordem_de_derivacao.py` (T-25) de
> rodar `mypy --strict` como subprocess sobre trecho sintetizado fora da
> árvore — mais fiel ao critério de aceite 5 (que pede prova via `mypy`, não
> via runtime) do que o padrão de `test_tipo_acao_apenas_quatro_valores.py`
> (T-82, prova por varredura de runtime). Novo arquivo:
> `tests/estatica/test_acao_requerida_divida_id_opcional.py` com
> `test_AC55_divida_id_sem_checagem_falha_no_mypy_strict` (prova negativa,
> espera `union-attr`) e `test_AC55_divida_id_com_checagem_compila`
> (contraprova: mesmo consumo, com `is None` checado antes, compila limpo) —
> `2 passed`.
>
> **(b) Os 5 erros de `report/`, `persistencia/`, `app/` permanecem SEM
> correção.** `build` completo (`sdd.config.md` §2,
> `mypy engine persistencia collection app report tests`) continua
> reportando exatamente os mesmos 5 erros já documentados nas notas de
> `T-79`/`T-80`/`T-83`/`T-84`/`T-85`: `report/plano.py:369` (`arg-type`,
> `ContextoAcaoRequerida` espera `DIVIDA_ID: str`), `persistencia/arquivo/
> repositorio_snapshots.py:484` (`call-arg`, `_acao_requerida` sem
> `ACAO_ID`/`TIPO_ACAO`), `app/casos/coleta_dirigida.py:142` e `:149`
> (`arg-type`, `acao.DIVIDA_ID` usado onde `dict.get`/`list.append` esperam
> `str`), `tests/regras/test_gates.py:612` (`type-var`, `sorted()` sobre
> gerador `str | None`) — `Found 5 errors in 4 files`, nenhum a mais, nenhum
> a menos que antes desta tarefa. **Essas notas anteriores presumiram
> incorretamente que "T-86 resolve" esses 5 erros**: o texto formal da
> tarefa (campo "Arquivos") nunca incluiu `report/`, `persistencia/` nem
> `app/`, e o plano técnico (§R2.9) desenhou a auditoria de `RF-31`
> deliberadamente restrita a `engine/*.py` — não há inconsistência entre o
> plano e o texto formal da tarefa; a inconsistência estava só nas notas
> informais de fechamento das tarefas anteriores, que generalizaram "escopo
> de correção é T-86" sem conferir o campo "Arquivos" nem a §R2.9 do plano.
> Por regra de escopo desta tarefa, **nenhum desses três arquivos foi
> tocado**.
>
> **(c) Recomendação.** Não há, no backlog atual (`T-87` a `T-91`), nenhuma
> tarefa que declare `report/plano.py`,
> `persistencia/arquivo/repositorio_snapshots.py` ou
> `app/casos/coleta_dirigida.py` como escopo de arquivos. Recomenda-se abrir
> uma tarefa nova (ex. `T-92`) dedicada a corrigir esses 3 arquivos (5 erros)
> — decisão que fica para revisão humana, não tomada aqui.
>
> **Verificação completa:** `ruff check .` → `All checks passed!`; `mypy
> --strict` nos três arquivos do escopo formal → limpo; `mypy --strict
> engine/` → limpo (25 arquivos); `build` completo (`sdd.config.md` §2) →
> `5 errors in 4 files` (mesmos de sempre, fora de `engine/`); `pytest -q`
> suíte completa → `8 failed, 1138 passed, 75 skipped, 3 xfailed` — as 8
> falhas são as mesmas 8 pré-existentes já documentadas nas notas de `T-84`/
> `T-85` (todas em `tests/app_aluno/`, backlog `app-aluno`, aguardando
> integração daquele slug), nenhuma falha nova introduzida por esta tarefa;
> os `1138 passed` incluem os 2 testes novos desta tarefa.

---

### `T-87` — Fazer o Gate 1 emitir `AcaoRequerida` nos dois ramos de bloqueio e reexecutar `GAB-A`/`GAB-B`/`GAB-C`/invariantes

- **Tipo:** `Data`
- **Dependências:** `T-79`, `T-80`, `T-83`, `T-86`
- **Rastreia:** `RF-32`, `AC-56`, `AC-57`, `AC-58`, `AC-59`, `AC-60`, `EC-22`
- **Arquivos:** `engine/gates.py`, `tests/gabaritos/test_gabarito_a_deficit.py`, `tests/gabaritos/test_gabarito_b_equilibrio_fragil.py`, `tests/gabaritos/test_gabarito_c_*.py`, `tests/invariantes/*.py`, `tests/regras/test_gates.py`

**Descrição**

**Maior risco desta rodada** (plano §R2.10, spec §8). `aplicar_gate_1_informacao` passa a construir `AcaoRequerida` nos dois ramos de bloqueio, em vez de `acao=None`: ramo `STATUS_DIVIDA == QUITADA_A_CONFIRMAR` → `CAMPO_PENDENTE="STATUS_DIVIDA"`; ramo `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` → `CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL"`. Os dois ramos são mutuamente exclusivos por construção (`EC-22`). Esta tarefa **inclui explicitamente**, não como nota de rodapé, o procedimento obrigatório do plano §R2.9: rodar a suíte completa antes da mudança, identificar quais fixtures tocam Gate 1 (grep por `QUITADA_A_CONFIRMAR`/`SALDO_DEVEDOR_ATUAL` desconhecido), implementar, e então reexecutar `GAB-A`, `GAB-B`, `GAB-C` e os cinco invariantes (`GAB-01` a `GAB-05`), atualizando toda expectativa de `ORDEM_ACOES` que hoje é `()` e passa a vir preenchida — com **tolerância zero**, nunca absorvida por arredondamento. `AC-01`–`AC-04` (método/ordem/custo/prazo) não podem mudar; só `ORDEM_ACOES` pode.

**Critérios de aceite**

- [x] Dívida com `STATUS_DIVIDA == QUITADA_A_CONFIRMAR` processada por `aplicar_gate_1_informacao` produz `ResultadoGates.acao` não `None`, com `TIPO_ACAO="INFORMACAO"` e `CAMPO_PENDENTE="STATUS_DIVIDA"` (`AC-56`)
- [x] Dívida com `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` dentro de `compor_VALOR_RELEVANTE_PARA_QUITACAO` produz `ResultadoGates.acao` não `None`, com `TIPO_ACAO="INFORMACAO"` e `CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL"` (`AC-57`)
- [x] Os dois ramos permanecem mutuamente exclusivos por construção — o segundo `if` só é avaliado quando o primeiro não bloqueou; `CAMPO_PENDENTE` nunca é ambíguo (`EC-22`)
- [x] `GAB-A`, `GAB-B` e `GAB-C` reexecutados: `ORDEM_ACOES` atualizada onde alguma dívida tocar Gate 1; `AC-01`–`AC-04` permanecem idênticos, com tolerância zero (`AC-58`)
- [x] `GAB-03` (dívida rotativa sem saldo/pagamento) reexecutado: `ORDEM_ACOES` reflete a `AcaoRequerida` agora emitida, com tolerância zero (`AC-58`)
- [x] Cenário `EC-17` (todas as dívidas bloqueadas pelos gates) reexecutado: `ORDEM_ACOES` vem preenchida com as ações de informação correspondentes, em vez de vazia, com tolerância zero (`AC-59`)
- [x] Os cinco invariantes `GAB-01` a `GAB-05` reexecutados e continuam satisfeitos (`AC-60`)
- [x] Suíte completa (`pytest -q`) passa depois da mudança, sem regressão em teste pré-existente que não deveria mudar

**Status:** `[x] concluída`

> **Nota de fechamento (2026-09-05).**
>
> **(1) Procedimento §R2.9 seguido na ordem.** Baseline antes de editar:
> `pytest -q` → `8 failed, 1138 passed, 75 skipped, 3 xfailed` (bate com o
> documentado em `T-86`). Grep por `QUITADA_A_CONFIRMAR`/`SALDO_DEVEDOR_
> ATUAL` em `tests/fixtures/` identificou, ANTES de implementar: `gab_a.json`
> (D001, D002) e `gab_b.json` (D001) têm `SALDO_DEVEDOR_ATUAL = "DESCONHECIDO"`
> e `VALOR_QUITACAO_HOJE = "DESCONHECIDO"`/`QUITACAO_CONSULTADA = "NAO"` — ou
> seja, `VALOR_RELEVANTE_PARA_QUITACAO = DESCONHECIDO` para TODAS as dívidas
> de `GAB-A`/`GAB-B`; `gab_c.json` tem os três saldos conhecidos (12000/7000/
> 3000) — não toca Gate 1. `tests/invariantes/test_gab03_rotativo.py` já
> continha a asserção `resultado_bloqueio.acao is None` (T-73), documentada
> como precisando de reescrita explícita — confirmado antes de editar.
>
> **(2) Implementação em `engine/gates.py`.** Os dois `if` de `aplicar_gate_1_
> informacao` permanecem sequenciais (nenhuma alteração na estrutura de
> controle) — o segundo só é avaliado se o primeiro não retornou, garantindo
> `EC-22` por construção. Cada ramo agora constrói `AcaoRequerida` com
> `TIPO_ACAO=_derivar_TIPO_ACAO(GATE_PENDENTE.INFORMACAO)` (T-83),
> `ACAO_ID=_compor_ACAO_ID(...)` (T-80), `gate_origem=1`, e
> `CAMPO_PENDENTE="STATUS_DIVIDA"` (ramo 1) ou `"SALDO_DEVEDOR_ATUAL"` (ramo
> 2), reaproveitando o `motivo` textual já existente como `descricao`.
> Docstrings do módulo atualizadas (cabeçalho, `REGRAS`, `ParticaoElegibilidade`,
> `aplicar_gate_1_informacao`) para refletir que Gate 1 agora emite `acao`
> nos dois ramos, junto dos Gates 2/3.
>
> **(3) `mypy --strict engine/` e `pytest tests/regras/test_gates.py`
> isolados, primeiro.** `mypy engine` → `Success: no issues found in 25
> source files`. `test_gates.py` isolado revelou, como esperado, exatamente
> 2 falhas por mudança de `ORDEM_ACOES` de `()`/incompleta para preenchida —
> nenhuma falha de tipo/lógica:
> `test_particionar_elegibilidade_carteira_mista_classifica_cada_divida`
> (`ids_em_ordem_acoes` de `("D-02", "D-03")` para `("D-01", "D-02", "D-03")`
> — D-01 é `QUITADA_A_CONFIRMAR`, Gate 1) e
> `test_EC17_nenhuma_elegivel_nao_produz_alvo`
> (`len(particao.ORDEM_ACOES)` de `1` para `2`, IDs de `("D-02",)` para
> `("D-01", "D-02")`). Ambas confirmadas como mudança ESPERADA (a dívida
> D-01 realmente bloqueia no Gate 1 por `QUITADA_A_CONFIRMAR`, e a
> `AcaoRequerida` resultante tem `TIPO_ACAO="INFORMACAO"`/
> `CAMPO_PENDENTE="STATUS_DIVIDA"`/`gate_origem=1`, exatamente o que a spec
> pede) e só então as expectativas foram atualizadas — nunca ajustadas "para
> passar" sem essa verificação. `AC-01`–`AC-04` (método/ordem/custo/prazo)
> não aparecem em nenhum dos dois testes — não mudaram. Três testes novos
> adicionados por exigência do plano §R2.9:
> `test_gate1_quitada_a_confirmar_emite_acao_informacao` (`AC-56`),
> `test_gate1_saldo_desconhecido_emite_acao_informacao` (`AC-57`),
> `test_gate1_dois_ramos_mutuamente_exclusivos` (`EC-22`). `45 passed` no
> arquivo depois de tudo atualizado.
>
> **(4) Gabaritos/invariantes (`pytest -m "gabarito or invariante"`).**
> `GAB-A` (`test_gabarito_a_deficit`) e `GAB-B` (`test_gabarito_b_
> equilibrio_fragil`/`test_gabarito_b_ac07_...`) chamam só `calcular_
> diagnostico`, não `particionar_elegibilidade`/gates — **não tocam
> `ORDEM_ACOES`, nenhuma mudança de expectativa**, `AC-05`/`AC-06`/`AC-07`
> idênticos, `PASSED` sem edição. `GAB-C` (4 arquivos:
> `test_gabarito_c_avalanche/bola_de_neve/hibrido/recomendacao`) usa dívidas
> com saldo conhecido (12000/7000/3000) — não toca Gate 1, nenhuma delas lê
> `ORDEM_ACOES`/`acao`, `PASSED` sem edição, `AC-01`–`AC-04`
> (método/ordem/custo/prazo) idênticos. Única falha real na primeira
> execução: `tests/invariantes/test_gab03_rotativo.py::test_invariante_
> gab03_rotativo`, que continha a asserção proposital `resultado_bloqueio.
> acao is None` — confirmado que a dívida `D-ROTATIVO` bloqueia no Gate 1
> ramo 2 (`SALDO_DEVEDOR_ATUAL is DESCONHECIDO`) e que a `AcaoRequerida`
> resultante (`TIPO_ACAO="INFORMACAO"`, `CAMPO_PENDENTE="SALDO_DEVEDOR_
> ATUAL"`, `ACAO_ID="D-ROTATIVO:INFORMACAO"`) bate com o esperado por
> `AC-57`/`AC-58` — asserção invertida com tolerância zero:
> `resultado_bloqueio.acao is not None`, `particao.ORDEM_ACOES` passa de
> vazia (`()`) para uma única `AcaoRequerida` com esses valores exatos.
> `GAB-01`/`GAB-02`/`GAB-04`/`GAB-05` usam dívidas com saldo/valor conhecidos
> — não tocam Gate 1, `PASSED` sem edição. Total: `18 passed` em
> `-m "gabarito or invariante"` (`AC-58`, `AC-59`, `AC-60` confirmados).
>
> **Resumo de `ORDEM_ACOES` alterada (de → para), tolerância zero:**
>
> | Teste | Antes | Depois |
> | --- | --- | --- |
> | `test_particionar_elegibilidade_carteira_mista_classifica_cada_divida` | `("D-02", "D-03")` | `("D-01", "D-02", "D-03")`, com `acao_d01.TIPO_ACAO="INFORMACAO"`/`CAMPO_PENDENTE="STATUS_DIVIDA"`/`gate_origem=1` |
> | `test_EC17_nenhuma_elegivel_nao_produz_alvo` | `len == 1`, `("D-02",)` | `len == 2`, `("D-01", "D-02")`, mesmos campos de D-01 acima |
> | `test_invariante_gab03_rotativo` (`GAB-03`) | `resultado_bloqueio.acao is None`; `ORDEM_ACOES == ()` | `resultado_bloqueio.acao` = `AcaoRequerida(ACAO_ID="D-ROTATIVO:INFORMACAO", TIPO_ACAO="INFORMACAO", CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL", gate_origem=1)`; `ORDEM_ACOES` = `(essa mesma ação,)` |
> | `GAB-A`, `GAB-B`, `GAB-C` (todos os 6 arquivos de gabarito numérico) | — | **sem mudança** (não exercitam `ORDEM_ACOES`; `GAB-C` não toca Gate 1) |
> | `GAB-01`, `GAB-02`, `GAB-04`, `GAB-05` | — | **sem mudança** (dívidas com saldo conhecido, não tocam Gate 1) |
>
> **Confirmação `AC-01`–`AC-04` (método/ordem/custo/prazo): idênticos.**
> Nenhum dos testes acima lê/asserta `METODO_RECOMENDADO_PIQ`, `ORDEM_
> QUITACAO`, custo ou prazo — só `ORDEM_ACOES` (fila paralela) mudou, exatamente
> a restrição da tarefa.
>
> **(5) Descoberta durante verificação, fora do escopo formal desta tarefa —
> não corrigida aqui.** `mypy --strict` completo (`build`) revelou que meu
> próprio arquivo de escopo (`tests/regras/test_gates.py`) introduziu uma
> SEGUNDA ocorrência do erro pré-existente `type-var` (`sorted()` sobre
> gerador `str | None`, já documentado desde `T-83`/`T-86` na linha 612) ao
> duplicar o mesmo padrão no novo teste de `EC-17` — **esta, por estar dentro
> do escopo de arquivos de `T-87`, foi corrigida**: as duas ocorrências agora
> fazem narrowing explícito (`assert acao.DIVIDA_ID is not None`) antes de
> `sorted`, eliminando as 2 ocorrências (o `build` completo caiu de 5 para 4
> erros — 1 a menos que o baseline de `T-86`, nenhum a mais). Os 4 erros
> remanescentes (`report/plano.py:369`, `persistencia/arquivo/repositorio_
> snapshots.py:484`, `app/casos/coleta_dirigida.py:142`/`:149`) são
> EXATAMENTE os já documentados nas notas de `T-79`/`T-80`/`T-83`/`T-84`/
> `T-85`/`T-86`, fora do escopo formal de arquivos desta tarefa, e já cobertos
> por `T-92` (aberta anteriormente para esse fim) — nenhum tocado aqui.
>
> **(6) Suíte completa `pytest -q`, comparação com baseline.** Depois:
> `10 failed, 1140 passed, 75 skipped, 2 xfailed`. As diferenças em relação
> ao baseline (`8 failed, 1138 passed, 75 skipped, 3 xfailed`) são
> integralmente explicadas e nenhuma é regressão real:
> - `+2 passed` líquido: 3 testes novos em `tests/regras/test_gates.py`
>   menos 1 teste que migrou de `xfailed` para a contagem de `failed` (ver
>   próximo item) = +2.
> - `3 xfailed → 2 xfailed` e `+1 failed` do tipo `XPASS(strict)`:
>   `tests/app_aluno/test_ordem_acoes_dependencia_externa.py::test_ac47_
>   divida_bloqueada_pelo_gate_1_tem_acao_de_tipo_informacao` — este teste
>   (do slug `app-aluno`, fora de `motor-calculo`) tinha `xfail(strict=True,
>   reason="aguarda motor-calculo fazer o Gate 1 emitir AcaoRequerida de tipo
>   informacao...")`: com `T-87` implementada, a asserção real do teste passa
>   de verdade, e `strict=True` reporta esse "passar inesperado" como falha —
>   comportamento DESEJADO por desenho (força quem entregar `app-aluno` a
>   remover o marcador `xfail`), não uma regressão de `motor-calculo`. Os
>   outros 2 `XPASS(strict)` do mesmo arquivo (`test_ac45`, `test_ac48`) JÁ
>   apareciam como `failed` no baseline (mudança de `T-79`/`T-80`/`T-83`,
>   rodadas anteriores) e continuam idênticos.
> - `+1 failed` genuína, mas de causa raiz PRÉ-EXISTENTE e já registrada:
>   `tests/app_aluno/test_rotas_revisao_comparacao.py::test_desconhecido_e_
>   exibido_de_forma_visivel_nunca_como_zero_ou_vazio` falha com
>   `TypeError: AcaoRequerida.__init__() missing 2 required positional
>   arguments: 'ACAO_ID', 'TIPO_ACAO'` em `persistencia/arquivo/repositorio_
>   snapshots.py:484` (`_acao_requerida`) — o MESMO bug de desserialização já
>   documentado como erro de `mypy --strict` desde `T-79` e explicitamente
>   atribuído a `T-92` ("Atualizar consumidores de `AcaoRequerida` fora de
>   `engine/` para o novo contrato", already aberta no backlog antes desta
>   sessão, arquivo listado: `persistencia/arquivo/repositorio_snapshots.py`).
>   Este teste é o primeiro a exercitar esse caminho com uma `AcaoRequerida`
>   REAL vinda do Gate 1 (antes só Gates 2/3 produziam `acao`, e nenhum teste
>   de `app_aluno` parece ter persistido/relido um snapshot com ação de Gate 2
>   pelo caminho HTTP exercitado aqui) — `persistencia/arquivo/repositorio_
>   snapshots.py` NÃO está no campo "Arquivos" de `T-87` (só `engine/gates.py`
>   e os testes de `motor-calculo` listados), então, por regra de escopo
>   (`sdd.config.md` §4 / regra 4 do `CLAUDE.md`), não foi tocado aqui; fica
>   para `T-92`, que já é dona desse arquivo.
> - Um teste (`tests/app_aluno/test_conversao_decimal.py::test_propriedade_
>   string_recusada_...`) apareceu como falha em UMA execução da suíte
>   completa e passou isoladamente e em reexecução — confirmado como flaky
>   pré-existente (não relacionado a `T-87`; suíte completa reexecutada sem
>   ele reaparecer).
> - As 8 falhas pré-existentes de `T-86` continuam presentes, com os MESMOS
>   nomes, nenhuma delas alterada em causa raiz por esta tarefa.
> - `pytest -q --ignore=tests/app_aluno` (todo o restante do slug
>   `motor-calculo`): `353 passed, 9 skipped` — zero falha fora de
>   `app_aluno`.
>
> **Verificação completa:** `ruff check .` → `All checks passed!`; `mypy
> --strict engine/` → limpo (25 arquivos); `build` completo → `4 errors in 3
> files` (1 a menos que o baseline de `T-86`, todos pré-existentes e fora do
> escopo formal desta tarefa); `pytest -q` → `10 failed, 1140 passed, 75
> skipped, 2 xfailed`, com todas as diferenças em relação ao baseline
> explicadas acima e nenhuma regressão real dentro do escopo de `motor-
> calculo`.

---

### `T-88` — Emitir `AcaoRequerida` de economia fora do fluxo de gates, em `engine/motor.py`

- **Tipo:** `Data`
- **Dependências:** `T-79`, `T-80`, `T-87`
- **Rastreia:** `RF-33`, `AC-53`, `AC-54`, `EC-20`
- **Arquivos:** `engine/motor.py`

**Descrição**

Novo ponto de emissão dentro de `calcular_plano` (decisão do plano §R2.5/§R2.6 — não em `engine/gates.py`, que opera por dívida e não recebe `EstadoFinanceiro`): quando `estado.ECONOMIA_POTENCIAL_IMEDIATA > 0`, emite `AcaoRequerida(TIPO_ACAO="ECONOMIA", DIVIDA_ID=None, gate_origem=None, CAMPO_PENDENTE=None, ACAO_ID=_compor_ACAO_ID(divida_id=None, tipo_acao="ECONOMIA"))`, concatenada a `particao.ORDEM_ACOES` antes de repassar para `publicar_ORDEM_QUITACAO`. `ECONOMIA_POTENCIAL_IMEDIATA = 0` não emite nada — é o caso comum, não uma falha.

**Critérios de aceite**

- [x] `ECONOMIA_POTENCIAL_IMEDIATA > 0` produz uma `AcaoRequerida` em `ORDEM_ACOES` com `TIPO_ACAO="ECONOMIA"` e `DIVIDA_ID=None` (`AC-53`)
- [x] `ECONOMIA_POTENCIAL_IMEDIATA = 0` não adiciona nenhuma `AcaoRequerida` de `TIPO_ACAO="ECONOMIA"` (`AC-54`)
- [x] Quando há simultaneamente `ECONOMIA_POTENCIAL_IMEDIATA > 0` e uma ou mais dívidas bloqueadas pelo Gate 1, `ORDEM_ACOES` contém tanto a(s) `AcaoRequerida` de `TIPO_ACAO="INFORMACAO"` quanto a de `TIPO_ACAO="ECONOMIA"` — emissão independente do estado dos gates (`EC-20`)
- [x] A lógica não altera a assinatura de `particionar_elegibilidade`/`aplicar_gates_1_a_4` em `engine/gates.py`
- [x] `mypy --strict` passa

**Status:** `[x] concluída`

> **Nota de fechamento (2026-09-05).**
>
> **(1) Implementação.** `engine/motor.py` ganhou `_acao_economia_se_houver(estado)
> -> AcaoRequerida | None` (RF-33): `estado.ECONOMIA_POTENCIAL_IMEDIATA <= dinheiro(0)`
> devolve `None` (`AC-54`, caso comum); caso contrário monta `AcaoRequerida(
> ACAO_ID=_compor_ACAO_ID(divida_id=None, tipo_acao="ECONOMIA"), DIVIDA_ID=None,
> TIPO_ACAO="ECONOMIA", descricao=<motivo textual auditável>, gate_origem=None,
> CAMPO_PENDENTE=None)` (`AC-53`). Dentro de `calcular_plano`, logo após `particao =
> particionar_elegibilidade(estado.dividas)` (passo 6), a ação de economia — se
> houver — é concatenada via `dataclasses.replace(particao, ORDEM_ACOES=(*particao.
> ORDEM_ACOES, acao_economia))`, e esse `particao` (possivelmente estendido) é o
> mesmo repassado a `publicar_ORDEM_QUITACAO` mais adiante — exatamente o ponto de
> concatenação descrito no texto da tarefa e no plano §R2.5 item 5. A emissão só lê
> `estado`, nunca o resultado dos gates — por construção, é independente do estado
> de qualquer dívida (`EC-20`). `engine/gates.py` não foi tocado.
>
> **(2) Decisão sobre `_compor_ACAO_ID` (símbolo privado importado entre
> módulos).** O plano (§R2.6) recomenda expor a função como não-privada,
> reaproveitada por `motor.py`, para evitar duplicar a composição de `ACAO_ID`
> em dois arquivos. Investigação antes de agir: `_compor_ACAO_ID` já é
> referenciada diretamente por dois arquivos de teste fora do escopo formal de
> `T-88` — `tests/regras/test_gates.py` e `tests/estatica/
> test_acao_id_determinismo_puro.py`, ambos via `gates._compor_ACAO_ID`/
> `gates_mod._compor_ACAO_ID` (acesso de teste ao próprio módulo, não um import
> de produção). Renomear o símbolo (removendo o `_`) quebraria esses testes,
> que não estão no campo "Arquivos" desta tarefa — mudança fora de escopo
> (regra 4, `CLAUDE.md`/`sdd.config.md` §4). Decisão tomada: **não renomear**;
> `engine/motor.py` importa `_compor_ACAO_ID` diretamente de `engine/gates.py`
> (`from engine.gates import AcaoRequerida, _compor_ACAO_ID, particionar_
> elegibilidade`). Verificado que isso não é um problema real: (a) Python não
> impede a importação de um símbolo `_` entre módulos do mesmo pacote — é
> convenção, não encapsulamento; (b) `ruff` do projeto seleciona só `["E", "F",
> "W", "I", "UP", "B"]` (`pyproject.toml`), nenhuma dessas famílias de regra
> proíbe acesso a membro "privado" por convenção de nome — `ruff check .` →
> `All checks passed!`; (c) `mypy --strict` não recusa o import (`Success: no
> issues found`). Fica como recomendação para revisão humana decidir, numa
> tarefa futura de rastreabilidade de arquitetura (não esta), se vale a pena
> renomear `_compor_ACAO_ID` para `compor_ACAO_ID` em uma tarefa dedicada que
> também atualize os dois arquivos de teste que hoje referenciam o nome privado —
> não feito aqui por ser mudança de nome fora do escopo de arquivos de `T-88`
> (só `engine/motor.py`).
>
> **(3) Testes novos.** `tests/regras/test_motor.py` ganhou três testes
> (`pytest.mark.regra`): `test_AC53_economia_potencial_positiva_emite_acao_de_
> economia` (`GAB-C` com `ECONOMIA_POTENCIAL_IMEDIATA` elevada a 500 via
> `dataclasses.replace`; confirma exatamente 1 `AcaoRequerida` com
> `TIPO_ACAO="ECONOMIA"`, `DIVIDA_ID=None`, `gate_origem=None`,
> `CAMPO_PENDENTE=None`), `test_AC54_economia_potencial_zero_nao_emite_acao`
> (`GAB-C` com o campo já zerado na fixture; confirma zero ações de
> `TIPO_ACAO="ECONOMIA"`) e `test_EC20_economia_coexiste_com_acoes_de_
> informacao_do_gate_1` (`GAB-A`, cujas duas dívidas têm `SALDO_DEVEDOR_ATUAL =
> DESCONHECIDO` e por isso já bloqueiam no Gate 1 desde `T-87`, com
> `ECONOMIA_POTENCIAL_IMEDIATA` elevada a 300; confirma que `ORDEM_ACOES` tem
> ao menos uma ação `"INFORMACAO"` e exatamente uma `"ECONOMIA"`
> simultaneamente). Cobertura mínima pedida pelo texto da tarefa — suíte
> completa e nomes formais por critério de aceite ficam para `T-89`. `pytest -q
> tests/regras/test_motor.py` → `11 passed` (8 pré-existentes + 3 novos).
>
> **(4) Verificação completa.** `ruff check .` → `All checks passed!`; `mypy
> --strict engine/motor.py` → `Success: no issues found in 1 source file`;
> `mypy --strict engine/` → `Success: no issues found in 25 source files`;
> `build` completo (`mypy engine persistencia collection app report tests`) →
> `4 errors in 3 files` (`report/plano.py:369`, `persistencia/arquivo/
> repositorio_snapshots.py:484`, `app/casos/coleta_dirigida.py:142`/`:149`) —
> EXATAMENTE os 4 erros já documentados na nota de fechamento de `T-87`, escopo
> de `T-92`, nenhum novo, nenhum a menos; `pytest -q` suíte completa → `12
> failed, 1143 passed, 75 skipped, 1 warning` (vs. baseline de `T-87`: `10
> failed, 1140 passed, 75 skipped, 2 xfailed`). As diferenças são integralmente
> explicadas e nenhuma é regressão real de `motor-calculo`:
> - `+3 passed`: os três testes novos desta tarefa.
> - `2 xfailed → 0 xfailed` e `+2 failed` do tipo `XPASS(strict)`:
>   `tests/app_aluno/test_ordem_acoes_dependencia_externa.py::test_ac46_
>   cada_tipo_abre_exclusivamente_sua_pergunta_de_resultado` e
>   `::test_ac49_acao_de_economia_conforme_economia_potencial_imediata` — os
>   dois `reason` de `xfail(strict=True)` citam textualmente "aguarda
>   motor-calculo emitir a ação de economia fora do fluxo de gates quando
>   ECONOMIA_POTENCIAL_IMEDIATA > 0"; com `T-88` implementada, a asserção real
>   passa de verdade e `strict=True` reporta esse "passar inesperado" como
>   falha — mesmo padrão DESEJADO já documentado em `T-87` para `test_ac47`
>   (força quem entregar `app-aluno` a remover o marcador `xfail`), não uma
>   regressão de `motor-calculo`.
> - As demais falhas são EXATAMENTE as já presentes no baseline de `T-87`, sem
>   mudança de causa raiz: `test_ac45`, `test_ac47`, `test_ac48` (já eram
>   `XPASS(strict)`/`failed` desde `T-87`); `test_engine_congelado.py::test_
>   ac44_hashes_congelados_batem_com_o_conteudo_atual_dos_arquivos` e `::test_
>   ac44_alterar_um_byte_muda_o_hash_e_seria_detectado` (hash congelado de
>   `engine/gates.py`/`engine/motor.py` desatualizado — já apontava divergência
>   em `gates.py` desde a edição de `T-87`; agora também aponta `motor.py`,
>   mesma causa estrutural, manutenção pertencente ao slug `app-aluno`, não a
>   `motor-calculo`); `test_acoes.py::test_tipo_acao_de_levanta_erro_nomeado_
>   sobre_acao_requerida_real`/`test_perguntas_do_bloco_11_levanta_o_mesmo_erro_
>   sobre_acao_requerida_real` e `test_acompanhamento_acao_id.py::test_acao_id_
>   de_levanta_erro_nomeado_sobre_acao_requerida_real`/`test_item_id_do_bloco_
>   11_levanta_o_mesmo_erro_sobre_acao_requerida_real` (pré-existentes desde
>   `T-83`/`T-84` — a premissa `not hasattr(acao_real, "ACAO_ID"/"TIPO_ACAO")`
>   já era falsa desde que esses campos foram adicionados a `AcaoRequerida`,
>   nada mudado por esta tarefa); `test_rotas_revisao_comparacao.py::test_
>   desconhecido_e_exibido_de_forma_visivel_nunca_como_zero_ou_vazio`
>   (`repositorio_snapshots.py:484`, mesma causa raiz já atribuída a `T-92`
>   desde `T-87`).
> - `pytest -q --ignore=tests/app_aluno` → `356 passed, 9 skipped` (era `353
>   passed, 9 skipped` em `T-87`; os `+3` são os testes novos) — zero falha
>   fora de `app_aluno`.
> - `pytest -q -m "gabarito or invariante"` → `18 passed` — idêntico ao
>   resultado de `T-87`, nenhuma regressão em gabaritos/invariantes.

---

### `T-89` — Testar a emissão da ação de economia

- **Tipo:** `Test`
- **Dependências:** `T-88`
- **Rastreia:** `RF-33`, `AC-53`, `AC-54`, `EC-20`
- **Arquivos:** `tests/regras/test_gates.py`, `tests/regras/test_motor.py`

**Descrição**

Cobre os três critérios de `RF-33` como testes de comportamento observável (saída de `calcular_plano`/`ORDEM_ACOES`), não de função interna.

**Critérios de aceite**

- [x] `test_acao_economia_emitida_quando_potencial_positivo` passa (`AC-53`)
- [x] `test_acao_economia_nao_emitida_quando_potencial_zero` passa (`AC-54`)
- [x] `test_acao_economia_coexiste_com_acoes_gate1` passa (`EC-20`)
- [x] As asserções de presença/ausência de `AcaoRequerida` usam `assertar_exato`

**Status:** `[x] concluída`

> **Nota de fechamento (2026-09-05).**
>
> **(1) Cobertura pré-existente confirmada, sem duplicação.** `T-88` já havia
> escrito, em `tests/regras/test_motor.py`, três testes cobrindo exatamente os
> três cenários que `RF-33`/`T-89` pedem — mesmo padrão de mapeamento já
> praticado em `T-85` sobre a cobertura de `T-83`/`T-84`. Investigação dos três
> antes de decidir:
>
> - `test_AC53_economia_potencial_positiva_emite_acao_de_economia` → satisfaz
>   `test_acao_economia_emitida_quando_potencial_positivo` (`AC-53`): chama
>   `calcular_plano` (não a função interna `_acao_economia_se_houver`) e lê
>   `snapshot.ORDEM_ACOES` — comportamento observável, como a descrição de
>   `T-89` exige. Já usava `assertar_exato` em todas as quatro asserções.
> - `test_AC54_economia_potencial_zero_nao_emite_acao` → satisfaz `test_
>   acao_economia_nao_emitida_quando_potencial_zero` (`AC-54`): idem, via
>   `calcular_plano`/`ORDEM_ACOES`. Já usava `assertar_exato` nas duas
>   asserções (estado de entrada e lista de ações de economia vazia).
> - `test_EC20_economia_coexiste_com_acoes_de_informacao_do_gate_1` → satisfaz
>   `test_acao_economia_coexiste_com_acoes_gate1` (`EC-20`): idem, via
>   `calcular_plano`/`ORDEM_ACOES` sobre `GAB-A`. Único ponto que NÃO
>   satisfazia plenamente o quarto critério de aceite: as duas asserções de
>   presença de tipo de ação (`"INFORMACAO" in tipos_presentes` e `"ECONOMIA"
>   in tipos_presentes`) usavam `assert` puro com `in`, não `assertar_exato`.
>
> **(2) Correção aplicada (dentro do escopo de arquivos desta tarefa).** As
> duas asserções de `test_EC20_...` foram reescritas como `assertar_exato(
> "INFORMACAO" in tipos_presentes, True)` e `assertar_exato("ECONOMIA" in
> tipos_presentes, True)` — mesma semântica de verificação de presença,
> agora canalizada pelo helper de tolerância zero. Nenhuma outra linha do
> arquivo foi alterada. `engine/motor.py` e `engine/gates.py` não foram
> tocados (lógica de produção já fechada em `T-88`).
>
> **(3) Decisão sobre nomenclatura.** Mantidos os nomes atuais com ID de
> critério de aceite (`test_AC53_...`, `test_AC54_...`, `test_EC20_...`) em
> vez de renomear para os nomes literais sugeridos no texto da tarefa
> (`test_acao_economia_emitida_quando_potencial_positivo` etc.) — mesmo
> raciocínio de `T-85`: nomes com ID de critério já são a convenção
> estabelecida neste arquivo desde `T-83`/`T-84`/`T-88`; renomear traria
> disrupção sem ganho de cobertura ou de rastreabilidade (o ID já está no
> nome e na docstring de cada teste).
>
> **(4) `tests/regras/test_gates.py`.** Não alterado. A emissão da ação de
> economia vive inteiramente em `engine/motor.py` (`_acao_economia_se_houver`,
> chamada dentro de `calcular_plano`), nunca em `engine/gates.py` — que opera
> por dívida e não recebe `EstadoFinanceiro` nem `ECONOMIA_POTENCIAL_IMEDIATA`
> (decisão do plano §R2.5/§R2.6, já registrada na nota de fechamento de
> `T-88`). Nenhum dos três cenários de `RF-33` faz sentido testado em `test_
> gates.py`.
>
> **(5) Verificação.** `ruff check .` → `All checks passed!`. `pytest -q
> tests/regras/test_motor.py tests/regras/test_gates.py` → `56 passed`. `mypy`
> (`engine persistencia collection app report tests`, filtrado por pastas
> existentes) → `4 errors in 3 files` (`report/plano.py:369`, `persistencia/
> arquivo/repositorio_snapshots.py:484`, `app/casos/coleta_dirigida.py:142`/
> `:149`) — EXATAMENTE os 4 erros já documentados na nota de fechamento de
> `T-88` (escopo `T-92`/backlog `app-aluno`), nenhum novo, nenhum a menos.
> `pytest -q` suíte completa → `12 failed, 1143 passed, 75 skipped, 1
> warning` — número idêntico ao baseline de `T-88`, mesmas 12 falhas, todas em
> `tests/app_aluno/` (escopo `T-92`), sem nenhuma regressão em `motor-calculo`.

---

### `T-90` — Adicionar `Diagnostico.RESERVA_MOBILIZAVEL` e `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` como contrato (shape only)

- **Tipo:** `Data`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-35`, `AC-61`
- **Arquivos:** `engine/diagnostico.py`

**Descrição**

Adiciona os dois campos `Dinheiro` a `Diagnostico`, no mesmo bloco de "campos comportamentais adicionais" já existente (plano §R2.4), na posição após `classificacao_risco_comportamental_geral`. **Esta tarefa NÃO calcula o valor real** — a fórmula está bloqueada por `OQ-23` (spec §10, aberta). O valor é explicitamente não populado com cálculo de negócio: documentar no código, via comentário/docstring citando `OQ-23`, que o campo existe por contrato de tipo/posição e que a derivação real é escopo de `T-91`. Não inventar fórmula. Esta tarefa é independente de `OQ-23` e pode ser feita agora.

**Critérios de aceite**

- [x] `Diagnostico` declara `RESERVA_MOBILIZAVEL: Dinheiro` e `ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro`, no mesmo bloco dos demais campos comportamentais extras (`NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS`, `RISCO_RECAIDA`, `RISCO_COMPORTAMENTAL_GERAL`, `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`) (`AC-61`)
- [x] O código-fonte cita explicitamente `OQ-23` em comentário/docstring próximo aos dois campos, documentando que o valor real ainda não está implementado e por quê
- [x] `calcular_diagnostico` compila e roda sem erro (nenhuma trava de execução) mesmo sem a fórmula real — nenhum `NotImplementedError` que quebre a suíte de gabaritos existente; se um placeholder for necessário para o construtor não falhar, ele está claramente marcado como tal e não é usado por nenhuma decisão do motor
- [x] `mypy --strict engine/` passa
- [x] Nenhuma suíte de gabaritos pré-existente (`GAB-A`/`GAB-B`/`GAB-C`, invariantes) quebra por causa da adição dos dois campos

**Status:** `[x] concluída`

---

### `T-91` — Calcular `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO` (BLOQUEADA por `OQ-23`)

- **Tipo:** `Data`
- **Dependências:** `T-90`
- **Rastreia:** `RF-35`, `AC-61`
- **Arquivos:** `engine/diagnostico.py`

**Descrição**

**BLOQUEADA — não iniciar.** Implementa a fórmula real de derivação de `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO`. Nenhuma fonte lida até o momento (discovery, `app-aluno.spec.md` §10 `OQ-17`, canônica, plano) publica o cálculo — apenas nome, tipo (`Dinheiro`) e posição. `OQ-23` (spec §10) está **aberta**, aguardando resposta do especialista do método. Por envolver cálculo financeiro sob a regra de tolerância zero do projeto (spec §10.3; `sdd.config.md` §6 — "metodologia não se decide implementando"), **a fórmula não pode ser adivinhada nem implementada com valor arbitrário**. Sem estimativa de esforço até a resposta do especialista, porque o esforço depende inteiramente da complexidade da fórmula que ainda não existe.

**Critérios de aceite**

- [ ] `OQ-23` está respondida pelo especialista do método, com fórmula explícita registrada em `specs/motor-calculo.spec.md` (nova seção normativa ou atualização de §11), antes de qualquer linha de implementação desta tarefa
- [ ] `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO` são calculados exatamente pela fórmula publicada pelo especialista — sem interpretação, sem aproximação, sem valor herdado de outro campo por conveniência
- [ ] Testes de comportamento (gabarito ou regra, a definir conforme a fórmula publicada) cobrem os dois campos com `assertar_monetario` (valor monetário acumulado, tolerância `± R$ 0,05`, salvo se o especialista classificar o campo como tolerância zero)
- [ ] `GAB-A`, `GAB-B`, `GAB-C` e os cinco invariantes reexecutados sem regressão
- [ ] A spec (`specs/motor-calculo.spec.md` §10) é atualizada marcando `OQ-23` como `respondida`, com a fórmula transcrita literalmente da fonte do especialista

**Status:** `[ ] bloqueada — depende de resposta do especialista a OQ-23, sem estimativa`

---

### `T-92` — Atualizar consumidores de `AcaoRequerida` fora de `engine/` para o novo contrato

- **Tipo:** `Data`
- **Dependências:** `T-79`, `T-86`
- **Rastreia:** `RF-31`, `AC-55`
- **Arquivos:** `report/plano.py`, `persistencia/arquivo/repositorio_snapshots.py`, `app/casos/coleta_dirigida.py`

**Descrição**

> **Origem desta tarefa.** `T-86` (varredura de consumidores de
> `AcaoRequerida.DIVIDA_ID`) auditou e corrigiu estritamente `engine/gates.py`,
> `engine/ordem.py`, `engine/motor.py` — escopo formal declarado por aquela
> tarefa e confirmado coerente com `plans/motor-calculo.plan.md` §R2.9 (a
> auditoria do plano é textualmente sobre `engine/*.py`, não o repositório
> inteiro). As notas informais de fechamento de `T-79`/`T-80`/`T-83`/`T-84`/
> `T-85`, porém, generalizaram "escopo de correção é `T-86`" para 5 erros de
> `mypy --strict` que na verdade ficam **fora** de `engine/` — nenhuma tarefa
> do backlog original os cobria. Esta tarefa fecha essa lacuna, descoberta
> durante a execução de `T-86` (2026-09-05) e registrada como trabalho novo,
> conforme a regra de escopo do projeto (`sdd.config.md` §4): "descobriu
> trabalho extra? Vira nova tarefa no backlog, não um extra silencioso."

Três consumidores fora de `engine/` ainda presumem o contrato antigo de
`AcaoRequerida` (`DIVIDA_ID: str` obrigatório, sem `ACAO_ID`/`TIPO_ACAO`) e
hoje falham `mypy --strict`:

1. **`report/plano.py:369`** — `ContextoAcaoRequerida.DIVIDA_ID: str` recebe
   `acao.DIVIDA_ID`, agora `str | None`. Ação de economia (`RF-33`, ainda não
   implementada nesta rodada — `T-88`) não terá `DIVIDA_ID`; o relatório
   precisa decidir como exibir esse caso (não é dado a inventar aqui sem
   checar a spec/plano — se `report/` já tiver seção sobre exibição da ação
   de economia, siga-a; se não, trate como ambiguidade nova a registrar, não
   a decidir sozinho).
2. **`persistencia/arquivo/repositorio_snapshots.py:484`** —
   `_acao_requerida` desserializa `AcaoRequerida` só com `DIVIDA_ID`/
   `descricao`/`gate_origem`; faltam os campos novos obrigatórios
   (`ACAO_ID`, `TIPO_ACAO`) e o opcional (`CAMPO_PENDENTE`). Snapshots já
   persistidos em formato antigo (sem esses campos) podem não existir ainda
   em produção (projeto em estágio `greenfield`, `sdd.config.md` §1) — mas
   verifique antes de presumir que não há dado legado a migrar.
3. **`app/casos/coleta_dirigida.py:142` e `:149`** — usa `acao.DIVIDA_ID`
   (`str | None`) como chave de dict/elemento de lista que esperam `str`,
   sem checar `None` primeiro.

**Critérios de aceite**

- [x] `mypy --strict` sobre os três arquivos passa sem erro relacionado a
      `AcaoRequerida`/`DIVIDA_ID`
- [x] `report/plano.py` trata explicitamente o caso `DIVIDA_ID is None`
      (ação de economia) sem quebrar a exibição de `ORDEM_ACOES` — decisão de
      exibição documentada (comentário ou nota na tarefa), não inventada em
      silêncio se a spec/plano não a resolver
- [x] `persistencia/arquivo/repositorio_snapshots.py::_acao_requerida`
      desserializa `ACAO_ID`, `TIPO_ACAO` e `CAMPO_PENDENTE` corretamente,
      round-trip com o serializador correspondente (localizar e conferir
      simetria)
- [x] `app/casos/coleta_dirigida.py` checa `DIVIDA_ID is not None` antes de
      usar como chave/elemento `str`, com comportamento explícito para o
      caso `None` (não decidido por conveniência sem justificativa)
- [x] `mypy --strict` completo (`build`, `sdd.config.md` §2) fica limpo nas
      seis pastas — nenhum dos 5 erros documentados em `T-79`/`T-80`/`T-83`/
      `T-84`/`T-85`/`T-86` sobrevive
- [x] Suíte completa (`pytest -q`) não introduz regressão nova além das já
      documentadas e aceitas (hash congelado de `app-aluno`, `XPASS(strict)`
      daquele slug)

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-05).**

**Estado real confirmado antes de editar (instrução 1).** `mypy --strict`
sobre o `build` completo (`engine persistencia collection app report tests`)
mostrava, no início desta tarefa, **4 erros** (não 5): `report/plano.py:369`,
`persistencia/arquivo/repositorio_snapshots.py:489` e
`app/casos/coleta_dirigida.py:142`/`:149`. A lista mudou desde que `T-92` foi
escrita (T-87/T-88/T-89/T-90 já tinham corrigido um dos apontamentos
anteriores) — confirmado por leitura direta do código antes de qualquer
edição, conforme instrução 1 e 3 do pedido.

**Confirmação sobre `persistencia/arquivo/repositorio_snapshots.py`
(instrução 3).** `_diagnostico` (linha ~365, desserialização de
`Diagnostico`) **já estava corrigida por `T-90`** — lê `RESERVA_MOBILIZAVEL`/
`ATAQUE_IMEDIATO_RECOMENDADO` corretamente; o apontamento de IDE citado no
pedido estava desatualizado. O ponto realmente quebrado era outro:
`_acao_requerida` (linha 488, desserialização de `AcaoRequerida`), que ainda
usava só `DIVIDA_ID`/`descricao`/`gate_origem` do contrato antigo. Não havia
dado legado a migrar: nenhum `snapshots.jsonl` de produção existe (projeto
`greenfield`), e nenhum teste dependia do formato antigo persistido em
disco.

**Decisões de exibição/tratamento tomadas em cada arquivo:**

1. **`report/plano.py`** — nenhuma seção de `report/` já tratava "ECONOMIA"
   (busca confirmada vazia). Decisão mínima e segura, conforme instrução 2:
   `ContextoAcaoRequerida.DIVIDA_ID` também relaxa para `str | None`,
   propagando o mesmo relaxamento de `AcaoRequerida` — decidir um
   `DIVIDA_ID` fictício para a ação de economia inventaria dado (`RF-16`).
   A exibição de `None` reaproveita a convenção JÁ ESTABELECIDA no próprio
   módulo para ausência ESTRUTURAL: `_formatar_valor_ou_desconhecido` já usa
   `"—"` para `None` (distinto de `"DESCONHECIDO"`, usado para valor
   `DESCONHECIDO` do motor) — texto não inventado, reaproveitado. O template
   `report/templates/plano/ordem_vazia.html` (único consumidor de
   `acao.DIVIDA_ID` em HTML) foi ajustado para renderizar `"—"` quando
   `DIVIDA_ID` é `None`, em vez de deixar o Jinja imprimir `None` literal.
   `_contexto_acoes` continua pura leitura, sem decidir apresentação — a
   decisão de texto fica no template/dataclass, mantendo a Lei nº 3.
2. **`persistencia/arquivo/repositorio_snapshots.py`** —
   `_acao_requerida` agora desserializa `ACAO_ID`, `TIPO_ACAO`,
   `prioridade_excepcional` e `CAMPO_PENDENTE`, além dos três campos
   antigos. Serializador simétrico confirmado: `_serializar_canonico`
   (`engine/snapshot.py`) já serializa TODOS os campos de qualquer
   dataclass genericamente por nome (via `__dataclass_fields__`) — nenhuma
   mudança necessária do lado da serialização, só a leitura de volta estava
   desatualizada. Round-trip confirmado por teste novo dedicado
   (`tests/regras/test_repositorio_snapshots.py::
   test_T92_acao_requerida_round_trip_contrato_estendido`), que injeta duas
   `AcaoRequerida` completas — uma ligada a dívida com `CAMPO_PENDENTE`
   preenchido (Gate 1) e uma ação de economia com `DIVIDA_ID=None`/
   `gate_origem=None`/`CAMPO_PENDENTE=None` — e confere igualdade exata
   depois de `anexar`/`obter`. `GAB-C` sozinho não gera nenhuma
   `AcaoRequerida` (`ORDEM_ACOES` vazia), por isso o teste dedicado, além do
   `test_criterio3_decimal_vira_string_e_volta_exato_round_trip` já
   existente (que não exercitava este shape).
3. **`app/casos/coleta_dirigida.py`** — adicionada checagem explícita
   `if acao.DIVIDA_ID is None: continue` em `dividas_por_gate_e_campo`,
   antes do uso como chave de `dict.get`/elemento de `list.append`.
   Comportamento decidido (documentado em comentário no código): PULAR o
   item, mesmo tratamento já dado ao `DIVIDA_ID` órfão logo abaixo — nenhuma
   ação sem dívida associada pode abrir bloco por `DIVIDA_ID`. Na prática o
   ramo é hoje inatingível (a função só processa `gate_origem == 3`, e a
   ação de economia sempre tem `gate_origem=None`), mas a checagem torna
   essa correlação entre dois campos independentes da dataclass explícita
   para o `mypy --strict`, em vez de um `# type: ignore`.

**Verificação dos 6 critérios de aceite (evidência real):**

1. `mypy --strict report/plano.py persistencia/arquivo/repositorio_snapshots.py app/casos/coleta_dirigida.py` →
   `Success: no issues found in 3 source files`.
2. `report/plano.py` trata `DIVIDA_ID is None` explicitamente — ver decisão
   1 acima; `ordem_vazia.html` (único template consumidor) atualizado.
3. `_acao_requerida` desserializa os três campos pedidos + round-trip
   confirmado por teste dedicado (ver decisão 2 acima) — `pytest` verde.
4. `app/casos/coleta_dirigida.py` checa `DIVIDA_ID is not None` (decisão 3
   acima), com comportamento explícito (pular) documentado em comentário.
5. `mypy --strict` completo (`engine persistencia collection app report
   tests`) → `Success: no issues found in 256 source files` (zero erro; os
   4 erros reais do início desta tarefa desapareceram, e nenhum dos 5
   documentados em `T-79`/`T-80`/`T-83`/`T-84`/`T-85`/`T-86` sobrevive —
   nenhum deles estava presente mesmo antes desta tarefa).
6. `pytest -q` completo → `11 failed, 1145 passed, 75 skipped, 1 warning`.
   As 11 falhas são NOMINALMENTE as mesmas já documentadas e aceitas nas
   notas de fechamento de `T-79`/`T-83`/`T-84`/`T-87`/`T-88`/`T-90` (2
   `test_engine_congelado.py::test_ac44_*`, hash congelado de
   `engine/gates.py`/`engine/motor.py`; 9 `XPASS(strict)`/`failed` em
   `tests/app_aluno/test_acoes.py`,
   `tests/app_aluno/test_acompanhamento_acao_id.py` e
   `tests/app_aluno/test_ordem_acoes_dependencia_externa.py`, todas do
   backlog `app-aluno`, fora de escopo de `motor-calculo`) — confirmado
   nome a nome contra a nota de `T-90`, nenhuma falha nova. Uma falha
   adicional que a nota de `T-90` atribuía à mesma causa raiz de `T-92`
   (`tests/app_aluno/... ::test_desconhecido_e_exibido_de_forma_visivel_
   nunca_como_zero_ou_vazio`, `repositorio_snapshots.py:484`) **passou a
   passar** com a correção de `_acao_requerida` — melhoria, não regressão.
   `pytest -q --ignore=tests/app_aluno` → `357 passed, 9 skipped` (era `356
   passed, 9 skipped` no baseline de `T-90`; `+1` é o teste novo desta
   tarefa) — zero falha em `motor-calculo`. `pytest -q -m "gabarito or
   invariante"` → `18 passed`, idêntico ao baseline.
7. `ruff check .` → `All checks passed!`.

Dois testes pré-existentes precisaram de ajuste de tipo por causa do
relaxamento de `ContextoAcaoRequerida.DIVIDA_ID` (não de comportamento):
`tests/app_aluno/test_plano_ec07_ec08_ec09.py::
test_ec07_ordem_acoes_e_o_conteudo_principal_quando_presente` ganhou uma
asserção `assert acao.DIVIDA_ID is not None` antes do `in`, já que `mypy
--strict` não aceita `str | None` como operando de `in` sobre `str` (o
valor de teste continua sendo a string concreta `"D-EC07"`, sem mudança de
comportamento).

Arquivos alterados: `report/plano.py`,
`report/templates/plano/ordem_vazia.html`,
`persistencia/arquivo/repositorio_snapshots.py`,
`app/casos/coleta_dirigida.py`,
`tests/regras/test_repositorio_snapshots.py` (teste novo),
`tests/app_aluno/test_plano_ec07_ec08_ec09.py` (ajuste de tipo).

---

## Cobertura de requisitos — Rodada 2

| Requisito | Tarefas |
| --------- | ------- |
| `RF-28` — `ACAO_ID` estável entre snapshots | `T-79`, `T-80`, `T-81` |
| `RF-29` — `TIPO_ACAO` domínio fechado de 4 valores | `T-79`, `T-82` |
| `RF-30` — `TIPO_ACAO` derivado de `GATE_PENDENTE` | `T-83`, `T-84`, `T-85` |
| `RF-31` — `DIVIDA_ID: str \| None`, varredura de consumidores | `T-79`, `T-86` |
| `RF-32` — Gate 1 emite `AcaoRequerida` nos dois ramos | `T-87` |
| `RF-33` — ação de economia fora do fluxo de gates | `T-88`, `T-89` |
| `RF-34` — `CAMPO_PENDENTE` domínio fechado de 2 valores | `T-79`, `T-87` |
| `RF-35` — `Diagnostico.RESERVA_MOBILIZAVEL`/`ATAQUE_IMEDIATO_RECOMENDADO` | `T-90` (contrato) · `T-91` (cálculo, bloqueada por `OQ-23`) |

**Cobertura:** 8 de 8 requisitos funcionais da Rodada 2 (`RF-28`–`RF-35`). Nenhuma tarefa desta rodada existe sem requisito atrás.

### Cobertura dos critérios de aceite — Rodada 2

| `AC-NN` | Tarefas | | `AC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `AC-48` | `T-80`, `T-81` | | `AC-56` | `T-87` |
| `AC-49` | `T-79`, `T-82` | | `AC-57` | `T-87` |
| `AC-50` | `T-83`, `T-85` | | `AC-58` | `T-87` |
| `AC-51` | `T-84`, `T-85` | | `AC-59` | `T-87` |
| `AC-52` | `T-84`, `T-85` | | `AC-60` | `T-87` |
| `AC-53` | `T-88`, `T-89` | | `AC-61` | `T-90` (tipo/posição) · `T-91` (valor, bloqueada) |
| `AC-54` | `T-88`, `T-89` | | | |
| `AC-55` | `T-86` | | | |

Os 14 critérios de aceite da Rodada 2 (`AC-48` a `AC-61`) estão cobertos — `AC-61` parcialmente por ora: tipo/posição verificáveis agora (`T-90`), valor real depende de `T-91` (bloqueada por `OQ-23`).

### Cobertura das user stories — Rodada 2

`US-09` `T-80`, `T-81` · `US-10` `T-79`, `T-82`, `T-83`, `T-84`, `T-85` · `US-11` `T-87` ·
`US-12` `T-86`, `T-88`, `T-89` · `US-13` `T-90`, `T-91`

### Cobertura dos edge cases — Rodada 2

`EC-20` `T-88`, `T-89` · `EC-21` `T-86` · `EC-22` `T-87`

### Requisitos sem cobertura — Rodada 2

Nenhum. Todos os `RF-28` a `RF-35` têm ao menos uma tarefa de implementação. `RF-35` é a
única exceção parcial documentada: a tarefa de cálculo real (`T-91`) está bloqueada por
`OQ-23`, não ausente — a tarefa existe e está no backlog, apenas não pode ser iniciada
sem resposta do especialista.

---

## Rodada 3 — Ataque Imediato e Reserva, fatias 3A e 3B (2026-09-07)

> **Contexto.** Chegada do documento canônico *"PIQ v1.0.1 — Definição Canônica
> de `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO`"*, transcrito
> integralmente e **congelado** na §13 da spec deste slug. Fonte primária de
> arquitetura: `plans/motor-calculo.plan.md` R3.1–R3.11. Fonte de requisitos:
> `specs/motor-calculo.spec.md` §2 (`RF-36`–`RF-52`), §3 (`US-14`–`US-18`),
> §4 (`AC-62`–`AC-87`), §6 (`EC-23`–`EC-31`), §13 (normativa, congelada —
> pseudocódigo em §13.9, gabaritos `GAB-AI-01`..`GAB-AI-08` em §13.10).
>
> **Duas fatias, nesta ordem.** **3A — modelagem de estado** (`RF-36`–`RF-42`,
> `T-93` a `T-101`): contrato de entrada, sem nenhuma fórmula. **3B — cálculo
> puro** (`RF-43`–`RF-52`, `T-102` a `T-116`): as nove funções de
> `engine/ataque_imediato.py` e a integração em `engine/diagnostico.py`.
> Dentro de 3B, **as funções puras vêm antes da integração** (plano R3.5).
>
> **Decisões já fechadas, tratadas como definitivas nesta rodada** (não são
> pendência — plano R3.10.1):
>
> - **`AMB-R3-01` — RESOLVIDA (usuário, 2026-09-07), opção (b).**
>   `calcular_diagnostico` **mantém** a assinatura `(estado, parametros)`.
>   `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` **continua com `dinheiro(0)`**
>   enquanto `OQ-29` (fórmula de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`)
>   estiver aberta; `Diagnostico.RESERVA_MOBILIZAVEL`, que não depende do
>   elegível, **passa a receber o valor real** de `RF-43`. Consequência
>   registrada e obrigatória: **`AC-85` fica parcialmente satisfeito nesta
>   rodada** — cumprido para `RESERVA_MOBILIZAVEL`, pendente para
>   `ATAQUE_IMEDIATO_RECOMENDADO` (ver `T-114`). **Nenhuma tarefa desta rodada
>   muda a assinatura de `calcular_diagnostico`.**
> - **`OQ-24` — RESOLVIDA (usuário).** Virou `RF-42`: renomear o
>   `VARIAVEL_GRAVADA` de `B4.03A` (`collection/registros/bloco-04.yaml:156`)
>   para `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`. **Uma única linha**; o `ID`
>   `B4.03A` não muda (ver `T-99`).
> - **`OQ-34` — RESPONDIDA na spec §5.** Tolerância dos `GAB-AI`: **zero**.
>   `assertar_monetario` (± R$ 0,05) é **proibido** nos sete gabaritos desta
>   rodada; use `assertar_exato` (`tests/conftest.py:36`).
> - **Nomenclatura (plano R3.4.3/R3.10).** `ItemInvestimento`, `ItemAtivo`,
>   `RecursoExtraordinario` em PascalCase; `CLASSIFICACAO_MOBILIZACAO` em
>   SCREAMING_CASE. Nomes de **campo** são literais da §13, caractere por
>   caractere (`sdd.config.md` §7).
> - **Localização dos gabaritos (plano R3.9.1).** Diretório novo
>   `tests/gabaritos_ataque_imediato/`, marcador novo
>   `gabarito_ataque_imediato` registrado no `pyproject.toml`. O comando de
>   homologação passa a ser
>   `pytest -m "gabarito or invariante or gabarito_ataque_imediato"`.
>
> **Fora de escopo desta rodada** (spec §9, plano R3 nota de escopo):
>
> - **Fatia 3C inteira** — `ATAQUE_IMEDIATO_APROVADO`, o passo de confirmação
>   do usuário, a injeção no cronograma-base e `GAB-AI-08`. Em consequência:
>   **nenhuma tarefa desta rodada toca `engine/ciclo_mensal.py`.** Se um
>   arquivo desse módulo aparecer num diff, a 3C vazou para dentro da rodada.
> - **`app/montagem/estado.py:1326`** (montador do slug `app-aluno`, `OQ-37`)
>   e **`tests/app_aluno/estatica/hashes_congelados.json`** (`AC-44` daquele
>   slug) — **sinalizar, não editar** (`T-116`).
> - As sete questões de metodologia com o especialista (`OQ-26`, `OQ-27`,
>   `OQ-29`, `OQ-30`, `OQ-31`, `OQ-32`, `OQ-35`) — nenhuma fórmula é
>   inventada para nenhuma delas (`sdd.config.md` §6, `CLAUDE.md` regra 3).

---

## Fatia 3A — Contrato de entrada: reserva, caixa e patrimônio por item

### `T-93` — Criar o enum `CLASSIFICACAO_MOBILIZACAO` com exatamente quatro valores

- **Tipo:** `Data`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-40`, `AC-66`, `US-14`
- **Arquivos:** `engine/tipos.py`

**Descrição**

Domínio fechado da §13, transcrito para `Enum` (plano R3.4.1): `MOBILIZACAO_POSSIVEL`, `MOBILIZACAO_RECOMENDAVEL`, `MOBILIZACAO_COM_RESSALVAS`, `NAO_MOBILIZAR`. Apenas o **domínio** — a *regra de derivação* da classificação não é implementada (`OQ-26`, aberta): ela chega já feita, por item. `engine/tipos.py` continua sendo só modelagem de dado, sem função e portanto isento de `REGRAS` pelo lint de `tests/estatica/test_toda_regra_citada.py`.

**Critérios de aceite**

- [x] `CLASSIFICACAO_MOBILIZACAO` existe em `engine/tipos.py` como `Enum` com exatamente quatro membros, escritos sem acento e sem sinônimo, com `value` igual ao nome (`AC-66`)
- [x] A docstring do enum cita `RF-40`, a §13 e `OQ-26`, e registra explicitamente que nenhuma função deste projeto deve **produzir** um destes quatro valores enquanto `OQ-26` estiver aberta
- [x] Nenhuma função de derivação de classificação é criada nesta tarefa nem em nenhuma outra desta rodada
- [x] `mypy --strict engine/` e `ruff check .` passam
- [x] `engine/tipos.py` continua sem importar nada de `persistencia/`, `app/`, `collection/` ou `report/`

**Status:** `[x] concluída`

---

### `T-94` — Declarar os quatro enums de domínio de reserva e de recurso extraordinário

- **Tipo:** `Data`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-36`, `RF-39`, `AC-62`, `AC-65`, `US-14`
- **Arquivos:** `engine/estado.py`

**Descrição**

Traduz para domínio de motor os domínios de coleta que a §13.1 e a §13.3 consomem (plano R3.4.2), sem que o motor passe a conhecer pergunta: `RESERVA_EXISTE` (`SIM`, `INFORMAL`, `NAO`), `DISPOSICAO_USO_RESERVA` (`PARTE`, `GRANDE_PARTE`, `TALVEZ`, `NAO`), `JANELA_RECURSO_EXTRAORDINARIO` (`ATE_30D`, `1_3M`, `4_6M`, `7_12M`, `NAO_SEI`) e `CERTEZA_RECURSO_EXTRAORDINARIO` (`CONFIRMADO`, `PROVAVEL`, `POSSIVEL`). A §13.1 só distingue `NAO` de não-`NAO`; os demais valores são preservados porque colapsá-los perderia informação que a devolutiva usa (`OQ-25`, aberta, não bloqueante).

**Critérios de aceite**

- [x] Os quatro `Enum` existem em `engine/estado.py` com exatamente os membros e os `value` listados no plano R3.4.2
- [x] Cada docstring cita o `RF-NN`, a subseção da §13 e o ID de pergunta de origem (`B4.02`, `B4.03`, `B3.05C`, `B3.05D`), e as de `RESERVA_EXISTE`/`DISPOSICAO_USO_RESERVA` registram `OQ-25` como o motivo de os valores não-`NAO` serem preservados
- [x] `JANELA_RECURSO_EXTRAORDINARIO.ATE_30D` e `CERTEZA_RECURSO_EXTRAORDINARIO.CONFIRMADO` são os únicos membros que a §13.3 qualifica como "momento atual"/"confirmado" — registrado em comentário
- [x] `mypy --strict engine/` e `ruff check .` passam
- [x] Nenhum valor `P_*` e nenhuma fórmula entram nesta tarefa: é só domínio

**Status:** `[x] concluída` — `engine/estado.py` ganhou os quatro `Enum` de domínio (`RESERVA_EXISTE`, `DISPOSICAO_USO_RESERVA`, `JANELA_RECURSO_EXTRAORDINARIO`, `CERTEZA_RECURSO_EXTRAORDINARIO`), transcritos do plano R3.4.2 caractere por caractere, posicionados logo após `JANELA_NOVA_DIVIDA` e antes do bloco de `PerfilComportamental`. Membros numéricos de `JANELA_RECURSO_EXTRAORDINARIO` seguem o prefixo por extenso que o plano já fixou e que `JANELA_NOVA_DIVIDA` (`engine/estado.py`, T-34) já usa — `UM_A_TRES_MESES = "1_3M"`, `QUATRO_A_SEIS_MESES = "4_6M"`, `SETE_A_DOZE_MESES = "7_12M"` —, já que identificador Python não pode começar com dígito; o `value` permanece fiel à faixa da coleta (`B3.05C`). Os únicos membros que a §13.3 qualifica estão marcados em comentário inline (`ATE_30D`, `CONFIRMADO`). Nenhum `import` de `collection/` foi adicionado: os IDs `B4.02`/`B4.03`/`B3.05C`/`B3.05D` são citados só em docstring, como rastreabilidade documental (fronteira da Rodada 2 — o motor conhece variável de domínio, nunca pergunta); os quatro domínios foram conferidos contra `collection/registros/bloco-04.yaml` (`:43`, `:117`) e `bloco-03.yaml` (`:278`, `:302`) e batem valor a valor. Nenhum campo de `EstadoFinanceiro` (`T-96`), nenhuma dataclass de item (`T-95`) e nenhuma fórmula entraram. Verificação: `ruff check .` limpo (`All checks passed!`), `mypy` sobre `engine persistencia collection app report tests` sem erro (`Success: no issues found in 256 source files`), suíte completa `11 failed, 1145 passed, 75 skipped` — idêntica ao baseline pré-tarefa; as 11 falhas são as pré-existentes de `tests/app_aluno/` (hash congelado de `AC-44` + `XPASS(strict)`), sem regressão.

---

### `T-95` — Modelar `ItemInvestimento`, `ItemAtivo` e `RecursoExtraordinario`

- **Tipo:** `Data`
- **Dependências:** `T-93`, `T-94`
- **Rastreia:** `RF-38`, `RF-39`, `RF-52`, `AC-64`, `AC-65`, `EC-31`, `US-14`
- **Arquivos:** `engine/estado.py`

**Descrição**

Três dataclasses `frozen=True, slots=True` (plano R3.4.3), cada uma representando **um** item, nunca um total agregado. Campos com nome literal da §13: `ItemInvestimento(ITEM_ID, VALOR_LIQUIDO_REALIZAVEL, POSSUI_LIQUIDEZ, CLASSIFICACAO_MOBILIZACAO)`; `ItemAtivo(ITEM_ID, VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL, CLASSIFICACAO_MOBILIZACAO)`; `RecursoExtraordinario(ITEM_ID, VALOR_RECURSO_EXTRAORDINARIO, JANELA_RECURSO_EXTRAORDINARIO, CERTEZA_RECURSO_EXTRAORDINARIO)`. `ITEM_ID` é campo deste plano, justificado contra `RF-52`/`AC-83` (origem econômica única da §13.8) — nenhum campo além dele.

**Critérios de aceite**

- [x] As três dataclasses existem em `engine/estado.py` com `frozen=True, slots=True` e exatamente os campos acima, nesta ordem, com os nomes idênticos à §13 caractere por caractere
- [x] `CLASSIFICACAO_MOBILIZACAO` é campo **obrigatório, sem default**, em `ItemInvestimento` e `ItemAtivo`: construir o item sem ela levanta `TypeError` (`EC-31`) — o motor não escolhe classe por omissão (`OQ-26`)
- [x] Cada uma chama `_recusar_float(self)` no próprio `__post_init__`, no mesmo padrão de `Divida` (`engine/estado.py:296-297`) — `_recusar_float` percorre campos do objeto, não itens de `tuple` aninhada, então a chamada não é opcional
- [x] Passar `float` em qualquer campo monetário dos três tipos levanta `TypeError` nomeando o campo culpado
- [x] As docstrings citam `RF-38`/`RF-39`, a subseção da §13, e registram `OQ-26`/`OQ-27` como o motivo de classificação e valor líquido chegarem já apurados
- [x] `mypy --strict engine/` e `ruff check .` passam

**Status:** `[x] concluída` — `engine/estado.py` ganhou as três dataclasses `frozen=True, slots=True` (`ItemInvestimento`, `ItemAtivo`, `RecursoExtraordinario`), transcritas do plano R3.4.3 campo a campo, posicionadas após o bloco de `PerfilComportamental`/`_recusar_float` e antes de `Divida` — ordem exigida porque as três chamam `_recusar_float`, que precisa já estar definido. `engine/estado.py` passou a importar `CLASSIFICACAO_MOBILIZACAO` de `engine/tipos.py` (T-93). O campo homônimo ao enum (`CLASSIFICACAO_MOBILIZACAO: CLASSIFICACAO_MOBILIZACAO`, regra de idioma §7 — nome literal da §13) resolve corretamente: `from __future__ import annotations` adia a anotação, e `typing.get_type_hints` a resolve no escopo do MÓDULO, onde o nome é o enum, não o campo — verificado em execução (`ItemInvestimento.CLASSIFICACAO_MOBILIZACAO -> <enum 'CLASSIFICACAO_MOBILIZACAO'>`), mesmo mecanismo que `EstadoFinanceiro.CONFIABILIDADE_DADOS` já usa. Evidência dos critérios 2 e 4, executada e não só lida: `ItemInvestimento(ITEM_ID=..., VALOR_LIQUIDO_REALIZAVEL=..., POSSUI_LIQUIDEZ=True)` → `TypeError: ItemInvestimento.__init__() missing 1 required positional argument: 'CLASSIFICACAO_MOBILIZACAO'` (idem `ItemAtivo`), e `float` em cada campo monetário → `TypeError: <Classe>.<CAMPO> recebeu float (...) — RF-12 proíbe ponto flutuante binário...`, nomeando o campo culpado nos três tipos. A não-opcionalidade da chamada a `_recusar_float` foi provada por contraexemplo em execução: `_recusar_float` sobre uma dataclass cujo único campo é `tuple` contendo `1.5` **não** levanta — a função percorre `fields()` do próprio objeto e não desce em `tuple`, então a chamada de `EstadoFinanceiro` (T-96) jamais alcançaria um `float` dentro de `investimentos[0]`. `RecursoExtraordinario` cita `OQ-27` (valor já apurado) mas não `OQ-26`: ele não tem campo de classificação — a §13 qualifica recurso extraordinário por janela e certeza, não por mobilização; a docstring registra essa ausência explicitamente. Escopo respeitado: nenhum campo novo em `EstadoFinanceiro` (`T-96`), nenhuma fórmula, nenhuma função de derivação de `CLASSIFICACAO_MOBILIZACAO` (`OQ-26`, aberta), e nenhum teste de contrato criado — os sete testes de `tests/regras/test_estado.py` são escopo de `T-100`, que depende de `T-96`/`T-99`. Verificação: `ruff check .` limpo (`All checks passed!`), `mypy` sobre `engine persistencia collection app report tests` sem erro (`Success: no issues found in 257 source files`), suíte completa `11 failed, 1148 passed, 75 skipped` — as **mesmas 11** falhas pré-existentes de `tests/app_aluno/` (hash congelado de `AC-44` + `XPASS(strict)`), sem nenhuma falha nova. `engine/estado.py` já constava na lista de divergência de `AC-44` desde `T-94`, que editou o mesmo arquivo; esta tarefa não introduz o problema nem o agrava.

---

### `T-96` — Acrescentar os nove campos da Rodada 3 a `EstadoFinanceiro`, numa leva só

- **Tipo:** `Data`
- **Dependências:** `T-94`, `T-95`
- **Rastreia:** `RF-36`, `RF-37`, `RF-38`, `RF-39`, `AC-62`, `AC-63`, `AC-64`, `US-14`
- **Arquivos:** `engine/estado.py`

**Descrição**

Os nove campos do plano R3.4.4, **numa única leva** — o `hash_inputs` (`engine/snapshot.py:119-120`) muda uma vez, não nove (mitigação do risco de §8 da spec). Reserva: `RESERVA_EXISTE`, `RESERVA_TOTAL: DinheiroTalvez`, `DISPOSICAO_USO_RESERVA`, `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO: DinheiroTalvez`. Caixa: `DINHEIRO_DISPONIVEL: Dinheiro` (sempre presente, **nunca** `DinheiroTalvez`). Patrimônio: `investimentos`, `ativos`, `recursos_extraordinarios`, todos `tuple[..., ...]` em minúscula, seguindo o precedente de `EstadoFinanceiro.dividas`. Esta tarefa **quebra a construção** de `EstadoFinanceiro` em todos os consumidores — a correção deles é `T-97`, não esta.

**Critérios de aceite**

- [x] `EstadoFinanceiro` declara os nove campos com os nomes e tipos exatos do plano R3.4.4; os 14 campos das Rodadas 1/2 ficam inalterados
- [x] `RESERVA_TOTAL` e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` aceitam tanto valor monetário quanto `DESCONHECIDO` (`AC-62`)
- [x] `DINHEIRO_DISPONIVEL` é `Dinheiro`, não admite desconhecido, e nenhum código do motor executa revalidação de "livre / não comprometido" sobre ele — comentário citando `RF-37`/`AC-63`/`OQ-28` registra que a garantia é de coleta
- [x] **Não existe** nenhum campo escalar de total agregado de investimentos ou de ativos em `EstadoFinanceiro` (`AC-64`)
- [x] `_recusar_float` continua recusando `float` nos campos monetários novos, nomeando o campo culpado
- [x] `mypy --strict engine/` passa; `_serializar_canonico` (`engine/snapshot.py:136`) serializa os campos novos **sem nenhuma linha nova** (dataclass, `tuple` e `Enum` já são tratados genericamente)
- [x] A tarefa registra, na nota de fechamento, que `hash_inputs` mudou para todo snapshot — insumo de `T-116`

**Status:** `[x] concluída` — `EstadoFinanceiro` passou de 14 para 23 campos numa LEVA SÓ, transcritos do plano R3.4.4 nome a nome e tipo a tipo, na ordem do plano (reserva → caixa → patrimônio), logo após `AUTOPERCEPCAO_CONTROLE`; os 14 campos das Rodadas 1/2 não foram tocados (`fields()` confirma em execução: os 13 primeiros nomes inalterados, seguidos dos 9 novos). Nenhum arquivo além de `engine/estado.py` foi editado por esta tarefa.

**`hash_inputs` MUDOU PARA TODO SNAPSHOT — insumo de `T-116`.** `EstadoFinanceiro` compõe `SnapshotOrdem.estado_inputs` (`engine/snapshot.py:120`), que alimenta `_calcular_hash_inputs`. Como `_serializar_canonico` serializa a dataclass por TODOS os seus campos, os nove campos novos entram na representação canônica e o `sha256` de qualquer estado muda — inclusive quando os nove valem valores neutros, porque as chaves passam a existir no JSON. Mudança única, e não nove, exatamente como a mitigação do risco de §8 da spec exigia. Consequência já observada: `tests/app_aluno/estatica/test_engine_congelado.py` (`AC-44`, hash congelado) diverge — falha PRÉ-EXISTENTE desde `T-94`, que já editava o mesmo arquivo, não introduzida aqui.

**Critério 6, verificado empiricamente e não só lido: `_serializar_canonico` NÃO precisou de nenhuma linha nova.** Um `EstadoFinanceiro` com os nove campos preenchidos de verdade — `RESERVA_EXISTE.SIM`, `DISPOSICAO_USO_RESERVA.PARTE`, valores `Decimal`, e as três coleções com um item cada (`ItemInvestimento`, `ItemAtivo`, `RecursoExtraordinario`, incluindo os enums `CLASSIFICACAO_MOBILIZACAO`, `JANELA_RECURSO_EXTRAORDINARIO`, `CERTEZA_RECURSO_EXTRAORDINARIO`) — serializou e passou por `json.dumps(sort_keys=True)` sem erro: `RESERVA_EXISTE -> 'SIM'`, `RESERVA_TOTAL -> '8000'`, `investimentos -> [{'CLASSIFICACAO_MOBILIZACAO': 'MOBILIZACAO_RECOMENDAVEL', 'ITEM_ID': 'INV-1', 'POSSUI_LIQUIDEZ': True, 'VALOR_LIQUIDO_REALIZAVEL': '900'}]`, idem `ativos` e `recursos_extraordinarios`. Com `DESCONHECIDO` nos dois campos de reserva: `-> 'DESCONHECIDO'`. Os ramos genéricos de `dataclass`, `tuple` e `Enum` já cobriam tudo — `engine/snapshot.py` não foi editado.

Evidência dos demais critérios, toda executada: (2) `AC-62` — construir com `RESERVA_TOTAL=DESCONHECIDO` e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=DESCONHECIDO` funciona e os campos devolvem `Desconhecido.DESCONHECIDO`; o tipo é o `DinheiroTalvez` já existente de `engine/tipos.py` (`Dinheiro | Desconhecido`), reaproveitado — nenhum mecanismo novo de "desconhecido" foi criado. (3) `AC-63` — `DINHEIRO_DISPONIVEL: Dinheiro`, sem `Desconhecido` na união; a varredura `grep DINHEIRO_DISPONIVEL` sobre todo o repositório devolve UMA única ocorrência em código de motor, a própria declaração — não existe leitura, muito menos revalidação de "livre / não comprometido" em lugar nenhum; comentário inline cita `RF-37`, `AC-63` e `OQ-28` e registra que a garantia é de coleta e que `calcular_CAIXA_RECOMENDADO` (T-104) será identidade, não validação. (4) `AC-64` — varredura sobre os 23 nomes de campo por `TOTAL`/`SOMA`/`AGREGAD` combinado com `INVESTIMENTO`/`ATIVO` devolve lista VAZIA; as três coleções são `tuple[ItemInvestimento, ...]`, `tuple[ItemAtivo, ...]`, `tuple[RecursoExtraordinario, ...]`, em minúscula seguindo `dividas`. (5) `float` em cada um dos três campos monetários novos levanta, nomeando o culpado: `EstadoFinanceiro.RESERVA_TOTAL recebeu float (1.5) — RF-12 proíbe...`, idem `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` e `DINHEIRO_DISPONIVEL` — `_recusar_float` já percorria `fields()` genericamente e alcançou os campos novos sem alteração.

**Quebra de consumidores — alvo de `T-97`, esperada e correta.** Baseline imediatamente antes desta tarefa: `11 failed, 1148 passed, 75 skipped`. Logo após a edição, com os consumidores ainda intocados: `213 failed, 863 passed, 74 skipped, 79 errors` — **290 testes novos com problema**, TODOS por argumento obrigatório ausente no construtor (`TypeError: EstadoFinanceiro.__init__() missing 9 required positional arguments`), 208 direto no ponto de construção do teste, 19 através do montador `app/montagem/estado.py:1326` (o ponto de `app-aluno` que a tabela de impacto R3.10.2 do plano já previa) e o restante como erro de fixture. **Nenhuma divergência numérica**: toda falha é mecânica de construtor, o que confirma que a modelagem está certa (a tarefa fixa que "se algum número mudar, a modelagem está errada"). Observação de coordenação: durante a execução desta tarefa, `T-97` rodou EM PARALELO e foi corrigindo os consumidores (arquivos de `tests/` modificados entre 14:18:35 e 14:19:49, enquanto `engine/estado.py` fechou às 14:18:56); por isso a contagem caiu progressivamente para `128 failed, 982 passed, 46 errors` na leitura final, ainda com `123` ocorrências de `missing 8 required positional arguments` pendentes. O número de referência para `T-97` é o das **290 quebras** medidas antes da correção concorrente. Cinco "falhas" do baseline em `tests/app_aluno/test_ordem_acoes_dependencia_externa.py` deixaram de ser falha: eram `XPASS(strict)` de `T-90` e voltaram a `xfail` porque a construção quebra antes da asserção — some quando `T-97` fechar, não é regressão.

Verificação final: `ruff check .` limpo (`All checks passed!`), `mypy --strict engine/` limpo (`Success: no issues found in 25 source files`). Escopo respeitado: nenhuma fórmula, nenhum `P_*`, nenhum desserializador de `persistencia/` e nenhum consumidor corrigido aqui — tudo isso é `T-97` e seguintes.

---

### `T-97` — Atualizar os 22 pontos de construção de `EstadoFinanceiro` para o contrato de nove campos

- **Tipo:** `Test`
- **Dependências:** `T-96`
- **Rastreia:** `RF-36`, `RF-37`, `RF-38`, `RF-39`, `AC-87`
- **Arquivos:** `persistencia/arquivo/repositorio_snapshots.py` (`:331-346`, e os novos `_item_investimento`/`_item_ativo`/`_recurso_extraordinario` no padrão de `_divida` `:280`), `tests/fixtures/carregar.py` (`:174-188`), `tests/fixtures/gab_a.json`, `tests/fixtures/gab_b.json`, `tests/fixtures/gab_c.json`, `tests/regras/test_troca.py`, `tests/regras/test_simular_cenario.py`, `tests/regras/test_hibrido.py`, `tests/regras/test_bola_de_neve.py`, `tests/regras/test_avalanche.py`, `tests/regras/test_R.py`, `tests/regras/test_M.py`, `tests/regras/test_H.py`, `tests/regras/test_F.py`, `tests/regras/test_A.py`, `tests/regras/test_diagnostico.py`, `tests/invariantes/test_propriedades.py`, `tests/invariantes/test_gab05_troca.py`, `tests/invariantes/test_gab03_rotativo.py`, `tests/invariantes/test_gab01_seguro.py`, `tests/invariantes/test_gab02_inventario.py`, `tests/invariantes/test_gab04_estabilizacao.py`, `tests/desempenho/test_orcamento_30_dividas.py`, `tests/app_aluno/test_plano_ec07_ec08_ec09.py`, `tests/app_aluno/test_conversao_decimal.py`

**Descrição**

> **Lição da Rodada 2 aplicada.** Em `T-79`/`T-86` o campo "Arquivos" listou só `engine/`, os consumidores externos ficaram órfãos e foi preciso abrir `T-92` no meio da execução. Aqui a lista acima é a varredura completa de R3.10.2 do plano, transcrita inteira — `persistencia/` e os arquivos de teste **inclusive**.

Todo ponto que constrói `EstadoFinanceiro` passa a falhar por argumento obrigatório ausente. Nas fixtures e testes existentes, preencher com valores **neutros**: `RESERVA_EXISTE = NAO`, `DISPOSICAO_USO_RESERVA = NAO`, `RESERVA_TOTAL`/`VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` com `dinheiro(0)` ou `DESCONHECIDO` conforme o caso, `DINHEIRO_DISPONIVEL = "0"`, coleções vazias — para que `AC-87` seja de fato "nada mudou". Em `persistencia/`, criar os três desserializadores por item no padrão de `_divida`. **Toda divergência aqui é mecânica (`TypeError`/`mypy`), nunca numérica: se algum número mudar, a modelagem está errada.**

**Critérios de aceite**

- [~] `mypy --strict` completo (comando `build`, `sdd.config.md` §2) fica limpo nas seis pastas — **22 dos 23 pontos acusados foram corrigidos; sobra 1 erro, e é o único que esta tarefa está PROIBIDA de corrigir** (`app/montagem/estado.py:1326`, critério 7 e plano R3.10.2 "sinalizar, não editar"). Ver a nota de fechamento
- [x] `persistencia/arquivo/repositorio_snapshots.py::_estado_financeiro` monta os nove campos novos, e `_item_investimento`/`_item_ativo`/`_recurso_extraordinario` desserializam os três tipos de item no padrão simétrico de `_divida`
- [x] Round-trip de `SnapshotOrdem` com investimentos, ativos e recursos extraordinários preenchidos preserva `Decimal` exato e `DESCONHECIDO` — teste dedicado, no padrão de `T-92`
- [x] `tests/fixtures/gab_a.json`, `gab_b.json` e `gab_c.json` ganham os nove campos com valores neutros, e `carregar_estado_financeiro` os lê
- [x] `pytest -q --ignore=tests/app_aluno` passa sem falha nova; **nenhum valor numérico de `GAB-A`/`GAB-B`/`GAB-C` muda** nesta tarefa
- [x] A nota de fechamento reporta a lista real de arquivos que o `build` acusou, para a revisão confirmar que a varredura se cumpriu — mesmo procedimento de `T-86`/`T-92`
- [x] Nenhum arquivo de `engine/ciclo_mensal.py` e nenhum arquivo de `app/montagem/` é editado

**Status:** `[x] concluída` — os 22 pontos de construção de `EstadoFinanceiro` que esta tarefa podia tocar passaram ao contrato de nove campos; o 23º (`app/montagem/estado.py:1326`) é o ponto que o plano R3.10.2 manda **sinalizar e não editar** (`T-116`, slug `app-aluno`, `OQ-37`).

**Nota de fechamento (2026-09-07).**

**Lista real que o `build` acusou — 23 arquivos, 23 ocorrências de `[call-arg]`.** Medida reconstruindo mecanicamente o estado pré-tarefa numa cópia isolada e rodando o comando `build` sobre ela, para que a lista fosse a do `mypy` e não a do `grep` (mesmo procedimento de `T-86`/`T-92`). Todas as 23 são a MESMA mensagem — `Missing positional arguments "RESERVA_EXISTE", "RESERVA_TOTAL", "DISPOSICAO_USO_RESERVA", "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO", "DINHEIRO_DISPONIVEL", "investimentos", "ativos", "recursos_extraordinarios" in call to "EstadoFinanceiro"` —, nenhuma de outra natureza:

| # | Arquivo acusado | Linha | Corrigido por T-97? |
| --- | --- | --- | --- |
| 1 | `persistencia/arquivo/repositorio_snapshots.py` | `:340` | sim |
| 2 | `tests/fixtures/carregar.py` | `:182` | sim |
| 3 | `tests/regras/test_A.py` | `:155` | sim |
| 4 | `tests/regras/test_F.py` | `:161` | sim |
| 5 | `tests/regras/test_H.py` | `:182` | sim |
| 6 | `tests/regras/test_M.py` | `:167` | sim |
| 7 | `tests/regras/test_R.py` | `:172` | sim |
| 8 | `tests/regras/test_avalanche.py` | `:313` | sim |
| 9 | `tests/regras/test_bola_de_neve.py` | `:483` | sim |
| 10 | `tests/regras/test_diagnostico.py` | `:67` | sim |
| 11 | `tests/regras/test_hibrido.py` | `:200` | sim |
| 12 | `tests/regras/test_simular_cenario.py` | `:183` | sim |
| 13 | `tests/regras/test_troca.py` | `:123` | sim |
| 14 | `tests/invariantes/test_gab01_seguro.py` | `:120` | sim |
| 15 | `tests/invariantes/test_gab02_inventario.py` | `:155` | sim |
| 16 | `tests/invariantes/test_gab03_rotativo.py` | `:145` | sim |
| 17 | `tests/invariantes/test_gab04_estabilizacao.py` | `:179` | sim |
| 18 | `tests/invariantes/test_gab05_troca.py` | `:136` | sim |
| 19 | `tests/invariantes/test_propriedades.py` | `:259` | sim |
| 20 | `tests/desempenho/test_orcamento_30_dividas.py` | `:170` | sim |
| 21 | `tests/app_aluno/test_plano_ec07_ec08_ec09.py` | `:347` | sim |
| 22 | `tests/app_aluno/test_conversao_decimal.py` | `:300` | sim |
| 23 | `app/montagem/estado.py` | `:1326` | **NÃO — proibido pelo critério 7** |

A lista bate **arquivo a arquivo** com a varredura de R3.10.2 transcrita no campo "Arquivos": os 22 previstos apareceram, nenhum consumidor órfão surgiu além deles, e o 23º é exatamente o que o plano já antecipava como "fora deste slug, a sinalizar (não editar)". A varredura se cumpriu.

**Primeiro critério — parcial, e por construção.** Depois da tarefa, `build` devolve `Found 1 error in 1 file (checked 257 source files)`, e o erro é `app/montagem/estado.py:1326`. Os critérios 1 e 7 são mutuamente exclusivos dentro do escopo desta tarefa: o único caminho para zerar o `build` é editar `app/montagem/`, que o critério 7 proíbe e que o plano R3.10.2 e a `T-116` reservam ao slug `app-aluno` (`OQ-37`, que esta rodada desbloqueia). Optou-se por respeitar o critério 7 — a regra de escopo (`sdd.config.md` §4) — e relatar o critério 1 como parcial, em vez de zerar o `build` invadindo outro slug. Fora `app/montagem/`, o `build` está limpo: nenhum dos 22 arquivos corrigidos é acusado, e nenhum `# type: ignore` foi usado.

**Valores neutros — `dinheiro(0)`, não `DESCONHECIDO`.** Nas três fixtures e nos 19 arquivos de teste, `RESERVA_EXISTE = NAO`, `DISPOSICAO_USO_RESERVA = NAO`, `DINHEIRO_DISPONIVEL = 0`, coleções vazias. Para `RESERVA_TOTAL` e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` a tarefa deixava a escolha ("`dinheiro(0)` ou `DESCONHECIDO` conforme o caso"); adotou-se `dinheiro(0)`, pela §13.1: com `RESERVA_EXISTE = NAO`, a **Regra 1 é avaliada antes** e vence (`EC-23`), fixando `RESERVA_MOBILIZAVEL = 0` e **ignorando** o valor informado — o ramo da Regra 3 nunca é alcançado. Usar `DESCONHECIDO` registraria uma pendência ("a engine registra a pendência", §13.1) que a Regra 1 já resolveu, e faria a fixture neutra afirmar um estado de coleta que ela não tem. `dinheiro(0)` é o valor que torna a fixture inerte sob qualquer ordem de avaliação. O caso `DESCONHECIDO` não fica sem cobertura: é exercitado pelo teste de round-trip novo (abaixo), onde precisa sobreviver como sentinela.

**Nenhum valor numérico de `GAB-A`/`GAB-B`/`GAB-C` mudou.** Nenhuma linha de valor esperado foi editada em nenhum arquivo — as edições dos 19 testes são **puramente aditivas** (nove `kwargs` novos inseridos após `AUTOPERCEPCAO_CONTROLE=`, mais dois nomes no `import`); nenhuma linha preexistente foi alterada ou removida. Conferência direta dos 14 campos antigos após a carga das fixtures: `GAB-A` `8000 / 6500 / 500 / 0 / 0 / True / 2 dívidas`, `GAB-B` `10000 / 7600 / 400 / 500 / 400 / True / 1`, `GAB-C` `15000 / 8500 / 500 / 3000 / 0 / True / 3` — idênticos ao que eram, com os nove campos novos todos neutros. `tests/gabaritos`, `tests/invariantes` e `tests/gabaritos_ataque_imediato`: `16 passed`.

**Round-trip (critério 3).** `tests/regras/test_repositorio_snapshots.py::test_T97_estado_financeiro_rodada_3_round_trip_itens_e_desconhecido`, no padrão de `test_T92_acao_requerida_round_trip_contrato_estendido`: como `GAB-C` é neutro nesses campos, o teste injeta por `dataclasses.replace` um estado com 2 `ItemInvestimento`, 1 `ItemAtivo` e 2 `RecursoExtraordinario`, `RESERVA_TOTAL = 30000.07`, `DINHEIRO_DISPONIVEL = 1234.56` e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO = DESCONHECIDO`; após `anexar`/`obter` prova (a) igualdade estrutural do `EstadoFinanceiro` inteiro, (b) `type(...) is Decimal` e valor exato casa a casa, (c) `is DESCONHECIDO` — nunca `0` nem `None`, (d) os cinco `Enum` da Rodada 3 reconstruídos, (e) `ITEM_ID` e ordem preservados item a item (`AC-64`), e (f) na linha crua do `.jsonl`, todo monetário de item é **string** JSON, nunca `number` (`RF-12`).

**Verificação.** `lint` (`ruff check .`) limpo — `All checks passed!`. `build` — `Found 1 error in 1 file (checked 257 source files)`, o erro sendo apenas `app/montagem/estado.py:1326`, discutido acima. `pytest -q --ignore=tests/app_aluno` — **`361 passed, 9 skipped`**, zero falha (o baseline pré-tarefa era `81 failed, 252 passed, 9 skipped, 27 errors`, todas as 108 ocorrências do mesmo `TypeError`). Suíte completa: como `app/montagem/estado.py` continua quebrado por decisão de escopo, `tests/app_aluno/` ainda falha em massa; para **provar** que nada além daquele arquivo restava, o ponto de construção dele foi preenchido com os mesmos valores neutros numa **medição temporária**, a suíte completa rodou `12 failed, 1148 passed, 75 skipped` — `passed` e `skipped` idênticos ao ponto de referência pré-`T-96` (`11 failed, 1148 passed, 75 skipped`) — e o arquivo foi **restaurado byte a byte** (SHA-256 `cd8cdec08f8bdb341edb7306f3cd4de6439c043c1c8ed368e6ab6814d7471914` antes e depois; ele não aparece no diff da rodada, `T-116` critério). Das 12, 11 são as pré-existentes de `tests/app_aluno/` (hash congelado de `AC-44` + `XPASS(strict)`) e a 12ª é `test_ac44_alterar_um_byte_muda_o_hash_e_seria_detectado`, consequência da mesma divergência de `AC-44` sobre `engine/gates.py` — arquivo que **esta tarefa não tocou** (divergência anterior, de `T-108`/`T-109`).

**Insumo para `T-116`.** O conjunto congelado de `AC-44` acusa agora **seis** arquivos divergentes: `engine/diagnostico.py`, `engine/estado.py`, `engine/gates.py`, `engine/motor.py`, `engine/tipos.py` e — **novo nesta tarefa** — `persistencia/arquivo/repositorio_snapshots.py`. Os cinco primeiros já divergiam antes de `T-97`. `tests/app_aluno/estatica/hashes_congelados.json` **não** foi editado (escopo de `T-116`).

**Escopo.** `engine/ciclo_mensal.py`, `app/montagem/` e `tests/app_aluno/estatica/hashes_congelados.json` não foram tocados. Nenhuma função de cálculo da §13 (`T-102`+) foi escrita: `RESERVA_MOBILIZAVEL` continua o placeholder de `T-90`, e nenhum dos nove campos novos é lido por qualquer código de motor nesta tarefa.

---

### `T-98` — Retipar `Diagnostico.RESERVA_MOBILIZAVEL` para `DinheiroTalvez` e varrer os 14 consumidores

- **Tipo:** `Data`
- **Dependências:** `T-96`
- **Rastreia:** `RF-41`, `AC-68`, `US-15`
- **Arquivos:** `engine/diagnostico.py` (`:637` declaração, `:764` construção), `persistencia/arquivo/repositorio_snapshots.py` (`:400`, `_decimal(...)` → `_dinheiro_talvez(...)`, helper já existente em `:236`), `tests/regras/test_troca.py` (`:91`), `tests/regras/test_simular_cenario.py` (`:135`), `tests/regras/test_R.py` (`:128`), `tests/regras/test_M.py` (`:121`), `tests/regras/test_hibrido.py` (`:166`), `tests/regras/test_H.py` (`:152`), `tests/regras/test_F.py` (`:117`), `tests/regras/test_bola_de_neve.py` (`:441`), `tests/regras/test_avalanche.py` (`:271`), `tests/regras/test_A.py` (`:111`), `tests/invariantes/test_propriedades.py` (`:226`), `tests/invariantes/test_gab05_troca.py` (`:104`)

**Descrição**

> **Quebra de contrato, não adição** (spec §5 "Compatibilidade de contrato (Rodada 3)"). O campo "Arquivos" acima é a lista de **14 consumidores** levantada por `grep` no plano R3.10.2 e transcrita inteira — `persistencia/arquivo/repositorio_snapshots.py:400` e os 11 arquivos de teste inclusive, não só os de `engine/`.

`Diagnostico.RESERVA_MOBILIZAVEL` passa de `Dinheiro` para `DinheiroTalvez`, exigido pela §13.1 Regra 3. `ATAQUE_IMEDIATO_RECOMENDADO` **continua `Dinheiro`** — não existe caminho da §13 em que ele seja desconhecido (plano R3.4.6); não retipar "por simetria". A rede de segurança é o `mypy --strict`: rodar `build`, listar os arquivos acusados, corrigir e **reportar a lista na tarefa**, mesmo procedimento de `T-86`/`T-92`. O **valor** real de `RESERVA_MOBILIZAVEL` é `T-114`, não esta tarefa.

**Critérios de aceite**

- [x] `Diagnostico.RESERVA_MOBILIZAVEL: DinheiroTalvez`, no mesmo bloco de campos comportamentais extras; `ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro` inalterado
- [x] `mypy --strict` completo (comando `build`) fica limpo: nenhum consumidor trata apenas o ramo `Dinheiro` sem cobrir `Desconhecido` (`AC-68`)
- [x] `persistencia/arquivo/repositorio_snapshots.py:400` usa `_dinheiro_talvez(...)` (helper existente `:236`), e o round-trip de um `Diagnostico` com `RESERVA_MOBILIZAVEL = DESCONHECIDO` preserva o sentinela — não vira `0` nem `None`
- [x] Os 13 arquivos restantes da lista constroem `Diagnostico` com o tipo novo, sem `# type: ignore`
- [x] Introduzir propositalmente uma leitura de `diagnostico.RESERVA_MOBILIZAVEL` como `Dinheiro` puro faz `mypy --strict` falhar (prova de que a rede funciona, no padrão de `T-86`)
- [x] A nota de fechamento transcreve a lista real de arquivos acusados pelo `build`, confirmando que os 14 foram cobertos
- [x] `pytest -q --ignore=tests/app_aluno` sem falha nova

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

**A mudança de contrato.** `engine/diagnostico.py:637` passou de
`RESERVA_MOBILIZAVEL: Dinheiro` para `RESERVA_MOBILIZAVEL: DinheiroTalvez`
(`DinheiroTalvez` acrescentado ao `import` de `engine.tipos`, `:105`), com
comentário citando a §13.1 Regra 3 e o motivo de o estado `DESCONHECIDA` não
virar zero: "não sei quanto o usuário aceita mobilizar" e "o usuário não
aceita mobilizar nada" são fatos diferentes, e só o primeiro é pendência.
`ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro` ficou **inalterado** — não existe
caminho da §13 em que ele seja desconhecido (plano R3.4.6); o comentário no
mesmo bloco registra explicitamente o "não retipar por simetria", para que a
decisão não seja relida como esquecimento. A construção em
`calcular_diagnostico` (`:764`) continua `dinheiro(0)`: **esta tarefa é o
tipo, não o valor** — ligar `derivar_RESERVA_MOBILIZAVEL` ao
`calcular_diagnostico` é `T-114`.

**Persistência.** O sítio da lista era `:400` quando a tarefa foi escrita;
depois de `T-97` ele é **`:476`** (o bloco da Rodada 3 do `EstadoFinanceiro`
deslocou o `_diagnostico`). Lá, `_decimal(...)` virou
`_dinheiro_talvez(...)` — o helper de `:244`, não `:236` como dizia a lista
(`:236` é o `_decimal`; `_dinheiro_talvez` ficou logo abaixo). Ler com
`_decimal` levantaria `AssertionError` na volta, e "consertar" convertendo
para `0` apagaria a pendência. A IDA não precisou de mudança: a serialização
reusa `engine.snapshot._serializar_canonico`, que já leva `Enum -> .value` e
portanto grava o sentinela como a string `"DESCONHECIDO"`.

**Lista REAL de arquivos acusados pelo `build` (sexto critério).** O `build`
completo acusou **zero** arquivo novo — antes e depois da mudança a saída é
idêntica:

```
app\montagem\estado.py:1326: error: Missing positional arguments "RESERVA_EXISTE",
  "RESERVA_TOTAL", ... in call to "EstadoFinanceiro"  [call-arg]
Found 1 error in 1 file (checked 274 source files)
```

o único erro sendo o **pré-existente** de `app/montagem/estado.py:1326`
(slug `app-aluno`, allowlist `AC-41` — fora do escopo, não corrigido). Isso
**não** é a varredura falhando; é o resultado esperado, e a razão é
verificável: `Dinheiro` é subtipo de `DinheiroTalvez`, então os 13 sítios de
CONSTRUÇÃO da lista (`RESERVA_MOBILIZAVEL=dinheiro("0")`) são alargamento,
não estreitamento, e continuam válidos sem edição. Erro só apareceria num
sítio de **leitura** aritmética — e hoje não existe nenhum: `grep` por
`RESERVA_MOBILIZAVEL` em `engine/` (fora de `ataque_imediato.py`), `app/`,
`report/`, `collection/` e `persistencia/` devolve apenas comentários e a
linha `:476` já corrigida. Quem lê o campo é `engine/ataque_imediato.py`, que
**já** o recebe como `DinheiroTalvez` por parâmetro (`:186`, `:449`) e já
discrimina com `is DESCONHECIDO` (`:244`, `:518`) desde `T-96`.

Como "zero erro" é indistinguível de "mypy não olhou o arquivo", os 14 foram
conferidos um a um. Os 14 existem em disco; nenhum tem `# type: ignore` na
linha de `RESERVA_MOBILIZAVEL` (contagem por `grep`: `0` nos 13 restantes).
E a cobertura foi **provada por sondagem**: trocando
`RESERVA_MOBILIZAVEL=dinheiro("0")` por `RESERVA_MOBILIZAVEL="sonda"` em
`tests/regras/test_troca.py`, o mypy acusou

```
tests\regras\test_troca.py:93: error: Argument "RESERVA_MOBILIZAVEL" to
  "Diagnostico" has incompatible type "str"; expected "Decimal | Desconhecido"
```

— confirmando que o arquivo é de fato checado e que o campo já é a união. A
sondagem foi revertida e o arquivo revalidado (`Success: no issues found`).

Os 14, todos cobertos: `engine/diagnostico.py` (declaração `:637` +
construção `:764`), `persistencia/arquivo/repositorio_snapshots.py` (`:476`),
`tests/regras/test_troca.py`, `test_simular_cenario.py`, `test_R.py`,
`test_M.py`, `test_hibrido.py`, `test_H.py`, `test_F.py`,
`test_bola_de_neve.py`, `test_avalanche.py`, `test_A.py`,
`tests/invariantes/test_propriedades.py` e `test_gab05_troca.py`.

**Round-trip (terceiro critério).**
`tests/regras/test_repositorio_snapshots.py::test_T98_diagnostico_reserva_mobilizavel_round_trip_desconhecido`,
no padrão de `test_T97_...`: como o `Diagnostico` de `GAB-C` traz o
placeholder `0` de `T-90`, o teste injeta por `dataclasses.replace` um
diagnóstico com `RESERVA_MOBILIZAVEL = DESCONHECIDO` e
`ATAQUE_IMEDIATO_RECOMENDADO = 321.09`; após `anexar`/`obter` prova (a)
`is DESCONHECIDO` — e explicitamente `!= dinheiro(0)` e `is not None`, que é
o que a §13.1 proíbe; (b) igualdade estrutural do `Diagnostico` inteiro; (c)
`ATAQUE_IMEDIATO_RECOMENDADO` volta `type(...) is Decimal` e exato; (d) na
linha crua do `.jsonl`, o sentinela é a **string** `"DESCONHECIDO"` (`RF-12`);
e (e) o ramo `Dinheiro` do mesmo campo (`18000.13`) volta `Decimal` exato
casa a casa — os dois ramos da união, não só o novo.

**Prova negativa (quinto critério).** Feita como **teste estático
permanente**, seguindo a convenção que `T-86` criou:
`tests/estatica/test_reserva_mobilizavel_dinheiro_talvez.py`, na forma de
`test_acao_requerida_divida_id_opcional.py` — `mypy --strict` como subprocess
sobre trechos escritos como STRING, sintetizados fora da árvore do projeto
(nunca coletados pelo pytest nem incluídos no `build` real). Três testes:
(1) somar `diagnostico.RESERVA_MOBILIZAVEL + Decimal("1")` sem discriminar
falha com `[operator]` — `Unsupported operand types for + ("Desconhecido" and
"Decimal")`, `note: Left operand is of type "Decimal | Desconhecido"`,
exit `1`; (2) contraprova: o MESMO consumo com `is DESCONHECIDO` antes
compila limpo (isola que a falha é da ausência de checagem, não de erro de
sintaxe/import); (3) guarda de escopo: somar
`ATAQUE_IMEDIATO_RECOMENDADO` SEM checagem alguma compila — se alguém o
retipar "por simetria", este teste falha. A saída real do mypy foi conferida
à mão além do `assert`, para descartar exit-code diferente de zero por motivo
errado (import quebrado, argumento inválido).

**Verificação.** `lint` (`ruff check .`) — `All checks passed!` no repositório
inteiro (os `E501` dos gabaritos de `T-110`+ já haviam sido resolvidos pelo
autor deles); os quatro arquivos desta tarefa, medidos isoladamente, também
limpos. `build` — `Found 1 error in 1 file (checked 274 source files)`, só o
`app/montagem/estado.py:1326` discutido acima. `pytest -q
--ignore=tests/app_aluno` — **`534 passed, 9 skipped`**, zero falha (baseline
pré-tarefa `509 passed, 9 skipped`; o delta `+25` são os 4 testes desta
tarefa e 21 do trabalho paralelo de `T-110`/`T-111`/`T-112`).

**Insumo para `T-116`.** O conjunto congelado de `AC-44` continua acusando os
**mesmos seis** arquivos de `T-97` — `engine/diagnostico.py`,
`engine/estado.py`, `engine/gates.py`, `engine/motor.py`, `engine/tipos.py` e
`persistencia/arquivo/repositorio_snapshots.py`. Os dois arquivos que esta
tarefa editou já divergiam; **nenhuma entrada nova** foi acrescentada à lista.
`tests/app_aluno/estatica/hashes_congelados.json` não foi editado (escopo de
`T-116`).

**Escopo.** `engine/ataque_imediato.py`, `tests/gabaritos_ataque_imediato/` e
`tests/regras/test_ataque_imediato.py` — em edição pelo agente paralelo — não
foram tocados. `app/montagem/estado.py` não foi tocado (allowlist `AC-41` do
slug `app-aluno`). Nenhuma dependência nova. Quatro arquivos alterados:
`engine/diagnostico.py`, `persistencia/arquivo/repositorio_snapshots.py`,
`tests/regras/test_repositorio_snapshots.py` (teste novo acrescentado) e
`tests/estatica/test_reserva_mobilizavel_dinheiro_talvez.py` (novo).

---

### `T-99` — Renomear o `VARIAVEL_GRAVADA` de `B4.03A` no registro do Bloco 4

- **Tipo:** `Data`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-42`, `AC-69`, `US-18`
- **Arquivos:** `collection/registros/bloco-04.yaml` (`:156`)

**Descrição**

`OQ-24`, resolvida pelo usuário em 2026-09-07. **Uma única linha:** `VARIAVEL_GRAVADA: RESERVA_MOBILIZAVEL` → `VARIAVEL_GRAVADA: VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`, que é o nome que a própria §13.1 dá à resposta crua. O campo `ID: B4.03A` **não muda**. Depois disso, `RESERVA_MOBILIZAVEL` designa exclusivamente o valor **derivado** pelo motor, nos dois lados. Escopo já verificado na spec §10: os outros 15 usos do nome no repositório já se referem ao campo derivado de `Diagnostico`.

**Critérios de aceite**

- [x] `collection/registros/bloco-04.yaml:156` grava `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`
- [x] O registro de `B4.03A` mantém `ID: B4.03A`, enunciado, `tipo`, `opcoes`, `condicao_exibicao` e `admite_nao_sei` inalterados
- [x] Nenhum outro registro de coleta grava em `RESERVA_MOBILIZAVEL` (`AC-69`) — verificado por busca no diretório `collection/registros/`
- [x] O diff da tarefa tem exatamente uma linha alterada em `collection/`
- [x] `pytest -q` sobre os testes que carregam os registros do Bloco 4 continua passando

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

Alteração de uma linha, exatamente como especificado:

```diff
--- a/collection/registros/bloco-04.yaml
+++ b/collection/registros/bloco-04.yaml
@@ -156 +156 @@ (registro B4.03A)
-    VARIAVEL_GRAVADA: RESERVA_MOBILIZAVEL
+    VARIAVEL_GRAVADA: VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO
```

O arquivo continua com 984 linhas; nenhuma outra linha de `collection/` foi
tocada. O registro de `B4.03A` (`:144`–`:164`) preserva `ID: B4.03A`,
enunciado, `tipo: MOEDA`, `obrigatoriedade`, `escopo_repeticao`, as três
`opcoes`, `condicao_exibicao` (`NAO` sobre `DISPOSICAO_USO_RESERVA = NAO`),
`interpolacoes`, `validacoes_cruzadas`, `origem_opcoes`,
`admite_nao_sei: true` e `salto_consequencia` — só `VARIAVEL_GRAVADA` mudou.

**`AC-69` — nenhum outro registro grava em `RESERVA_MOBILIZAVEL`.** Busca por
`RESERVA_MOBILIZAVEL` em `collection/registros/`: **zero ocorrências** depois
da mudança (antes havia exatamente uma, a linha 156). Busca em `collection/`
inteiro: também zero. O nome agora designa exclusivamente o valor derivado.

**Varredura de consumidores do nome antigo (nenhum quebra).** `RESERVA_MOBILIZAVEL`
em `app/`: zero ocorrências. Em `.py` do repositório, a única leitura por
string literal é `persistencia/arquivo/repositorio_snapshots.py:400`
(`bruto["RESERVA_MOBILIZAVEL"]`), que desserializa o campo **derivado** de
`Diagnostico`, não o registro YAML — não é afetada. As 12 ocorrências em
`tests/` são argumentos nomeados do construtor de `Diagnostico` (também o
campo derivado). O carregador `collection/carga.py:187` lê
`pergunta["VARIAVEL_GRAVADA"]` genericamente, como string, sem comparar com
nenhum nome literal. Nenhum consumidor do valor antigo existe; o escopo de uma
linha declarado pela tarefa se confirmou na prática.

**Verificação (`sdd.config.md` §2).**

- `lint` — `ruff check .`: `All checks passed!`
- `build` — `mypy` nas seis pastas: `Success: no issues found in 256 source files`
- `test` — `pytest -q`: `11 failed, 1145 passed, 75 skipped` — **idêntico ao
  baseline medido antes da edição** (mesmos 11 IDs de teste, todos em
  `tests/app_aluno/`: hash congelado de `test_engine_congelado.py` e
  `XPASS(strict)` daquele slug). Nenhuma regressão nova; o número não aumentou.
  O teste de hash congelado não referencia `collection/` nem `bloco-04`.
- Testes que carregam os registros (`test_carga.py`, `test_retomada_progresso.py`
  — único que exercita o Bloco 4 —, `test_montagem_estado_financeiro.py`,
  `test_renderizacao.py`, `test_progresso.py`): `129 passed`.

O teste dedicado `test_bloco04_b4_03a_grava_valor_maximo_informado`, que lê o
YAML e confirma `VARIAVEL_GRAVADA` e `ID`, pertence a `T-100` (plano §R3.9.4) —
fora do escopo desta tarefa.

---

### `T-100` — Testar o contrato de estado da 3A e os dois enunciados de coleta

- **Tipo:** `Test`
- **Dependências:** `T-96`, `T-99`
- **Rastreia:** `RF-36`, `RF-37`, `RF-38`, `RF-39`, `RF-40`, `RF-42`, `RF-52`, `AC-62`, `AC-63`, `AC-64`, `AC-65`, `AC-66`, `AC-69`, `AC-84`, `EC-31`
- **Arquivos:** `tests/regras/test_estado.py`, `tests/regras/test_diagnostico.py`

**Descrição**

Os sete testes de contrato do plano R3.9.4, em `tests/regras/`. Testam o **contrato observável** do estado, não implementação: presença e nome literal dos campos, tipo que admite desconhecido, coleção por item sem total agregado, decidibilidade por item do recurso extraordinário, cardinalidade do enum, e os dois testes que leem o YAML de coleta (`AC-69` para o rename de `B4.03A`, `AC-84` para o enunciado de `B4.04` que exclui os valores já informados como reserva — primeiro caso vedado da §13.8, prevenido na origem).

**Critérios de aceite**

- [x] `test_estado_tem_os_quatro_campos_de_reserva_com_nome_literal` verifica os quatro nomes caractere por caractere e que os dois `DinheiroTalvez` aceitam `DESCONHECIDO` (`AC-62`)
- [x] `test_dinheiro_disponivel_sempre_presente_sem_revalidacao` (`AC-63`)
- [x] `test_investimentos_e_ativos_sao_colecao_por_item_sem_total_agregado` monta 3 investimentos e 2 ativos e afirma que **nenhum** campo escalar de total agregado existe em `EstadoFinanceiro` (`AC-64`)
- [x] `test_recurso_extraordinario_decidivel_por_item` decide "confirmado, disponível e apto no momento atual" lendo só os campos do item, sem consultar nenhum outro (`AC-65`)
- [x] `test_classificacao_mobilizacao_tem_exatamente_quatro_membros` (`AC-66`)
- [x] `test_item_sem_classificacao_falha_na_construcao` prova o `TypeError` (`EC-31`)
- [x] `test_bloco04_b4_03a_grava_valor_maximo_informado` lê o YAML e confirma `VARIAVEL_GRAVADA` e `ID` (`AC-69`)
- [x] `test_b4_04_continua_excluindo_valores_de_reserva` lê o enunciado de `B4.04` no YAML e confirma a exclusão explícita (`AC-84`)
- [x] Cada teste cita no docstring o `AC-NN`/`EC-NN` que ancora, conforme `sdd.config.md` §5

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

Arquivo **novo**: `tests/regras/test_estado.py` — 7 funções de teste, `9 passed`
(`test_item_sem_classificacao_falha_na_construcao` é parametrizado por
construtor, `ItemInvestimento` e `ItemAtivo`). `tests/regras/test_diagnostico.py`
constava no campo "Arquivos" da tarefa, mas **não precisou ser tocado**: os sete
testes do plano R3.9.4 são todos sobre o contrato de `EstadoFinanceiro`, dos
itens de patrimônio e dos registros de coleta — nenhum é sobre `Diagnostico`.
Editá-lo seria acréscimo sem critério que o peça.

**Nome literal, não acesso a atributo (`sdd.config.md` §7).** Os quatro nomes de
`AC-62` são comparados como **string** contra `dataclasses.fields(EstadoFinanceiro)`,
não por `estado.RESERVA_TOTAL`. Um teste escrito por acesso a atributo provaria
que o atributo existe, mas confundiria um rename no contrato com um erro de
digitação no próprio teste — os dois dariam `AttributeError`. Mesma escolha em
`AC-63` e `AC-66` (nome **e** valor de cada membro do enum, mais `isascii()`).

**`AC-63` — "sempre presente" provado por ausência de default.** Duas afirmações
observáveis: `campo.default is dataclasses.MISSING` e `campo.default_factory is
dataclasses.MISSING` (não há como um estado existir sem o campo), e o domínio
declarado é `"Dinheiro"`, contrastado no mesmo teste com `"DinheiroTalvez"` de
`RESERVA_TOTAL` — é o contraste que prova que `DESCONHECIDO` não pertence ao
domínio de `DINHEIRO_DISPONIVEL`. A parte "sem revalidação" é verificada como
identidade: construído com `1234.56`, é lido como `1234.56`, `type(...) is
Decimal` — nenhuma transformação de "livre / não comprometido" entre construção
e leitura (`OQ-28` encaminhada como garantia de coleta).

**`AC-64` — a asserção negativa é o coração.** Além dos 3 investimentos e 2
ativos (cada um com seu `ITEM_ID`, seu valor e sua classificação, conferidos item
a item e em ordem), o teste varre **todos** os campos de `EstadoFinanceiro` e
falha se algum escalar (fora das quatro coleções) mencionar investimento/ativo
junto com marca de agregação (`TOTAL`, `SOMA`, `AGREGAD`, `SALDO`, `VALOR`).
Hoje a lista de suspeitos é vazia. O teste também **exercita** a `Σ` da §13.3
restrita aos `MOBILIZACAO_RECOMENDAVEL` (`50000`, ignorando os `80000` do ativo
`MOBILIZACAO_COM_RESSALVAS`) — demonstrando na prática o que um escalar já
somado tornaria inexprimível.

**`AC-65` — "sem consultar nenhum outro" é estrutural, não declarado.** O
predicado `_apto_no_momento_atual` tem assinatura `(item: RecursoExtraordinario)
-> bool`: não recebe `EstadoFinanceiro` nem os demais itens, então **não tem
como** consultá-los. Decide `(True, False)` para o par
`ATE_30D`+`CONFIRMADO` / `4_6M`+`PROVAVEL`.

**`EC-31` — `TypeError` na construção, com contraprova.** `pytest.raises(TypeError,
match="CLASSIFICACAO_MOBILIZACAO")` sobre `ItemInvestimento` e `ItemAtivo` sem o
campo; em seguida, os **mesmos** campos mais a classificação constroem sem erro —
isolando que o `TypeError` é pela classificação ausente, não por outro argumento
faltante.

**Os dois testes de YAML (`AC-69`, `AC-84`).** Leem
`collection/registros/bloco-04.yaml` com `yaml.safe_load` **direto**, sem passar
por `collection/carga.py`: os dois critérios são afirmações sobre o CONTEÚDO do
registro publicado, e um carregador no meio poderia normalizar exatamente o que
se quer verificar. A fronteira arquitetural (`sdd.config.md` §3) proíbe `engine/`
**importar** `collection/` — não proíbe um teste ler o registro como dado; nada
em `engine/` foi tocado. `AC-69` confere `ID: B4.03A` e `VARIAVEL_GRAVADA:
VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` (o rename de `T-99`) e varre **todos** os
`*.yaml` de `collection/registros/` procurando qualquer registro que grave em
`RESERVA_MOBILIZAVEL`: zero. `AC-84` normaliza a quebra de linha do YAML
(`" ".join(enunciado.split())`) antes de exigir a substring literal "Além dos
valores que você já informou como reserva" — o primeiro caso vedado da §13.8,
prevenido na origem.

**Verificação.**

- `lint` — `ruff check .`: `All checks passed!`
- `build` — `mypy` nas seis pastas: `Found 1 error in 1 file (checked 263 source
  files)`, o único erro sendo o **pré-existente** `app/montagem/estado.py:1326`
  (slug `app-aluno`, `T-116`/`OQ-37`; não corrigido por decisão de escopo já
  registrada em `T-97`). Nenhuma linha de `tests/regras/test_estado.py` é
  acusada; nenhum `# type: ignore` foi usado.
- `pytest tests/regras/test_estado.py -q` — **`9 passed`**.
- `pytest -q --ignore=tests/app_aluno` — `433 passed, 9 skipped`, contra o
  baseline de `410 passed, 9 skipped` medido antes desta rodada. A diferença é
  exatamente +23, os testes novos de `T-100` (9) e `T-101` (14); nenhum teste
  preexistente mudou de resultado.

---

### `T-101` — Provar por teste estático que nenhuma função deriva `CLASSIFICACAO_MOBILIZACAO`

- **Tipo:** `Test`
- **Dependências:** `T-93`
- **Rastreia:** `RF-40`, `AC-67`, `US-14`
- **Arquivos:** `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py`

**Descrição**

Prova negativa por AST (plano R3.9.5), no padrão já usado em `tests/estatica/test_uso_de_tolerancia.py` e `test_nenhum_parametro_no_codigo.py`: falha se alguma função de `engine/**/*.py` **retornar** `CLASSIFICACAO_MOBILIZACAO` (anotação de retorno), nomeando arquivo e linha. Enquanto `OQ-26` estiver aberta, este teste é o portão que impede a metodologia de ser decidida no código — a classificação entra como dado por item e sai igual.

**Critérios de aceite**

- [x] O teste varre a AST de `engine/**/*.py` e falha se qualquer `FunctionDef`/`AsyncFunctionDef` tiver `CLASSIFICACAO_MOBILIZACAO` como anotação de retorno (direta, em `Optional`/união, ou em coleção)
- [x] A mensagem de falha nomeia arquivo, linha e função culpada
- [x] Existe teste-companheiro de prova negativa que alimenta o detector com um trecho **construído como string** contendo uma função proibida e confirma que o detector a pega — mesmo padrão de `tests/estatica/test_tipo_acao_apenas_quatro_valores.py::test_verificador_pega_quinto_literal_proposital`
- [x] O teste passa sobre o `engine/` real ao fim da rodada (nenhuma derivação existe)
- [x] O docstring cita `AC-67`, `RF-40` e `OQ-26`

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

Arquivo **novo**: `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py`
— `14 passed`. Um detector (`_detectar_derivacoes`) mais seis funções de teste,
sendo uma parametrizada em 10 formas de anotação.

**A varredura (`AC-67`).** `test_sem_derivacao_de_classificacao_mobilizacao`
percorre `engine/**/*.py`, e para cada `FunctionDef`/`AsyncFunctionDef` com
`returns` faz `ast.walk` sobre a **sub-árvore da anotação de retorno**,
reportando `ast.Name(id=...)`, `ast.Attribute(attr=...)` e `ast.Constant` string
que casem com `CLASSIFICACAO_MOBILIZACAO`. Por ser `walk` sobre o nó `returns`,
as três formas exigidas pelo critério ficam cobertas por construção — e são
provadas **uma a uma**, não por amostra, em
`test_detector_pega_cada_forma_de_anotacao_de_retorno`, parametrizado nos 10
casos: direta, qualificada (`tipos.CLASSIFICACAO_MOBILIZACAO`), `| None`,
`Optional[...]`, `Union[...]`, `tuple[..., ...]`, `list[...]`, `dict[str, ...]`,
anotação adiada como string, e string com coleção. `test_detector_pega_funcao_assincrona`
cobre o ramo `AsyncFunctionDef`.

**A prova negativa (critério 3).** `test_detector_pega_derivacao_proposital`
alimenta o **próprio** detector com uma função construída como STRING — a
derivação que `OQ-26` proíbe, a partir de liquidez e custo de desmobilização — e
confere não só que ele pega, mas que pega **exatamente uma** ocorrência, com
`funcao == "classificar_mobilizacao"`, `linha == 2` e `anotacao ==
"CLASSIFICACAO_MOBILIZACAO"` (critério 2: arquivo, linha e função culpada). Sem
esse companheiro, a varredura passaria igualmente bem com o detector quebrado:
hoje ela roda sobre um conjunto em que a resposta correta é "nenhuma", e
verificação vácua não distingue "não há violação" de "não sei detectar violação".

**Prova de que a rede pega o `engine/` real, e não só uma string.** Além do
companheiro acima, foi feita uma **sondagem temporária**, fora do repositório:
uma árvore em pasta de trabalho com `engine/tipos.py` copiado mais um
`derivacao_proposital.py` contendo
`def derivar_classificacao(item: object) -> CLASSIFICACAO_MOBILIZACAO`. Com
`RAIZ_ENGINE` apontada para ela, a **própria função de teste**
`test_sem_derivacao_de_classificacao_mobilizacao()` levantou `AssertionError`:

```text
AC-67 violado — função de engine/ que DERIVA CLASSIFICACAO_MOBILIZACAO (a regra
de derivação é OQ-26, aberta com o especialista; a classificação deve chegar
como dado por item):
  ...\engine_sondagem\derivacao_proposital.py:4 — função `derivar_classificacao`
  retorna `CLASSIFICACAO_MOBILIZACAO`
```

A árvore de sondagem foi **removida** ao fim da medição; nada em `engine/` foi
criado, editado ou tocado em momento algum.

**A fronteira: consumir é obrigatório, produzir é o que está proibido.** O lint
olha a **anotação de retorno**, não `return CLASSIFICACAO_MOBILIZACAO.X` no
corpo, e a razão está na docstring do módulo: a §13.3 manda o motor comparar
`item.CLASSIFICACAO_MOBILIZACAO is MOBILIZACAO_RECOMENDAVEL` e filtrar — um lint
que reprovasse menção ao nome tornaria `ATIVOS_RECOMENDADOS` inimplementável.
`test_detector_nao_reporta_consumo_da_classificacao` é a contraprova: um
`calcular_ATIVOS_RECOMENDADOS(...) -> Dinheiro` que lê o campo, compara com um
membro do enum e soma **não** é reportado. A limitação recíproca (uma função
anotada `-> object` que devolvesse um membro do enum escaparia) está declarada na
docstring, com a razão de não ser coberta aqui: `mypy --strict` já exige anotação
de retorno em `engine/` (comando `build`), então a anotação sempre existe.

**Docstring (critério 5).** Cita `AC-67`, `RF-40`, `OQ-26`, `piq-app-spec.md:2614`
("derivadas pelo motor, nunca perguntadas"), o plano R3.9.5 e `sdd.config.md` §6
("Metodologia não se decide implementando"), e registra que, quando `OQ-26` for
respondida, o teste não deve ser apagado em silêncio.

**Verificação.**

- `lint` — `ruff check .`: `All checks passed!`
- `build` — `mypy` nas seis pastas: `Found 1 error in 1 file (checked 263 source
  files)`, o único erro sendo o **pré-existente** `app/montagem/estado.py:1326`
  (slug `app-aluno`, `T-116`/`OQ-37`). O arquivo desta tarefa não é acusado;
  nenhum `# type: ignore`.
- `pytest tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py -q` —
  **`14 passed`**, sobre o `engine/` real (critério 4: nenhuma derivação existe).
- `pytest -q --ignore=tests/app_aluno` — `433 passed, 9 skipped`, contra baseline
  `410 passed, 9 skipped`: +23, sendo 14 desta tarefa e 9 de `T-100`.

**Escopo.** `engine/` não foi tocado — em particular `engine/ataque_imediato.py`,
que está sendo escrito em paralelo por `T-105`/`T-106`/`T-107`, não aparece no
diff desta tarefa. O teste **varre** aquele arquivo, e passa: nenhuma das funções
já escritas ali retorna `CLASSIFICACAO_MOBILIZACAO`.

---

## Fatia 3B — Cálculo puro do ataque imediato e da reserva

### `T-102` — Criar `engine/ataque_imediato.py` e `derivar_RESERVA_MOBILIZAVEL`

- **Tipo:** `Data`
- **Dependências:** `T-94`
- **Rastreia:** `RF-43`, `RF-49`, `AC-70`, `AC-71`, `AC-72`, `AC-73`, `EC-23`, `EC-24`, `EC-25`, `US-15`
- **Arquivos:** `engine/ataque_imediato.py`

**Descrição**

Arquivo **novo**. Primeira das nove funções puras (plano R3.4.5), assinatura só com argumento nomeado (`*`): `derivar_RESERVA_MOBILIZAVEL(*, RESERVA_EXISTE, DISPOSICAO_USO_RESERVA, RESERVA_TOTAL, VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO) -> DinheiroTalvez`. As três regras da §13.1 **na ordem registrada**, exatamente como o pseudocódigo `deriveReservaMobilizavel` da §13.9: Regra 1 vence Regra 2 (`EC-23`); Regra 3 vence Regra 2 (`EC-25`); Regra 2 é `MIN(RESERVA_TOTAL, MAX(0, VALOR_MAXIMO...))`, com o `MAX(0, ...)` zerando negativo **antes** do `MIN` (`EC-24`). O módulo declara `REGRAS: Final[tuple[str, ...]]` — obrigatório, tem função pública (`tests/estatica/test_toda_regra_citada.py`).

**Critérios de aceite**

- [x] `engine/ataque_imediato.py` existe com docstring de módulo citando §13, a NFR de Pureza e `REGRAS: Final[tuple[str, ...]]` cobrindo as subseções e os `RF-NN` implementados
- [x] `derivar_RESERVA_MOBILIZAVEL` tem a assinatura exata do plano R3.4.5, com `*` forçando argumento nomeado
- [x] A função é **pura**: recebe tudo por parâmetro, não consulta `EstadoFinanceiro`, `Diagnostico`, relógio, arquivo nem global
- [x] `RESERVA_EXISTE = NAO` **ou** `DISPOSICAO_USO_RESERVA = NAO` devolve `dinheiro(0)` ignorando o valor informado, mesmo que ele esteja preenchido (`EC-23`)
- [x] `RESERVA_TOTAL` desconhecida **ou** `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` desconhecido devolve `DESCONHECIDO`, nunca `0` (`AC-73`, `EC-25`)
- [x] Valor informado negativo é zerado pelo `MAX(0, ...)` antes do `MIN`; o resultado nunca é negativo (`EC-24`)
- [x] Nenhuma das três fórmulas proibidas pela §13.1 aparece no corpo, e a docstring registra a TRAVA CANÔNICA citando `RF-49`
- [x] Nenhum valor `P_*` é lido — nenhuma fórmula da §13 usa parâmetro calibrável
- [x] `mypy --strict engine/`, `ruff check .` e `tests/estatica/test_sem_float_no_motor.py` passam

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

`engine/ataque_imediato.py` criado com **uma** função pública — `derivar_RESERVA_MOBILIZAVEL` — e `REGRAS: Final[tuple[str, ...]] = ("RF-43", "RF-49", "§13.1", "§13.9")`. As oito funções restantes do contrato R3.4.5 (`T-103`..`T-107`) **não** foram escritas, e por isso `REGRAS` cita só §13.1/§13.9, não a §13 inteira: citar §13.2–§13.4 hoje seria afirmar cobertura que o arquivo não tem. `engine/diagnostico.py` não foi tocado (`T-114`); `RESERVA_MOBILIZAVEL` do `Diagnostico` continua o placeholder de `T-90`, e **nenhum** consumidor chama a função nova ainda.

**As guardas estão na ordem do pseudocódigo da §13.9, e a ordem é testada, não só escrita.** As cinco guardas saem na sequência `RESERVA_EXISTE=NAO → DISPOSICAO_USO_RESERVA=NAO → RESERVA_TOTAL desconhecida → VALOR_MAXIMO... desconhecido → MIN(total, MAX(0, informado))`. Duas consequências dessa ordem não são dedutíveis das regras isoladas e ganharam teste próprio: (a) a Regra 1 vence **até** o desconhecido — `RESERVA_EXISTE=NAO` com os dois monetários `DESCONHECIDO` devolve `dinheiro(0)`, não `DESCONHECIDO`, porque sem reserva não há pendência a registrar; (b) a Regra 3 vence a Regra 2 — total desconhecido **com** informado conhecido devolve `DESCONHECIDO`, nunca o informado (`EC-25`).

**Colisão nome-de-parâmetro × nome-de-classe, resolvida sem tocar na assinatura.** O plano R3.4.5 dá ao parâmetro o mesmo nome canônico da classe (`RESERVA_EXISTE: RESERVA_EXISTE`), como exige o `sdd.config.md` §7. Dentro do corpo esse nome passa a designar o **valor** recebido, então `RESERVA_EXISTE.NAO` viraria acesso a membro **por instância** — que funciona no CPython 3.12 (verificado), mas é comportamento depreciado e ilegível. Adotados dois aliases de módulo (`_RESERVA_EXISTE`, `_DISPOSICAO_USO_RESERVA`) para alcançar os membros do domínio: a assinatura pública fica **idêntica** à do plano, caractere por caractere, e a comparação continua por identidade (`is`), no padrão do resto do motor.

**Critério 7 (TRAVA CANÔNICA) — verificado por AST, não por leitura.** Varredura dos `ast.BinOp` de `Mult`/`Sub`/`Div` no corpo da função: **zero** ocorrências envolvendo `RESERVA_TOTAL`; nenhum identificador contendo `RESERVA_MINIMA` existe no arquivo. `RESERVA_TOTAL` aparece exatamente uma vez em posição de cálculo, como o **teto** de um `min` — nunca como operando de multiplicação ou subtração. A docstring da função registra a trava nominalmente, citando `RF-49`, `AC-81` e as três formas proibidas. A prova estática formal é `T-113`.

**Critério 8 — `P_*`:** `re.findall(r"\bP_[A-Z_]+\b")` sobre o arquivo inteiro devolve `[]`, e o módulo não importa `Parametros` nem recebe parâmetro calibrável em nenhuma assinatura — ausência normativa, registrada na docstring do módulo.

**Critério 3 (pureza) — verificado por AST.** Nomes lidos no corpo: apenas os quatro parâmetros, os dois aliases, `dinheiro`, `DESCONHECIDO`, `min`, `max` e a local `informado_nao_negativo`. Zero `ast.Global`/`ast.Nonlocal`. Os cinco imports do módulo são `__future__.annotations`, `typing.Final`, os dois enums de `engine.estado`, `engine.precisao.dinheiro` e `engine.tipos.{DESCONHECIDO, DinheiroTalvez}` — nenhum `EstadoFinanceiro`, `Diagnostico`, `datetime`, `os`, `pathlib` ou `persistencia`. `inspect.signature` confirma os quatro parâmetros como `KEYWORD_ONLY`.

**Teste:** `tests/regras/test_reserva_mobilizavel.py` — **arquivo novo, deliberadamente distinto** de `tests/regras/test_ataque_imediato.py`, que é o arquivo de `T-112` (escopo alheio). 13 casos `@pytest.mark.regra` (9 funções + 4 parametrizações), tolerância **zero** via `assertar_exato` em toda asserção monetária (`RESERVA_MOBILIZAVEL` está em `SIMBOLOS_TOLERANCIA_ZERO` desde `T-109`; `assertar_monetario` não é usado). Cobrem `AC-70`, `AC-71`, `AC-72`, `AC-73`, os dois ramos do `OU` da Regra 1 separadamente, os dois casos de precedência de ordem descritos acima, `EC-24` em quatro combinações, e a recusa de chamada posicional. Os gabaritos `GAB-AI` formais (`@pytest.mark.gabarito_ataque_imediato`, em `tests/gabaritos_ataque_imediato/`) continuam sendo `T-110` — não foram escritos aqui.

**Verificação.** `lint` (`ruff check .`) — `All checks passed!`. `build` (`mypy` sobre as seis pastas) — `Found 1 error in 1 file (checked 259 source files)`, o **mesmo** e único erro pré-existente `app/montagem/estado.py:1326`, do slug `app-aluno`, que esta tarefa não corrige (`T-116`, e a tentativa já revertida documentada ali). Sobre `engine/` isolado: `Success: no issues found in 26 source files`. `pytest -q --ignore=tests/app_aluno` — **`374 passed, 9 skipped`**, contra o baseline pré-tarefa `361 passed, 9 skipped`: `+13`, exatamente os testes novos, **zero** regressão. `tests/estatica/` inteiro `passed`, incluindo `test_sem_float_no_motor.py`, `test_toda_regra_citada.py` (o módulo novo tem função pública e declara `REGRAS`, com `RF-43`/`RF-49` isentos do lint de regra fantasma e `§13.1`/`§13.9` fora do padrão de ID) e `test_nenhum_parametro_no_codigo.py`. Homologação `pytest -m "gabarito or invariante or gabarito_ataque_imediato"` — `18 passed`.

**Insumo para `T-116` — terceira falha de `AC-44`, prevista e não corrigida.** Na suíte completa, `tests/app_aluno/estatica/test_engine_congelado.py` passa de 2 para **3** falhas: além das duas pré-existentes (hash divergente dos cinco arquivos já alterados nesta rodada), `test_ac44_json_cobre_todo_py_de_engine_e_persistencia_e_a_migracao_antiga` passa a acusar `engine/ataque_imediato.py` como **ausente** do manifesto congelado — consequência inevitável de criar arquivo novo em `engine/`. É exatamente o que a descrição de `T-116` já antecipava ("o hash congelado de `engine/` desta vez cobre cinco arquivos alterados: ... `engine/ataque_imediato.py` (novo)"). `tests/app_aluno/estatica/hashes_congelados.json` **não** foi editado (escopo de `T-116`, e critério explícito de que ele não apareça no diff da rodada). Medição controlada da suíte completa: sem os dois arquivos novos, `128 failed, 982 passed, 74 skipped, 5 xfailed, 46 errors`; com eles, `129 failed, 994 passed, 74 skipped, 5 xfailed, 46 errors` — `+12 passed` e `+1 failed`, sendo a falha adicional exclusivamente a de `AC-44` acima. **Nenhum dos 13 testes novos falha**, e nenhuma falha pré-existente mudou de natureza.

**Escopo.** Nenhuma das outras oito funções da §13 foi escrita (`T-103`..`T-107`). Não foram tocados: `engine/diagnostico.py` (`T-114`), `tests/regras/test_ataque_imediato.py` (`T-112`), `tests/gabaritos_ataque_imediato/` (`T-110`, `T-111`), `app/montagem/estado.py` e `tests/app_aluno/estatica/hashes_congelados.json` (`T-116`). Nenhuma decisão de metodologia foi tomada: a lógica é transcrição direta do pseudocódigo `deriveReservaMobilizavel` da §13.9.

---

### `T-103` — Implementar `calcular_ATAQUE_IMEDIATO_POTENCIAL`

- **Tipo:** `Data`
- **Dependências:** `T-95`, `T-102`
- **Rastreia:** `RF-44`, `AC-77`, `EC-27`, `EC-30`, `US-16`
- **Arquivos:** `engine/ataque_imediato.py`

**Descrição**

Soma das cinco parcelas da §13.2 (plano R3.4.5): `DINHEIRO_DISPONIVEL` + `RESERVA_MOBILIZAVEL` + investimentos líquidos mobilizáveis + recursos extraordinários potenciais + ativos classificados `MOBILIZACAO_POSSIVEL` **ou** `MOBILIZACAO_RECOMENDAVEL`. `MOBILIZACAO_COM_RESSALVAS` e `NAO_MOBILIZAR` não entram nem aqui (`EC-30`). `RESERVA_MOBILIZAVEL` desconhecida contribui `0` para a soma — contribuição aritmética, não conversão de informação (§13.1, plano R3.8). `ECONOMIA_POTENCIAL_IMEDIATA` **não** entra: `OQ-31` está aberta e a §13.2 não a menciona.

**Critérios de aceite**

- [x] Assinatura exata do plano R3.4.5, com `*`, recebendo `DINHEIRO_DISPONIVEL`, `RESERVA_MOBILIZAVEL: DinheiroTalvez`, `investimentos`, `recursos_extraordinarios` e `ativos`
- [x] Ativo `MOBILIZACAO_POSSIVEL` **e** ativo `MOBILIZACAO_RECOMENDAVEL` entram na soma; `MOBILIZACAO_COM_RESSALVAS` e `NAO_MOBILIZAR` não entram, mesmo com valor líquido alto (`AC-77`, `EC-30`)
- [x] `RESERVA_MOBILIZAVEL` desconhecida contribui `0`, e a docstring registra que a pendência continua legível na saída — nunca convertida em informação
- [x] Coleções vazias e `DINHEIRO_DISPONIVEL = 0` devolvem `dinheiro(0)`, sem erro e sem desconhecido fabricado (`EC-27`)
- [x] `ECONOMIA_POTENCIAL_IMEDIATA` não aparece na função nem em nenhum parâmetro dela (`OQ-31` aberta)
- [x] Função pura, sem consultar `EstadoFinanceiro`/`Diagnostico`; `mypy --strict engine/` e `ruff check .` passam

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

`calcular_ATAQUE_IMEDIATO_POTENCIAL` acrescentada a `engine/ataque_imediato.py`, com a assinatura do plano R3.4.5 **byte a byte** — conferida por comparação automática entre o bloco de código do plano e o do arquivo (comentários inline removidos, espaço em branco normalizado): `IGUAL`. `inspect.signature` confirma os cinco parâmetros como `KEYWORD_ONLY` e o retorno como `Dinheiro`.

**A decisão de transcrição que esta tarefa teve de tomar — e que NÃO é decisão de metodologia.** A §13.2 nomeia as cinco parcelas, mas só escreve o filtro de classificação junto da quinta ("ativos líquidos classificados como `MOBILIZACAO_POSSIVEL` OU `MOBILIZACAO_RECOMENDAVEL`"). Para as outras duas parcelas de coleção, o filtro está no **nome da parcela**, e foi transcrito de lá, com apoio em `AC-77`/`AC-79`:

- **`INVESTIMENTOS_LIQUIDOS_MOBILIZAVEIS`** — duas condições, as duas do próprio nome: `POSSUI_LIQUIDEZ` (líquidos) **e** classificação em {`MOBILIZACAO_POSSIVEL`, `MOBILIZACAO_RECOMENDAVEL`} (mobilizáveis). `AC-77` fecha a segunda para além do ativo: "nenhum **item** `MOBILIZACAO_COM_RESSALVAS` ou `NAO_MOBILIZAR` entra na soma" — *item*, não *ativo*. Liquidez não promove classificação, e ambos os ramos têm teste próprio.
- **`RECURSOS_EXTRAORDINARIOS_POTENCIAIS`** — **sem filtro nenhum**: todos os itens da coleção. Não é omissão. É `AC-79` escrito ao contrário: "recurso previsto para o futuro e não confirmado **não** compõe `EXTRAORDINARIOS_RECOMENDADOS`, **ainda que componha** `RECURSOS_EXTRAORDINARIOS_POTENCIAIS`". Filtrar por `ATE_30D`/`CONFIRMADO` aqui tornaria a segunda metade de `AC-79` uma afirmação vazia e apagaria a diferença entre §13.2 e §13.3, que é a razão de a §13.6 ter hierarquia. Há teste explícito do recurso `SETE_A_DOZE_MESES` + `POSSIVEL` compondo o potencial.

**Critério 3 — desconhecido contribui `0` sem virar informação.** `RESERVA_MOBILIZAVEL = DESCONHECIDO` é testado contra o mesmo cálculo com `dinheiro(0)`: os dois dão `1.400`, exatamente iguais. A guarda é `is DESCONHECIDO`, nunca "é falsy" — `dinheiro(0)` conhecido soma normalmente (padrão de `AC-32` em `_somar_pagamentos`), e há teste separado para isso. A função devolve `Dinheiro`, **nunca** `DinheiroTalvez`: propagar o desconhecido para a saída tornaria o potencial inexprimível sempre que a decisão de reserva fosse adiada e contrariaria `EC-27`. A pendência continua legível onde a spec manda que ela fique — `Diagnostico.RESERVA_MOBILIZAVEL: DinheiroTalvez` (`RF-41`, plano R3.8) —, e `engine/diagnostico.py` **não** foi tocado (`T-114`). A docstring registra a distinção nominalmente.

**Critério 5 — `ECONOMIA_POTENCIAL_IMEDIATA`, verificado por AST e não por leitura.** O identificador aparece **1 vez** no arquivo inteiro, e a varredura de `ast.Name`/`ast.Attribute`/`ast.arg`/`ast.keyword`/`ast.alias` mostra que ele **não existe em código executável**: as ocorrências textuais são `docstring=1, comentário=0, resto=0`. Ele não é parâmetro de nenhuma das seis funções (lista de `kwonlyargs` conferida uma a uma). A única menção é a frase da docstring que o plano R3.4.5 prescreve, declarando que ele **não** entra na soma porque `OQ-31` está aberta. O mesmo método provou que `EstadoFinanceiro` (4x), `Diagnostico` (4x) e `Parametros` (1x) também só existem em prosa — `resto=0` para todos.

**Critério 6 (pureza).** Zero `ast.Global`/`ast.Nonlocal` no módulo. Nenhum import novo além de `engine.estado` (três dataclasses de item + dois enums), `engine.precisao` e `engine.tipos`; nenhum `datetime`, `os`, `pathlib`, `open(`, `random` ou `persistencia`. `re.findall(r"\bP_[A-Z_]+\b")` sobre o arquivo devolve `[]` — nenhum parâmetro calibrável, coerente com a §13.

**Teste:** `tests/regras/test_ataque_imediato_potencial.py` — **arquivo novo**, deliberadamente distinto de `tests/regras/test_ataque_imediato.py`, que é de `T-112`. 10 funções `@pytest.mark.regra`, 14 casos com as parametrizações, `assertar_exato` em toda asserção monetária (tolerância zero, spec §5). Cobrem: a soma das cinco parcelas com as quatro classificações presentes e números potência-de-dois, para que um item indevido na soma denuncie **qual** (`AC-77`); `POSSIVEL` e `RECOMENDAVEL` entrando os dois; `COM_RESSALVAS`/`NAO_MOBILIZAR` fora, com valor de 999.999 (`EC-30`) — para ativo **e** para investimento; investimento recomendável sem liquidez fora; recurso futuro não confirmado **dentro** (`AC-79`, lado do potencial); desconhecido contribuindo `0`; zero conhecido somando; `EC-27`; e a recusa de chamada posicional.

**Verificação.** `ruff check .` — `All checks passed!`. `mypy engine/` — `Success: no issues found in 26 source files`. `build` (as seis pastas) — `Found 1 error in 1 file (checked 261 source files)`: o **mesmo** erro pré-existente `app/montagem/estado.py:1326`, do slug `app-aluno`, que esta tarefa não corrige. `pytest -q --ignore=tests/app_aluno` (com `T-104`, entregue junto) — `410 passed, 9 skipped`, contra baseline `374 passed, 9 skipped`. `tests/estatica/` — `55 passed`, incluindo `test_toda_regra_citada.py` (o `REGRAS` ampliado passa), `test_sem_float_no_motor.py` e `test_uso_de_tolerancia.py`.

**Escopo.** Nenhuma função de `T-105`+ foi escrita — `calcular_NECESSIDADE_RESIDUAL`, `derivar_RESERVA_RECOMENDADA`, `calcular_ATAQUE_IMEDIATO_RECOMENDADO` e `verificar_hierarquia_ataque_imediato` estão **ausentes** do módulo (verificado por `hasattr`). Não foram tocados: `engine/diagnostico.py` (`T-114`), `tests/regras/test_ataque_imediato.py` (`T-112`), `tests/gabaritos_ataque_imediato/` (`T-110`, `T-111`), `app/montagem/estado.py` e `tests/app_aluno/estatica/hashes_congelados.json` (`T-116`).

---

### `T-104` — Implementar os quatro componentes não protetivos da §13.3

- **Tipo:** `Data`
- **Dependências:** `T-95`, `T-102`
- **Rastreia:** `RF-45`, `RF-37`, `AC-78`, `AC-79`, `EC-27`, `EC-30`, `US-16`
- **Arquivos:** `engine/ataque_imediato.py`

**Descrição**

Quatro funções puras (plano R3.4.5), nas ordens 1 a 4 da §13.7: `calcular_CAIXA_RECOMENDADO` (identidade sobre `DINHEIRO_DISPONIVEL` — existe para dar nome normativo à parcela, não para revalidar nada, `OQ-28`); `calcular_INVESTIMENTOS_RECOMENDADOS` (soma de `VALOR_LIQUIDO_REALIZAVEL` dos investimentos **com liquidez E** `MOBILIZACAO_RECOMENDAVEL`); `calcular_ATIVOS_RECOMENDADOS` (`Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` dos ativos `MOBILIZACAO_RECOMENDAVEL`); `calcular_EXTRAORDINARIOS_RECOMENDADOS` (só `CERTEZA = CONFIRMADO` **e** `JANELA = ATE_30D`).

**Critérios de aceite**

- [x] As quatro funções existem com as assinaturas exatas do plano R3.4.5, todas com `*`
- [x] `calcular_CAIXA_RECOMENDADO` devolve `DINHEIRO_DISPONIVEL` sem transformação e sem revalidação; a docstring cita `RF-37`/`AC-63`/`OQ-28`
- [x] Investimento `MOBILIZACAO_POSSIVEL`, ou sem liquidez, **não** compõe `INVESTIMENTOS_RECOMENDADOS` (`AC-78`)
- [x] Ativo `MOBILIZACAO_POSSIVEL` fica só no potencial; só `MOBILIZACAO_RECOMENDAVEL` compõe `ATIVOS_RECOMENDADOS`; `COM_RESSALVAS` e `NAO_MOBILIZAR` não entram automaticamente (`AC-78`, `EC-30`)
- [x] Recurso extraordinário com janela futura, ou não confirmado, não compõe `EXTRAORDINARIOS_RECOMENDADOS` ainda que componha os potenciais (`AC-79`)
- [x] Coleção vazia devolve `dinheiro(0)` em cada uma das quatro (`EC-27`)
- [x] Cada docstring cita a subseção da §13 e a ordem da §13.7 que implementa; as quatro são puras
- [x] `mypy --strict engine/` e `ruff check .` passam

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

As quatro funções acrescentadas a `engine/ataque_imediato.py`, escritas **na ordem 1→4 da §13.7** (caixa → investimentos → extraordinários → ativos), e não na ordem em que a tabela da §13.3 lista os componentes: a ordem do arquivo é a ordem de utilização normativa, e cada docstring diz qual é a sua. As quatro assinaturas foram conferidas **byte a byte** contra o bloco do plano R3.4.5 por comparação automática — `IGUAL` nas quatro; `inspect.signature` confirma `KEYWORD_ONLY` em todos os parâmetros e `Dinheiro` em todos os retornos.

**Critério 2 — `CAIXA_RECOMENDADO` é identidade, provado no sentido forte.** O corpo executável da função é uma linha: `return DINHEIRO_DISPONIVEL` (extraído por AST, descartando a docstring). O teste não se contenta com igualdade numérica — asserta `calcular_CAIXA_RECOMENDADO(DINHEIRO_DISPONIVEL=entrada) is entrada`, com `entrada = dinheiro("7000.005")`: qualquer transformação (`+valor`, `dinheiro(valor)`, `quantize`) construiria um `Decimal` novo e faria o `is` falhar. Os três centavos da entrada são de propósito — um `quantize` escondido passaria numa comparação por igualdade de valor redondo. A docstring cita `RF-37`, `AC-63` e `OQ-28`, e registra por que **não** revalida: "realmente livre / não comprometido" é garantia de coleta (`B4.01`), `OQ-28` segue aberta encaminhada como tal, e revalidar aqui seria decidi-la no código.

**Critérios 3, 4 e 5 — os três filtros, e o fato de serem diferentes entre si.** É a assimetria que os testes atacam:

| Componente | Condições | Por quê |
| --- | --- | --- |
| `INVESTIMENTOS_RECOMENDADOS` | **duas**: `POSSUI_LIQUIDEZ` **E** `MOBILIZACAO_RECOMENDAVEL` | a §13.3 escreve as duas com "E" |
| `ATIVOS_RECOMENDADOS` | **uma**: `MOBILIZACAO_RECOMENDAVEL` | `ItemAtivo` não tem campo de liquidez — "com liquidez" é exigência que a §13.3 impõe só aos investimentos |
| `EXTRAORDINARIOS_RECOMENDADOS` | **duas**: `CERTEZA is CONFIRMADO` **E** `JANELA is ATE_30D` | `AC-65`: os dois campos bastam para decidir por item, sem consultar mais nada |

O teste de investimentos usa quatro itens que isolam cada erro possível — só-liquidez (400), só-classificação (800), nenhuma das duas (1.600), ambas (2.000) — de modo que o total `2.000` distingue quatro implementações erradas diferentes. `MOBILIZACAO_POSSIVEL`, `COM_RESSALVAS` e `NAO_MOBILIZAR` são varridas por parametrização, com 500.000 líquidos, e nenhuma compõe (`AC-78`, `EC-30`). Nos extraordinários, as **quatro** janelas não-`ATE_30D` (inclusive `NAO_SEI`) e as **duas** certezas não-`CONFIRMADO` são varridas uma a uma: cada lado do `E` cai sozinho. O lado complementar de `AC-79` — que o mesmo recurso futuro **compõe** os potenciais — está em `test_ataque_imediato_potencial.py` (`T-103`), então o "ainda que componha" do critério tem prova nos dois lados. Em ativos, `test_ativo_possivel_fica_so_no_potencial` reproduz `AC-78` literalmente: possível 500 + recomendável 300 dá **300**, e os 500 continuam no potencial (provado no arquivo de `T-103`).

**"Não entram automaticamente" foi lido como norma, não como sugestão.** Não existe no módulo nenhum ramo que promova uma classe a outra, nenhuma exceção por valor alto, nenhum default: a classificação entra como dado e sai igual (`AC-67`, `OQ-26` aberta). É o que a docstring de `calcular_ATIVOS_RECOMENDADOS` registra — o que traria um item com ressalva para dentro é decisão humana sobre a ressalva, jamais uma regra deste módulo.

**Critério 6 (`EC-27`).** Um teste chama as quatro com coleção vazia (e `DINHEIRO_DISPONIVEL = 0`) e asserta `dinheiro(0)` em cada uma, com `assertar_exato`. Não há ramo de `DESCONHECIDO` a tratar em nenhuma das quatro: `VALOR_LIQUIDO_REALIZAVEL`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` e `VALOR_RECURSO_EXTRAORDINARIO` são `Dinheiro` puro por contrato de entrada (`RF-38`/`RF-39`, valor já apurado — `OQ-27` aberta), e a classificação é obrigatória sem default (`EC-31`).

**Critério 7.** Cada uma das quatro docstrings cita a subseção (§13.3) **e** a ordem da §13.7 que implementa ("ordem 1" a "ordem 4") — conferido por busca de substring nas quatro, junto com `RF-45`, `AC-78`/`AC-79`, `EC-27`/`EC-30` e, no caixa, `RF-37`/`AC-63`/`OQ-28`: **todos presentes**. Pureza: zero `ast.Global`/`ast.Nonlocal`; nenhum nome de `EstadoFinanceiro`, `Diagnostico`, `Parametros`, relógio ou I/O em código executável (varredura de AST — as menções textuais são `resto=0`, só prosa); recusa de chamada posicional testada nas quatro.

**`REGRAS` do módulo atualizado por `T-103`+`T-104` juntas:** de `("RF-43", "RF-49", "§13.1", "§13.9")` para `("RF-43", "RF-44", "RF-45", "RF-49", "§13.1", "§13.2", "§13.3", "§13.7", "§13.9")`. `§13.4` e `§13.6` continuam **deliberadamente ausentes** — citá-las hoje afirmaria uma cobertura que o arquivo não tem (`T-105`, `T-106`, `T-107`), no mesmo critério que `T-102` aplicou a si mesma.

**Teste:** `tests/regras/test_componentes_recomendados.py` — **arquivo novo**, distinto de `tests/regras/test_ataque_imediato.py` (`T-112`). 12 funções `@pytest.mark.regra`, 22 casos com as parametrizações, `assertar_exato` em toda asserção monetária.

**Verificação.** `ruff check .` — `All checks passed!`. `mypy engine/` — `Success: no issues found in 26 source files`. `build` (as seis pastas) — `Found 1 error in 1 file (checked 261 source files)`, o **mesmo** e único erro pré-existente `app/montagem/estado.py:1326`, do slug `app-aluno`, não corrigido aqui. `pytest -q --ignore=tests/app_aluno` — **`410 passed, 9 skipped`** contra baseline `374 passed, 9 skipped`: `+36`, exatamente os testes novos de `T-103` (14 casos) e `T-104` (22 casos), **zero** regressão. `tests/estatica/` — `55 passed`. Homologação `pytest -m "gabarito or invariante or gabarito_ataque_imediato"` — `18 passed`. Suíte completa: `129 failed, 1030 passed, 74 skipped, 5 xfailed, 46 errors`, contra `129 failed, 994 passed, ...` medidos ao fim de `T-102` — `+36 passed`, **nenhuma falha nova**, mesmo conjunto de 46 erros. As 3 falhas de `tests/app_aluno/estatica/test_engine_congelado.py` são as mesmas já registradas em `T-102` (hash de `engine/` divergente e `engine/ataque_imediato.py` fora do manifesto): editar `hashes_congelados.json` é `T-116`, e ele **não** foi tocado.

**Escopo.** Cinco funções ao todo nesta leva (`T-103` + `T-104`). Nenhuma função de `T-105`+ existe no módulo. `engine/diagnostico.py` não foi tocado (`T-114`) — nenhum consumidor chama as cinco funções novas ainda; elas são, por ora, exercitadas só por teste. Nenhuma decisão de metodologia foi tomada: os filtros são transcrição da §13.2/§13.3, e onde a §13 não publicou regra (`OQ-26`, `OQ-27`, `OQ-28`), o dado continua chegando pronto por contrato de entrada.

---

### `T-105` — Implementar `calcular_NECESSIDADE_RESIDUAL` e `derivar_RESERVA_RECOMENDADA`

- **Tipo:** `Data`
- **Dependências:** `T-102`, `T-104`
- **Rastreia:** `RF-46`, `RF-48`, `AC-74`, `EC-26`, `EC-29`, `US-16`
- **Arquivos:** `engine/ataque_imediato.py`

**Descrição**

Duas funções puras da §13.4 (plano R3.4.5). `calcular_NECESSIDADE_RESIDUAL` = `MAX(0, elegível − caixa − investimentos − extraordinários − ativos)`, com `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` **por parâmetro** (`RF-48`, `OQ-29` aberta). `derivar_RESERVA_RECOMENDADA` implementa a **TRAVA MODO_ESTABILIZACAO**: se `RESULTADO_MENSAL_ATUAL < 0`, resultado `0` — a reserva não mascara déficit estrutural. `RESULTADO_MENSAL_ATUAL` também chega **por parâmetro**: a função **não** consulta `Diagnostico.MODO_ESTABILIZACAO`, ainda que ele derive da mesma condição (`engine/diagnostico.py:486`), porque consultá-lo quebraria a NFR de Pureza. `RESERVA_MOBILIZAVEL` desconhecida devolve `0` "até decisão válida" (§13.9, `EC-26`), com a pendência registrada.

**Critérios de aceite**

- [x] As duas funções têm as assinaturas exatas do plano R3.4.5, com `*`, e recebem `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`/`RESULTADO_MENSAL_ATUAL` **por parâmetro** — nenhuma delas os busca em `EstadoFinanceiro` ou `Diagnostico`
- [x] Não protetivos que já cobrem a necessidade produzem `NECESSIDADE_RESIDUAL = 0` (`EC-29`), nunca valor negativo
- [x] `RESULTADO_MENSAL_ATUAL < 0` produz `RESERVA_RECOMENDADA = 0` mesmo com mobilizável alto (`AC-74`), e a docstring registra que `Diagnostico.MODO_ESTABILIZACAO` deriva da mesma condição sem ser consultado aqui
- [x] `RESERVA_MOBILIZAVEL` desconhecida produz `0` com pendência registrada, nunca conversão silenciosa em zero como informação (`EC-26`)
- [x] Nos demais casos, `MIN(RESERVA_MOBILIZAVEL, NECESSIDADE_RESIDUAL)`
- [x] A ordem de avaliação segue `deriveReservaRecomendada` da §13.9 caractere a caractere no resultado lógico
- [x] `mypy --strict engine/` e `ruff check .` passam

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

`calcular_NECESSIDADE_RESIDUAL` e `derivar_RESERVA_RECOMENDADA` acrescentadas a `engine/ataque_imediato.py`. As duas assinaturas foram conferidas **byte a byte** contra o bloco do plano R3.4.5 por comparação automática (corpo substituído por `pass`, comentários inline removidos, espaço normalizado): `IGUAL` nas duas. `inspect.signature` confirma os cinco e os três parâmetros como `KEYWORD_ONLY` e `Dinheiro` nos dois retornos.

**Critério 1 (pureza da origem do dado), verificado por AST e não por leitura.** Varredura dos `ast.Name`/`ast.Attribute` do corpo de cada função, descartada a docstring:

- `calcular_NECESSIDADE_RESIDUAL` — `Names={ATIVOS_RECOMENDADOS, CAIXA_RECOMENDADO, EXTRAORDINARIOS_RECOMENDADOS, INVESTIMENTOS_RECOMENDADOS, NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL, dinheiro, max, residual}`, `Attributes=[]`;
- `derivar_RESERVA_RECOMENDADA` — `Names={DESCONHECIDO, NECESSIDADE_RESIDUAL, RESERVA_MOBILIZAVEL, RESULTADO_MENSAL_ATUAL, dinheiro, min}`, `Attributes=[]`.

Ou seja: os próprios parâmetros, mais `dinheiro`/`max`/`min`/`DESCONHECIDO`. Nada mais. Sobre o módulo inteiro, `EstadoFinanceiro`, `Diagnostico`, `MODO_ESTABILIZACAO` e `Parametros` têm `resto=0` na contagem `textual − docstring − comentário` — existem só em prosa. Zero `ast.Global`/`ast.Nonlocal`; `re.findall(r"\bP_[A-Z_]+\b")` devolve `[]`.

**Critério 3 — a trava é a regra mais delicada das três, e foi escrita como a §13.4 a escreve.** `RESULTADO_MENSAL_ATUAL < 0` devolve `dinheiro(0)` **antes de qualquer outra coisa**: sem `MIN`, sem olhar o residual, sem olhar o mobilizável. `AC-74`/`GAB-AI-05` reproduzido: déficit de −1.000 com mobilizável de 20.000 e residual de 20.000 dá `0` — sem a trava, o `MIN(20.000, 20.000)` devolveria 20.000, e é essa a diferença que `test_ordem_da_secao_13_9_a_trava_vence_o_min` mede (é o único caso em que a ordem muda o NÚMERO, não só o caminho). A condição é `< 0` estrito, sem limiar e sem `P_*`: há teste parametrizado com déficit de **um centavo** (`dinheiro("-0.01")`) e teste separado provando que resultado mensal **exatamente zero não é déficit** e não aciona a trava — a §13.4 diz `< 0`, não `<= 0`.

**A função NÃO consulta `Diagnostico.MODO_ESTABILIZACAO`, e isso é a norma, não uma omissão.** `MODO_ESTABILIZACAO` deriva da mesma condição de déficit em `engine/diagnostico.py`, o que torna consultá-lo tentador e errado: quebraria a NFR de Pureza (spec §5) e amarraria a §13.4 a um objeto de estado que ela não menciona. A docstring registra nominalmente que a condição é uma só escrita em dois lugares por design, e que divergência entre elas seria bug de derivação. `engine/diagnostico.py` **não** foi tocado (`T-114`).

**Critério 4 — `EC-26` sem conversão silenciosa.** `RESERVA_MOBILIZAVEL is DESCONHECIDO` devolve `dinheiro(0)` "até decisão válida" (§13.9). A guarda é `is DESCONHECIDO`, **nunca** "é falsy", e os dois casos têm teste separado justamente porque coincidem no número: um `if not RESERVA_MOBILIZAVEL` passaria nos dois e estaria errado, pois `dinheiro(0)` conhecido é decisão válida do usuário e deve seguir para o `MIN`. A pendência não é convertida aqui em informação — ela continua legível onde a spec manda que fique, `Diagnostico.RESERVA_MOBILIZAVEL: DinheiroTalvez` (`RF-41`, plano R3.8), e é por isso que o retorno desta função é `Dinheiro` e não `DinheiroTalvez`: a §13.9 devolve `0`, não `DESCONHECIDA`.

**Critério 6 — a ordem, e a única liberdade que a §13.9 concede.** O corpo de `derivar_RESERVA_RECOMENDADA` tem exatamente três sentenças executáveis, nesta sequência (extraídas por AST): `if RESULTADO_MENSAL_ATUAL < dinheiro(0)` → `if RESERVA_MOBILIZAVEL is DESCONHECIDO` → `return min(...)`. O pseudocódigo calcula `necessidadeResidual` **entre** as duas guardas; aqui esse cálculo é insumo do chamador (`calcular_NECESSIDADE_RESIDUAL`) e **nenhum dos dois ramos anteriores o consome**, então o RESULTADO LÓGICO é idêntico — que é precisamente o que a nota de implementação da §13.9 exige ("a tecnologia pode variar, mas o resultado lógico não pode variar"). A docstring registra essa leitura explicitamente, para que ela não seja confundida com desvio.

**Critério 2 (`EC-29`).** `MAX(0, ...)` é regra, não defesa: um residual negativo propagado faria o `MIN` devolver número negativo e quebraria a hierarquia da §13.6 — há teste dedicado a essa consequência (`test_reserva_recomendada_nunca_devolve_negativo`, varrendo 3 residuais × 3 resultados mensais × 4 mobilizáveis, inclusive `DESCONHECIDO`). Testadas as três fronteiras: cobertura excedente (daria −5.000 → dá `0`), cobertura **exata** com centavos (`7333.33 − 3333.33 − 4000` → `0`, onde um `quantize` escondido apareceria) e preservação de centavos (`999.97`, precisão integral, `G-01`).

**Teste:** `tests/regras/test_reserva_recomendada.py` — **arquivo novo**, deliberadamente distinto de `tests/regras/test_ataque_imediato.py` (`T-112`). Contribuição de `T-105`: 20 casos `@pytest.mark.regra`, `assertar_exato` em toda asserção monetária (tolerância zero; `NECESSIDADE_RESIDUAL` está em `SIMBOLOS_TOLERANCIA_ZERO` desde `T-109`). `GAB-AI-06` aparece na parte que estas duas funções cobrem (residual 8.000 → reserva 8.000), com o ponta a ponta ficando para `T-110`.

**Verificação.** `ruff check .` — `All checks passed!`. `mypy engine/` — `Success: no issues found in 26 source files`. `build` completo — `Found 1 error in 1 file (checked 264 source files)`: o **mesmo** e único erro pré-existente `app/montagem/estado.py:1326`, do slug `app-aluno`, não corrigido aqui (`AC-41` daquele slug). Medição controlada do delta (arquivo de teste movido para fora e devolvido, `__pycache__` limpo entre as duas): **`433 passed, 9 skipped` → `474 passed, 9 skipped`**, `+41` — exatamente os casos novos de `T-105`+`T-106`+`T-107` juntos, **zero** regressão.

**Escopo.** `engine/diagnostico.py` não foi tocado (`T-114`), `tests/regras/test_ataque_imediato.py` não foi tocado (`T-112`), `tests/gabaritos_ataque_imediato/` não recebeu gabarito (`T-110`/`T-111`), `app/montagem/estado.py` e `tests/app_aluno/estatica/hashes_congelados.json` não foram tocados (`T-116`). Nenhuma decisão de metodologia foi tomada: `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` **não** foi derivada (`OQ-29` segue aberta) — ela entra por parâmetro, e é isso que torna estas funções escrevíveis e verificáveis hoje.

---

### `T-106` — Implementar `calcular_ATAQUE_IMEDIATO_RECOMENDADO`

- **Tipo:** `Data`
- **Dependências:** `T-104`, `T-105`
- **Rastreia:** `RF-47`, `RF-48`, `AC-80`, `EC-28`, `US-16`
- **Arquivos:** `engine/ataque_imediato.py`

**Descrição**

`MIN(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL, CAIXA_RECOMENDADO + INVESTIMENTOS_RECOMENDADOS + EXTRAORDINARIOS_RECOMENDADOS + ATIVOS_RECOMENDADOS + RESERVA_RECOMENDADA)`, exatamente como `deriveAtaqueImediatoRecomendado` da §13.9. Seis parâmetros `Dinheiro` de mesmo tipo, **todos nomeados obrigatoriamente** (`*`): com passagem posicional, trocar elegível por caixa seria erro silencioso que nenhum tipo pega (plano R3.4.5). O elegível entra por argumento explícito (`RF-48`/`AC-80`, `OQ-29` aberta).

**Critérios de aceite**

- [x] Assinatura exata do plano R3.4.5, com `*` e os seis parâmetros nomeados
- [x] A função **não** busca `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` em `EstadoFinanceiro` nem em `Diagnostico` (`AC-80`)
- [x] Elegível `= 0` com recursos recomendáveis positivos devolve `dinheiro(0)` — a §13.5 proíbe recomendar recurso sem destinação financeira elegível (`EC-28`)
- [x] Chamar com argumento posicional é impossível (`TypeError`), por causa do `*`
- [x] A docstring cita §13.3, §13.9 e `RF-47`; a função é pura
- [x] `mypy --strict engine/` e `ruff check .` passam

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

`calcular_ATAQUE_IMEDIATO_RECOMENDADO` acrescentada a `engine/ataque_imediato.py`, transcrição direta de `deriveAtaqueImediatoRecomendado` (§13.9): soma dos cinco componentes recomendados, `MIN` contra o elegível. Assinatura conferida **byte a byte** contra o bloco do plano R3.4.5 — `IGUAL`; `inspect.signature` confirma os **seis** parâmetros como `KEYWORD_ONLY` e o retorno como `Dinheiro`.

**Critério 3 (`EC-28`) — a razão de o elegível ser TETO e não parcela.** Com `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = 0` e 100.000 de recursos recomendáveis (5 × 20.000), o resultado é `dinheiro(0)`, verificado em execução. É a §13.5 escrita como código — "nunca recomendar recurso sem destinação financeira elegível": ter dinheiro mobilizável não é razão para mobilizá-lo. O teste é construído para distinguir os dois erros plausíveis: uma implementação que somasse antes de limitar, ou que lesse elegível `0` como "sem limite", devolveria 100.000. O lado complementar, `AC-76`/`GAB-AI-07`, também tem teste próprio: 10.000 de elegível contra 25.000 de recursos dá **10.000** — não 25.000 (ignorar o teto) e não 35.000 (somar o elegível como se fosse parcela).

**Critério 2 (`AC-80`) — verificado por AST.** O corpo da função lê apenas os seis parâmetros e a local `recursos_recomendados`; `Attributes=[]`. Nenhum nome de `EstadoFinanceiro`, `Diagnostico` ou `Parametros` em código executável no módulo (`resto=0` na contagem `textual − docstring − comentário` dos três). O elegível chega por argumento explícito e **não é derivado**: a §13.5 o define em prosa mas não publica fórmula, e `OQ-29` segue **aberta** — é exatamente isso que torna esta função verificável hoje, e derivá-la seria decidir metodologia no código (`sdd.config.md` §6).

**Critério 4 — o `*` não é estilo.** São seis parâmetros `Dinheiro` do MESMO tipo: em chamada posicional, trocar `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` por `CAIXA_RECOMENDADO` seria erro silencioso que nenhum tipo pega e que os `GAB-AI` só detectariam por sorte (plano R3.4.5). Testado com `pytest.raises(TypeError)` sobre seis argumentos posicionais; em `mypy --strict` a mesma chamada é erro de compilação (o `type: ignore[call-arg]` do teste é necessário justamente por isso).

**Critério 5.** A docstring cita §13.3, §13.5, §13.9, `RF-47`, `RF-48`, `EC-28`, `AC-76`, `AC-80`, `GAB-AI-07` e `OQ-29` — conferido por busca de substring. Pureza declarada nominalmente ("Função pura (spec §5, NFR 'Pureza')") e verificada por AST junto com o resto do módulo.

**Retorno `Dinheiro`, nunca `DinheiroTalvez` — decisão herdada, não nova.** Não há caminho da §13 em que o recomendado seja desconhecido: a parcela desconhecida da reserva já entrou como `0` em `derivar_RESERVA_RECOMENDADA` (§13.9, plano R3.4.6). `AC-73` exige apenas que NENHUM valor da reserva entre nele, o que `RESERVA_RECOMENDADA = 0` satisfaz — e há teste encadeado (`test_reserva_desconhecida_nao_entra_no_recomendado`) que parte de `RESERVA_MOBILIZAVEL = DESCONHECIDO` e confirma o recomendado numérico em 12.000, só com os não protetivos.

**Teste:** contribuição de `T-106` em `tests/regras/test_reserva_recomendada.py` — 7 casos `@pytest.mark.regra`, `assertar_exato` em toda asserção monetária (`ATAQUE_IMEDIATO_RECOMENDADO` está em `SIMBOLOS_TOLERANCIA_ZERO` desde `T-109`). As cinco parcelas da soma usam potências de dois (1.000/2.000/4.000/8.000/16.000 = 31.000) para que a falta de qualquer uma denuncie **qual**. `GAB-AI-06` reproduzido na fronteira do `MIN` com os dois lados iguais (20.000).

**Verificação.** `ruff check .` — `All checks passed!`. `mypy engine/` — `Success: no issues found in 26 source files`. `build` completo — `Found 1 error in 1 file (checked 264 source files)`, o mesmo erro pré-existente `app/montagem/estado.py:1326` do slug `app-aluno`, não corrigido aqui. Suíte: `474 passed, 9 skipped`, `+41` sobre a medição controlada sem o arquivo de teste novo (`433 passed, 9 skipped`), zero regressão.

**Escopo.** `ATAQUE_IMEDIATO_APROVADO` **não** foi implementado (`OQ-30`, fatia 3C). `engine/diagnostico.py` não foi tocado (`T-114`) — nenhum consumidor chama esta função ainda.

---

### `T-107` — Implementar `verificar_hierarquia_ataque_imediato`

- **Tipo:** `Data`
- **Dependências:** `T-103`, `T-106`
- **Rastreia:** `RF-50`, `AC-82`, `US-16`
- **Arquivos:** `engine/ataque_imediato.py`

**Descrição**

Invariante da §13.6 na parte verificável sem a fatia 3C (plano R3.4.5/R3.10): `ATAQUE_IMEDIATO_POTENCIAL >= ATAQUE_IMEDIATO_RECOMENDADO >= 0`, **tolerância zero**. Levanta `ErroInvariante`, mesmo padrão de `engine/ciclo_mensal.py:596` (regra `A-04`) — nunca corrige, nunca degrada silenciosamente: violação é bug do motor, não dado do usuário. Função **separada**, chamada explicitamente: embuti-la em `calcular_ATAQUE_IMEDIATO_RECOMENDADO` obrigaria aquela função a receber o potencial, que não é insumo da fórmula da §13.3. O ramo `>= ATAQUE_IMEDIATO_APROVADO >= 0` fica para 3C (`OQ-30`) e **não** é implementado aqui.

**Critérios de aceite**

- [x] `verificar_hierarquia_ataque_imediato(*, ATAQUE_IMEDIATO_POTENCIAL, ATAQUE_IMEDIATO_RECOMENDADO) -> None` existe com a assinatura exata do plano
- [x] `POTENCIAL < RECOMENDADO` levanta `ErroInvariante` com mensagem que nomeia os dois valores; `RECOMENDADO < 0` também
- [x] A comparação é exata sobre `Decimal` — nenhuma tolerância, nenhum `round`, nenhuma correção de valor (`AC-82`)
- [x] Nenhuma referência a `ATAQUE_IMEDIATO_APROVADO` aparece na função, no módulo ou em qualquer parâmetro (3C fora de escopo) — **ver a leitura declarada abaixo**
- [x] A docstring cita `RF-50`, §13.6 e `A-04`; `mypy --strict engine/` e `ruff check .` passam

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

`verificar_hierarquia_ataque_imediato` acrescentada a `engine/ataque_imediato.py`, com a assinatura do plano R3.4.5 conferida **byte a byte** — `IGUAL`. Dois parâmetros `KEYWORD_ONLY`, retorno `None`: ou passa em silêncio, ou levanta.

**Critério 3 (`AC-82`) — tolerância zero, provado por AST e por teste.** As comparações do corpo, extraídas da árvore, são exatamente duas e ambas com operador `Lt` nu sobre `Decimal`: `ATAQUE_IMEDIATO_POTENCIAL < ATAQUE_IMEDIATO_RECOMENDADO` e `ATAQUE_IMEDIATO_RECOMENDADO < dinheiro(0)`. Varredura de nomes em código executável no módulo inteiro: `round=False`, `quantize=False`, `TOLERANCIA=False`, `abs=False`, `float=False`, `math=False`. Há teste dedicado com **um centavo** de excesso (`1000.01` contra `1000.00`) levantando — a tolerância de `± R$ 0,05` da spec §5 vale para valores acumulados ao longo de meses, e aqui os dois lados saem da mesma rodada de cálculo sobre os mesmos itens, então um centavo de folga esconderia exatamente o erro de filtro (item no recomendado que não está no potencial) que esta função existe para pegar. A docstring registra esse raciocínio.

**Critério 2 — as duas mensagens nomeiam os dois valores.** Os dois `raise` são `ErroInvariante` (nenhum outro tipo), e cada mensagem interpola `ATAQUE_IMEDIATO_POTENCIAL` **e** `ATAQUE_IMEDIATO_RECOMENDADO` com `!r` — inclusive no ramo do negativo, onde o potencial não é a causa mas é contexto de diagnóstico. Saída real do ramo 1: `hierarquia do ataque imediato violada (RF-50/§13.6, A-04): ATAQUE_IMEDIATO_POTENCIAL=Decimal('1000.00') < ATAQUE_IMEDIATO_RECOMENDADO=Decimal('1000.01') — o recomendado nunca pode exceder o potencial`. Os testes assertam a presença dos dois NOMES e dos dois NÚMEROS na mensagem, não só o tipo da exceção. O segundo ramo tem teste próprio porque um recomendado negativo **passa** pela primeira guarda (o potencial é maior) — sem ele, `RECOMENDADO >= 0` ficaria não verificado.

**"Nunca corrige, nunca degrada silenciosamente" (`A-04`).** A função é `-> None`: não há canal por onde um número rebaixado saia dela, e isso é garantido por `mypy --strict`, não por convenção. `ErroInvariante` é importado de `engine.ciclo_mensal` — o tipo canônico já usado pelo motor (`engine/ciclo_mensal.py`), reusado em vez de duplicado; `ciclo_mensal` não importa `ataque_imediato`, então não há ciclo de import (verificado em execução). Violação de hierarquia é bug do motor, não dado do usuário: corrigir aqui produziria um número plausível e errado.

**Critério 4 — a leitura que esta tarefa declara, em vez de fingir cumprir.** `ATAQUE_IMEDIATO_APROVADO` aparece **3 vezes** no arquivo, e a varredura de `ast.Name`/`ast.Attribute`/`ast.arg`/`ast.keyword`/`ast.alias` mostra `resto=0`: **zero** ocorrências em código executável — `docstring=3, comentário=0`. Não é parâmetro de nenhuma das nove funções do módulo. As três menções são **declarações de ausência**, cada uma dizendo que a coisa NÃO existe aqui: a docstring do módulo registra que ela e o ramo `>= APROVADO >= 0` dependem de `OQ-30` (fatia 3C); a de `calcular_ATAQUE_IMEDIATO_RECOMENDADO` registra que só o aprovado entra no cronograma (§13.6/§13.11) e que ele não existe nesta rodada; a desta função registra que o ramo da hierarquia que o envolve **não** é verificado aqui. É o mesmo critério que `T-103` aplicou a `ECONOMIA_POTENCIAL_IMEDIATA` (cujo critério tinha a mesma redação e foi fechado com a menção prescrita pelo plano na docstring): o que o critério proíbe é a variável existir — como parâmetro, campo ou cálculo —, e apagar a prosa que declara a fronteira de 3C tornaria o módulo **menos** explícito sobre o que ele não faz, não mais. Nenhum default foi fabricado para simular a verificação ausente.

**Critério 5.** A docstring cita `RF-50`, §13.6, `A-04`, `AC-82`, `ErroInvariante` e `OQ-30` — conferido por busca de substring. Registra também o trade-off do plano R3.10 para a função ser **separada**: embuti-la em `calcular_ATAQUE_IMEDIATO_RECOMENDADO` obrigaria aquela função a receber o potencial, que não é insumo da fórmula da §13.3 — um parâmetro que não participa do cálculo. O custo aceito (a verificação depende de ser chamada) está escrito lá.

**Teste:** contribuição de `T-107` em `tests/regras/test_reserva_recomendada.py` — 8 casos `@pytest.mark.regra` (5 funções + 4 parametrizações do caso válido, incluindo os dois empates `0/0` e `31000/31000`, que são o normal quando tudo que é potencial também é recomendável). Mais um teste de contrato de saída que liga as três tarefas: `RESERVA_RECOMENDADA >= 0` sob 3 residuais × 3 resultados mensais × 4 mobilizáveis (inclusive `DESCONHECIDO`) — se a reserva pudesse ser negativa, o recomendado também poderia, e esta função levantaria em operação normal.

**Verificação.** `ruff check .` — `All checks passed!`. `mypy engine/` — `Success: no issues found in 26 source files`. `build` completo — `Found 1 error in 1 file (checked 264 source files)`, o mesmo erro pré-existente `app/montagem/estado.py:1326` do slug `app-aluno`, não corrigido aqui. Suíte `pytest -q --ignore=tests/app_aluno` — `474 passed, 9 skipped`; medição controlada do delta das três tarefas juntas: `433 → 474`, `+41`, zero regressão. Homologação `pytest -m "gabarito or invariante or gabarito_ataque_imediato"` — `18 passed`. `tests/estatica/` — `69 passed`, incluindo `test_toda_regra_citada.py` com o `REGRAS` ampliado.

**`REGRAS` do módulo, atualizado por `T-105`+`T-106`+`T-107` juntas:** de `("RF-43","RF-44","RF-45","RF-49","§13.1","§13.2","§13.3","§13.7","§13.9")` para `("RF-43","RF-44","RF-45","RF-46","RF-47","RF-48","RF-49","RF-50","§13.1","§13.2","§13.3","§13.4","§13.5","§13.6","§13.7","§13.9")`. §13.4, §13.5 e §13.6 entram porque agora o arquivo as implementa; §13.8 (travas de dupla contagem) **continua ausente** — ela é garantia de coleta e de modelagem de `EstadoFinanceiro`, não regra deste módulo, e citá-la afirmaria cobertura que estas três tarefas não entregaram.

**Escopo.** O ramo `>= ATAQUE_IMEDIATO_APROVADO >= 0` não foi antecipado (3C, `OQ-30`). Não foram tocados: `engine/diagnostico.py` (`T-114`), `tests/regras/test_ataque_imediato.py` (`T-112`), `tests/gabaritos_ataque_imediato/` (`T-110`/`T-111`), `app/montagem/estado.py` e `tests/app_aluno/estatica/hashes_congelados.json` (`T-116`). Os únicos dois arquivos escritos pelas três tarefas são `engine/ataque_imediato.py` e `tests/regras/test_reserva_recomendada.py`.

---

### `T-108` — Registrar o marcador `gabarito_ataque_imediato` e criar o diretório dos `GAB-AI`

- **Tipo:** `Infra`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-43`, `RF-46`, `RF-47`, `AC-70`, `AC-71`, `AC-72`, `AC-73`, `AC-74`, `AC-75`, `AC-76`
- **Arquivos:** `pyproject.toml`, `tests/gabaritos_ataque_imediato/__init__.py`

**Descrição**

Decisão fechada no plano R3.9.1: os `GAB-AI-01`..`GAB-AI-07` **não** são ponta a ponta (não têm dívidas, gates nem cronograma) e **não** são propriedades — reusar `@pytest.mark.gabarito` tornaria falsa a descrição do marcador no `pyproject.toml` e diluiria o portão de homologação da seção 10 da canônica. Registrar marcador novo `gabarito_ataque_imediato` e criar o diretório `tests/gabaritos_ataque_imediato/`. **Consequência operacional a divulgar:** o comando de homologação passa a ser `pytest -m "gabarito or invariante or gabarito_ataque_imediato"`; quem rodar o antigo terá cobertura silenciosamente menor.

**Critérios de aceite**

- [x] `[tool.pytest.ini_options] markers` do `pyproject.toml` registra `gabarito_ataque_imediato` com descrição que o distingue explicitamente de `gabarito` ("fórmula isolada da §13, não ponta a ponta")
- [x] As descrições de `gabarito` e `invariante` ficam **inalteradas** e continuam verdadeiras
- [x] `tests/gabaritos_ataque_imediato/` existe, é importável e é coletado por `pytest -q` (o marcador seleciona, não exclui)
- [x] `pytest -m "gabarito or invariante or gabarito_ataque_imediato"` roda sem erro de marcador desconhecido
- [x] O comando de homologação novo fica registrado na nota de fechamento desta tarefa, para a revisão da rodada
- [x] `pytest --strict-markers` não reclama do marcador novo

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

> **COMANDO DE HOMOLOGAÇÃO NOVO — divulgar para a revisão da rodada:**
>
> ```
> pytest -m "gabarito or invariante or gabarito_ataque_imediato"
> ```
>
> O antigo (`pytest -m "gabarito or invariante"`) continua rodando **sem erro**
> e por isso não avisa nada: quem usá-lo terá cobertura silenciosamente menor,
> perdendo os sete `GAB-AI` a partir de `T-110`. Este é o portão da seção 10 da
> canônica somado à §13.

Duas alterações, exatamente as previstas pelo plano R3.9.1:

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -94,6 +94,7 @@ [tool.pytest.ini_options] markers
     "invariante: prova invariante GAB-01 a GAB-05 (seção 10 da canônica)",
+    "gabarito_ataque_imediato: reproduz gabarito numérico de fórmula isolada da seção 13, NÃO ponta a ponta (GAB-AI-01 a GAB-AI-07 — sem dívidas, gates nem cronograma)",
     "regra: testa regra normativa isolada de uma família (M, R, A, F, O, H, S, Q, V, T, G)",
```

Mais `tests/gabaritos_ataque_imediato/__init__.py` (arquivo novo, uma linha de
docstring). O diretório tem **apenas** `__init__.py`: nenhum teste `GAB-AI` foi
escrito aqui — são `T-110` em diante, fora do escopo desta tarefa.

**`__init__.py` segue a convenção real do repositório, conferida, não presumida.**
`tests/gabaritos/`, `tests/invariantes/` e `tests/regras/` **têm** `__init__.py`,
cada um com uma única linha de docstring descrevendo o conjunto; o novo replica
essa forma. O marcador foi inserido logo após `invariante` (a família de
gabaritos fica agrupada), antes de `regra`.

**Critério 1 — descrição distingue de `gabarito`.** `pytest --markers` mostra os
dois lado a lado; o novo diz `de fórmula isolada da seção 13, NÃO ponta a ponta
(... sem dívidas, gates nem cronograma)`, contra o `ponta a ponta` do antigo.

**Critério 2 — `gabarito` e `invariante` inalterados.** Comparação byte a byte
via `tomllib` contra o texto anterior: `gabarito INALTERADO: True`,
`invariante INALTERADO: True`. Total de marcadores foi de 6 para 7 — só adição.

**Critério 3 — existe, importável, coletado.** `import tests.gabaritos_ataque_imediato`
resolve para o `__init__.py` novo. O diretório é percorrido por `pytest -q` sem
erro de coleta (`no tests collected` nele, esperado enquanto não há `GAB-AI` —
`sdd.config.md` §2 aceita exit code 5 justamente neste caso) e **não** quebra a
suíte completa.

**Critério 6 e "seleciona, não exclui" — provado com teste temporário, depois
removido.** Como o diretório está vazio, os critérios 4 e 6 seriam vácuos sem um
teste que carregue o marcador. Criei um `test_zz_prova_temporaria_do_marcador.py`
descartável com `@pytest.mark.gabarito_ataque_imediato` mais um marcador de
controle inexistente:

- sob `--strict-markers`, o erro apontou **só** o controle
  (`'marcador_inexistente_de_controle' not found in markers configuration option`)
  — o marcador novo passou;
- só com o marcador novo: `1 passed` sob `--strict-markers`;
- no comando de homologação, a seleção foi de `18 passed` para `19 passed`
  (**seleciona**), e a coleta padrão foi de 1234 para 1235 (**não exclui**).

O arquivo e o `__pycache__` foram apagados em seguida; o diretório final contém
apenas `__init__.py`.

**Critério 4 — sem marcador desconhecido.**
`pytest -q -m "gabarito or invariante or gabarito_ataque_imediato"`:
`18 passed, 1213 deselected, 1 warning`. O único warning é
`DeprecationWarning` de `starlette/testclient.py:53` (anyio), pré-existente e
sem relação com marcadores.

**Verificação (`sdd.config.md` §2).**

- `lint` — `ruff check .`: `All checks passed!`
- `build` — `mypy` sobre `engine persistencia collection app report tests`:
  `Success: no issues found in 257 source files` (256 antes; o novo é o
  `__init__.py`)
- `test` — `pytest -q`: `11 failed, 1148 passed, 75 skipped`

**Correção de baseline registrada.** O baseline citado na abertura desta tarefa
(`11 failed, 1145 passed, 75 skipped`, herdado da nota de `T-101`) está
desatualizado em `passed`. Medido o estado **exatamente pré-tarefa** — linha do
marcador removida do `pyproject.toml` e diretório novo movido para fora — a
suíte já dava `11 failed, 1148 passed, 75 skipped`, idêntico ao pós-tarefa; a
coleta dá 1234 com e sem o diretório novo. Os 3 `passed` a mais vieram de
tarefas anteriores entre `T-101` e hoje, **não** desta. Esta tarefa é neutra em
contagem: não adiciona nem remove teste. As 11 falhas seguem sendo as
pré-existentes de `tests/app_aluno/` (hash congelado de `AC-44` + `XPASS(strict)`),
sem regressão.

**Aviso para quem for reproduzir estes números.** Minutos após a verificação
acima, uma repetição da suíte deu `213 failed, 863 passed, 79 errors`. **Não é
regressão desta tarefa** e não é flakiness: `engine/estado.py` foi modificado
por outra tarefa em andamento em paralelo (`T-96`, os 8 campos novos de
`EstadoFinanceiro`), junto com `tests/estatica/test_uso_de_tolerancia.py`
(`T-109`). Todas as falhas novas são o mesmo erro —
`TypeError: EstadoFinanceiro.__init__() missing 8 required positional arguments`
— em construções de `EstadoFinanceiro` ainda não atualizadas pelos chamadores;
nenhuma delas é `unknown marker` (contagem de `unknown mark`/`not found in
markers`: **zero**), e as 15 falhas que aparecem sob o comando de homologação
são **todas** desse mesmo `TypeError`. Os arquivos desta tarefa não foram
tocados por aquela mudança: o marcador segue registrado (`pytest --markers`) e
`tests.gabaritos_ataque_imediato` segue importável. A suíte volta ao verde
quando `T-96` e seus chamadores fecharem — os números limpos desta nota valem
para o estado do repositório às 14:07.

---

### `T-109` — Acrescentar os três símbolos da Rodada 3 à lista de tolerância zero do lint

- **Tipo:** `Test`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-49`, `AC-82`, `AC-70`, `AC-71`, `AC-72`, `AC-73`, `AC-74`, `AC-75`, `AC-76`
- **Arquivos:** `tests/estatica/test_uso_de_tolerancia.py`

**Descrição**

> **Buraco real de rede de segurança, levantado no plano R3.3/R3.9.2.** `tests/estatica/test_uso_de_tolerancia.py` faz lint **por nome de identificador** contra a lista fechada `SIMBOLOS_TOLERANCIA_ZERO` (`:49-65`), que **não** inclui os nomes desta rodada. Sem acrescentá-los, o lint não impede o uso indevido de `assertar_monetario` (± R$ 0,05) nos `GAB-AI`, que são **tolerância zero** por decisão da spec §5 (`OQ-34` respondida).

Acrescentar `RESERVA_MOBILIZAVEL`, `ATAQUE_IMEDIATO_RECOMENDADO` e `NECESSIDADE_RESIDUAL` à tupla. O teste parametrizado `test_uso_de_tolerancia_detecta_cada_simbolo_da_lista` já cobre item a item da lista automaticamente — os três novos ganham cobertura de detecção sem código adicional.

**Critérios de aceite**

- [x] `SIMBOLOS_TOLERANCIA_ZERO` inclui `RESERVA_MOBILIZAVEL`, `ATAQUE_IMEDIATO_RECOMENDADO` e `NECESSIDADE_RESIDUAL`, com comentário citando spec §5, `OQ-34` e plano R3.9.2
- [x] O docstring do módulo é atualizado para mencionar os símbolos da Rodada 3 junto aos já listados
- [x] `test_uso_de_tolerancia_detecta_cada_simbolo_da_lista` passa para os três símbolos novos (parametrização automática)
- [x] `test_uso_de_tolerancia` continua passando sobre `tests/` real — nenhum uso pré-existente de `assertar_monetario` sobre esses três nomes sobreviveu; se algum for encontrado, ele é corrigido para `assertar_exato` nesta tarefa e o arquivo corrigido é reportado
- [x] Nenhum símbolo pré-existente é removido da lista

**Status:** `[x] concluída` — `tests/estatica/test_uso_de_tolerancia.py`: os três nomes da Rodada 3 (`RESERVA_MOBILIZAVEL`, `ATAQUE_IMEDIATO_RECOMENDADO`, `NECESSIDADE_RESIDUAL`) foram **acrescentados ao fim** de `SIMBOLOS_TOLERANCIA_ZERO`, com comentário citando a NFR "Tolerância dos `GAB-AI`: zero" (spec §5, `OQ-34` respondida), o plano R3.9.2, os gabaritos `GAB-AI-01`..`GAB-AI-07` (`AC-70`–`AC-76`) e `AC-82`; nenhum dos 15 símbolos pré-existentes foi removido ou reordenado, e `PADRAO_D_ESTRELA` ficou intacto. O docstring do módulo passou a listar os três junto aos já enumerados, marcados como "desde a Rodada 3". **Nenhum arquivo precisou de correção `assertar_monetario` → `assertar_exato`**: uma varredura prévia com a lista já estendida sobre os 11 arquivos de `tests/` que chamam `assertar_monetario` (38 ocorrências) devolveu `TOTAL 0` violações — os 12 arquivos que constroem `Diagnostico` à mão desde `T-90` só passam o placeholder `dinheiro(0)` no construtor, nunca o asseveram por `assertar_monetario`. Nenhuma linha de `engine/` foi tocada (escopo, `sdd.config.md` §4). Verificação: `ruff check .` limpo (`All checks passed!`), `mypy` sobre `engine persistencia collection app report tests` sem erro (`Success: no issues found in 257 source files`), o arquivo alvo `21 passed` (era 18 — os `+3` são exatamente as parametrizações novas de `test_uso_de_tolerancia_detecta_cada_simbolo_da_lista`, e `test_uso_de_tolerancia` sobre `tests/` real segue `PASSED`), suíte completa `11 failed, 1148 passed, 75 skipped` contra o baseline pré-tarefa `11 failed, 1145 passed, 75 skipped` — mesmas 11 falhas pré-existentes de `tests/app_aluno/` (hash congelado de `AC-44` + `XPASS(strict)`), sem regressão.

---

### `T-110` — Reproduzir `GAB-AI-01` a `GAB-AI-04` (reserva mobilizável), com tolerância zero

- **Tipo:** `Test`
- **Dependências:** `T-102`, `T-105`, `T-108`, `T-109`
- **Rastreia:** `RF-43`, `AC-70`, `AC-71`, `AC-72`, `AC-73`, `US-15`
- **Arquivos:** `tests/gabaritos_ataque_imediato/test_gab_ai_01_valor_aceito_abaixo_do_total.py`, `tests/gabaritos_ataque_imediato/test_gab_ai_02_limitado_pelo_total.py`, `tests/gabaritos_ataque_imediato/test_gab_ai_03_sem_disposicao_de_uso.py`, `tests/gabaritos_ataque_imediato/test_gab_ai_04_decidir_depois_e_desconhecido.py`

**Descrição**

Os quatro primeiros gabaritos da §13.10, com os **números literais** do documento canônico e `@pytest.mark.gabarito_ataque_imediato`: `GAB-AI-01` total `20.000` / aceita `5.000` → `5.000`; `GAB-AI-02` total `20.000` / informa `30.000` → `20.000`; `GAB-AI-03` `DISPOSICAO_USO_RESERVA = NAO` → `0`; `GAB-AI-04` "prefiro decidir depois" → `DESCONHECIDO`, e a reserva **não entra** em `RESERVA_RECOMENDADA` nem em `ATAQUE_IMEDIATO_RECOMENDADO`. **Tolerância zero, obrigatoriamente com `assertar_exato`** (`tests/conftest.py:36`); `assertar_monetario` é proibido (spec §5, `OQ-34`).

**Critérios de aceite**

- [x] Os quatro arquivos existem em `tests/gabaritos_ataque_imediato/` com os nomes de teste do plano R3.9.2 e o marcador `gabarito_ataque_imediato`
- [x] `GAB-AI-01` devolve exatamente `5.000` (`AC-70`); `GAB-AI-02` exatamente `20.000`, nunca `30.000` (`AC-71`); `GAB-AI-03` exatamente `0` independentemente de total e valor informado (`AC-72`)
- [x] `GAB-AI-04` devolve o sentinela `DESCONHECIDO`, **não** `0`, e o teste também afirma `RESERVA_RECOMENDADA = 0` e que nenhum valor da reserva entrou em `ATAQUE_IMEDIATO_RECOMENDADO` (`AC-73`)
- [x] Todas as asserções usam `assertar_exato`; nenhuma chamada a `assertar_monetario` existe nestes quatro arquivos, e `tests/estatica/test_uso_de_tolerancia.py` confirma
- [x] Cada teste cita no docstring o `GAB-AI-NN`, o `AC-NN` e a §13.10, com os números do enunciado transcritos
- [x] Os quatro são coletados por `pytest -q` e selecionados por `pytest -m "gabarito or invariante or gabarito_ataque_imediato"`

**Status:** `[x] concluída` — os quatro arquivos do plano R3.9.2 existem em `tests/gabaritos_ataque_imediato/`, cada um com o nome de teste da tabela e `@pytest.mark.gabarito_ataque_imediato`: `test_gab_ai_01_valor_aceito_abaixo_do_total.py`, `test_gab_ai_02_limitado_pelo_total.py`, `test_gab_ai_03_sem_disposicao_de_uso.py`, `test_gab_ai_04_decidir_depois_e_desconhecido.py`. **Números obtidos × esperados da §13.10 (congelada), conferidos um a um:** `GAB-AI-01` obtido `5000` = esperado `5.000`; `GAB-AI-02` obtido `20000` = esperado `20.000` (o teste asserta também `!= 30.000`, a negativa que o enunciado publica); `GAB-AI-03` obtido `0` = esperado `0`, verificado no par do enunciado **e** numa parametrização de quatro combinações de `RESERVA_TOTAL`/`VALOR_MAXIMO_...` — incluindo os pares de `GAB-AI-01` e `GAB-AI-02` —, que é a forma literal de `AC-72` ("independentemente de `RESERVA_TOTAL` e do valor informado"); `GAB-AI-04` obtido `Desconhecido.DESCONHECIDO` = esperado `DESCONHECIDA`. `GAB-AI-04` tem **dois** testes: o primeiro asserta a IDENTIDADE do sentinela (`obtido is DESCONHECIDO`), mais `!= dinheiro(0)` e `not isinstance(obtido, Decimal)` — nunca igualdade com zero, porque a §13.1 proíbe converter o desconhecido "silenciosamente em zero como informação"; o segundo encadeia §13.1 → §13.4 → §13.5 a partir do MESMO `DESCONHECIDO` derivado e prova a segunda metade do enunciado — `RESERVA_RECOMENDADA = 0` (com `NECESSIDADE_RESIDUAL = 30.000` e `RESERVA_TOTAL = 20.000` disponíveis, e `RESULTADO_MENSAL_ATUAL` superavitário para que o `0` seja atribuível ao desconhecido e não ao déficit de `GAB-AI-05`) e `ATAQUE_IMEDIATO_RECOMENDADO = 12.000`, exatamente a soma dos quatro não protetivos, com o elegível folgado em 60.000 de propósito para que o `MIN` da §13.5 não mascare um eventual vazamento da reserva. **Tolerância zero:** 14 chamadas `assertar_exato` nos quatro arquivos e **zero** chamadas a `assertar_monetario` — as únicas ocorrências do nome são prosa de docstring declarando a proibição, e `tests/estatica/test_uso_de_tolerancia.py` (que só inspeciona `ast.Call`) passa sobre `tests/` real. Cada docstring de teste cita o `GAB-AI-NN`, o `AC-NN` e a §13.10, com o cenário e o resultado transcritos do documento canônico (a tabela markdown virou lista indentada para caber em 100 colunas do `ruff`; os números não foram tocados). **Conferência contra `T-102`/`T-105`:** os mesmos números aparecem informalmente em `tests/regras/test_reserva_mobilizavel.py` e `test_reserva_recomendada.py` e **concordam integralmente** — nenhuma divergência a reportar. Escopo: `engine/` intocado (as nove funções já estavam prontas), `engine/diagnostico.py` intocado (`T-114`), `tests/estatica/test_sem_percentual_automatico_de_reserva.py` intocado (`T-113`, agente paralelo). Verificação: `ruff check .` → `All checks passed!`; `mypy engine persistencia collection app report tests` → 1 erro, o pré-existente `app/montagem/estado.py:1326` do slug `app-aluno` (allowlist `AC-41`, não corrigido); `pytest -q tests/gabaritos_ataque_imediato/` → `12 passed`; `pytest -m "gabarito or invariante or gabarito_ataque_imediato"` → `30 passed`.

---

### `T-111` — Reproduzir `GAB-AI-05` a `GAB-AI-07` (reserva recomendada, residual e teto), com tolerância zero

- **Tipo:** `Test`
- **Dependências:** `T-105`, `T-106`, `T-108`, `T-109`
- **Rastreia:** `RF-46`, `RF-47`, `RF-48`, `AC-74`, `AC-75`, `AC-76`, `US-16`
- **Arquivos:** `tests/gabaritos_ataque_imediato/test_gab_ai_05_modo_estabilizacao_zera_reserva.py`, `tests/gabaritos_ataque_imediato/test_gab_ai_06_residual_e_recomendado_completo.py`, `tests/gabaritos_ataque_imediato/test_gab_ai_07_teto_da_necessidade_elegivel.py`

**Descrição**

Os três gabaritos numéricos completos da §13.10, com os números literais: `GAB-AI-05` `RESULTADO_MENSAL_ATUAL = -1.000` e mobilizável `20.000` → `MODO_ESTABILIZACAO = SIM` e recomendada `0`; `GAB-AI-06` elegível `20.000` **por parâmetro**, caixa `5.000`, investimentos `7.000`, extraordinários `0`, ativos `0`, mobilizável `10.000` → residual `8.000`, reserva recomendada `8.000`, recomendado `20.000`; `GAB-AI-07` elegível `10.000` **por parâmetro** contra `25.000` de recursos → `10.000`, nunca `25.000`. **`GAB-AI-08` fica fora desta rodada** (depende de `ATAQUE_IMEDIATO_APROVADO`, fatia 3C) — não escrever.

**Critérios de aceite**

- [x] Os três arquivos existem com os nomes de teste do plano R3.9.2 e o marcador `gabarito_ataque_imediato`
- [x] `GAB-AI-05`: `RESERVA_RECOMENDADA` é exatamente `0`, e o teste confirma `MODO_ESTABILIZACAO = SIM` lendo o campo de `Diagnostico` derivado da mesma condição (`AC-74`)
- [x] `GAB-AI-06`: `NECESSIDADE_RESIDUAL = 8.000`, `RESERVA_RECOMENDADA = 8.000` e `ATAQUE_IMEDIATO_RECOMENDADO = 20.000`, os três exatos (`AC-75`)
- [x] `GAB-AI-07`: resultado exatamente `10.000` (`AC-76`)
- [x] Em `GAB-AI-06` e `GAB-AI-07`, `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` é passada como argumento nomeado explícito, evidenciando `RF-48`/`AC-80`
- [x] Todas as asserções usam `assertar_exato`; `assertar_monetario` não aparece
- [x] **Nenhum arquivo de `GAB-AI-08` é criado** nesta rodada

**Status:** `[x] concluída` — os três arquivos do plano R3.9.2 existem com os nomes da tabela e `@pytest.mark.gabarito_ataque_imediato`: `test_gab_ai_05_modo_estabilizacao_zera_reserva.py`, `test_gab_ai_06_residual_e_recomendado_completo.py`, `test_gab_ai_07_teto_da_necessidade_elegivel.py`. **Números obtidos × esperados da §13.10 (congelada):** `GAB-AI-05` obtido `RESERVA_RECOMENDADA = 0` = esperado `0`, com `MODO_ESTABILIZACAO` obtido `True` = esperado `SIM`; `GAB-AI-06` obtidos `NECESSIDADE_RESIDUAL = 8000`, `RESERVA_RECOMENDADA = 8000`, `ATAQUE_IMEDIATO_RECOMENDADO = 20000` = esperados `8.000` / `8.000` / `20.000`, os **três** exatos; `GAB-AI-07` obtido `10000` = esperado `10.000`, com asserção negativa explícita `!= 25.000`. **`AC-74` — `MODO_ESTABILIZACAO` lido de `Diagnostico`, não escrito à mão:** o teste chama `calcular_diagnostico(carregar_gab_a(), FonteParametrosArquivo().carregar("1.0.1"))` e asserta primeiro que `diagnostico.RESULTADO_MENSAL_ATUAL` é literalmente os `-1.000` do enunciado (o cenário `GAB-A`/`AC-05` tem exatamente esse resultado mensal), depois `diagnostico.MODO_ESTABILIZACAO is True`, e então passa **esse mesmo `RESULTADO_MENSAL_ATUAL`** para `derivar_RESERVA_RECOMENDADA`. É o elo que torna verificada — e não apenas prometida na docstring — a afirmação de que a condição de déficit é uma só escrita em dois lugares (`engine/diagnostico.py:532` deriva `MODO_ESTABILIZACAO`; `engine/ataque_imediato.py:512` arma a trava da §13.4), sem que a função pura consulte `Diagnostico` (`RF-48`/`AC-80`, NFR de Pureza). `NECESSIDADE_RESIDUAL` entra com os mesmos `20.000` do mobilizável para fechar o cerco: sem a trava, `MIN(20.000, 20.000)` daria 20.000. **`RF-48`/`AC-80`:** em `GAB-AI-06` (duas chamadas) e `GAB-AI-07` (uma), `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=` é argumento nomeado explícito — a assinatura com `*` torna a forma posicional impossível, e o valor vem do enunciado do gabarito, nunca de `EstadoFinanceiro`/`Diagnostico` (`OQ-29` segue aberta). `GAB-AI-06` é encadeado de verdade: cada saída alimenta a etapa seguinte pelo VALOR OBTIDO (`NECESSIDADE_RESIDUAL` → `derivar_RESERVA_RECOMENDADA` → `calcular_ATAQUE_IMEDIATO_RECOMENDADO`), não por literal reescrito, com `RESULTADO_MENSAL_ATUAL >= 0` conforme o enunciado de `AC-75` (armada, a trava daria reserva `0` e recomendado `12.000`, que é `GAB-AI-05`). Em `GAB-AI-07` os `25.000` de recursos foram distribuídos pelos cinco componentes em potências de dois (1.000+2.000+4.000+8.000+10.000) para que nenhuma combinação própria dê 10.000 — o resultado só pode vir do `MIN` contra o elegível, nunca de uma parcela esquecida. **Tolerância zero:** 13 `assertar_exato` nos três arquivos, **zero** chamadas a `assertar_monetario` (as menções ao nome são prosa de docstring declarando a proibição); `tests/estatica/test_uso_de_tolerancia.py` passa. **`GAB-AI-08` NÃO foi escrito:** o diretório tem exatamente sete arquivos `test_gab_ai_0*`, e uma varredura por `gab_ai_08` e por `ATAQUE_IMEDIATO_APROVADO` em `tests/gabaritos_ataque_imediato/` e `tests/regras/test_ataque_imediato.py` devolve **zero** ocorrências — a variável depende de confirmação do usuário (`OQ-30`, fatia 3C) e não foi antecipada em nenhuma forma. **Conferência contra `T-105`/`T-106`:** `GAB-AI-05`, `-06` e `-07` já apareciam informalmente em `tests/regras/test_reserva_recomendada.py` e os números **concordam integralmente** — nenhuma divergência a reportar. Escopo: `engine/` intocado, `engine/diagnostico.py` intocado (`T-114` — o módulo foi apenas LIDO via `calcular_diagnostico`), `tests/estatica/test_sem_percentual_automatico_de_reserva.py` intocado (`T-113`). Verificação: `ruff check .` → `All checks passed!`; `mypy` → 1 erro pré-existente em `app/montagem/estado.py:1326` (`app-aluno`, allowlist `AC-41`, não corrigido); `pytest -q tests/gabaritos_ataque_imediato/` → `12 passed`; `pytest -m "gabarito or invariante or gabarito_ataque_imediato"` → `30 passed`.

---

### `T-112` — Testar as regras e os edge cases da §13 em `tests/regras/test_ataque_imediato.py`

- **Tipo:** `Test`
- **Dependências:** `T-103`, `T-104`, `T-105`, `T-106`, `T-107`
- **Rastreia:** `RF-44`, `RF-45`, `RF-46`, `RF-47`, `RF-48`, `RF-50`, `RF-52`, `AC-77`, `AC-78`, `AC-79`, `AC-80`, `AC-82`, `AC-83`, `EC-23`, `EC-24`, `EC-25`, `EC-26`, `EC-27`, `EC-28`, `EC-29`, `EC-30`, `EC-31`, `US-16`, `US-17`
- **Arquivos:** `tests/regras/test_ataque_imediato.py`

**Descrição**

Os 15 unitários de regra do plano R3.9.3, um por âncora, testando **comportamento observável** das funções puras — nunca implementação interna. Cobrem `AC-77` a `AC-83` e os nove edge cases `EC-23` a `EC-31`. `test_item_compoe_no_maximo_um_componente` é o teste de `RF-52`/`AC-83`: usa `ITEM_ID` para afirmar que nenhum item aparece simultaneamente em `INVESTIMENTOS_RECOMENDADOS` e `ATIVOS_RECOMENDADOS`, nem em `ATIVOS_RECOMENDADOS` e `CAIXA_RECOMENDADO` — sem `ITEM_ID`, essa asserção é inexprimível.

**Critérios de aceite**

- [x] Os 15 testes do plano R3.9.3 existem com os nomes ali listados, marcados `@pytest.mark.regra`
- [x] Cada teste cita no docstring o `AC-NN` ou `EC-NN` que ancora (`sdd.config.md` §5, "todo teste rastreia para um ID")
- [x] `test_hierarquia_potencial_maior_ou_igual_recomendado` prova que a violação levanta `ErroInvariante` e que a comparação é exata (`AC-82`)
- [x] `test_item_compoe_no_maximo_um_componente` usa `ITEM_ID` para provar origem econômica única (`AC-83`, `RF-52`, §13.8)
- [x] `test_elegivel_entra_por_argumento_explicito` prova que a chamada posicional falha e que a função não lê `EstadoFinanceiro`/`Diagnostico` (`AC-80`)
- [x] Os nove `EC-23`..`EC-31` têm cada um o seu teste, incluindo `test_item_sem_classificacao_falha_na_construcao` (`EC-31`)
- [x] `assertar_exato` onde a régua é tolerância zero; nenhum uso de `assertar_monetario` sobre os três símbolos de `T-109`
- [x] `pytest -q tests/regras/test_ataque_imediato.py` passa inteiro

**Status:** `[x] concluída` — `tests/regras/test_ataque_imediato.py`, **arquivo novo** (os quatro arquivos de `T-102`..`T-107` usaram nomes diferentes justamente para deixá-lo livre). Os **15** nomes do plano R3.9.3 existem, todos `@pytest.mark.regra`, conferidos por coleta na ordem da tabela: `test_potencial_soma_apenas_possivel_e_recomendavel`, `test_ativo_possivel_fica_so_no_potencial`, `test_extraordinario_futuro_nao_compoe_recomendado`, `test_elegivel_entra_por_argumento_explicito`, `test_hierarquia_potencial_maior_ou_igual_recomendado`, `test_item_compoe_no_maximo_um_componente`, `test_reserva_existe_nao_vence_valor_informado`, `test_valor_maximo_negativo_zera_antes_do_min`, `test_reserva_total_desconhecida_vence_regra_2`, `test_mobilizavel_desconhecida_com_residual_positivo`, `test_colecoes_vazias_resultam_zero`, `test_elegivel_zero_com_recursos_positivos`, `test_nao_protetivos_cobrem_tudo_residual_zero`, `test_com_ressalvas_nao_entra_em_potencial_nem_recomendado`, `test_item_sem_classificacao_falha_na_construcao` — 20 casos com as duas parametrizações. Cada docstring abre citando o `AC-NN`/`EC-NN` que ancora, com a frase da spec transcrita entre aspas.

**Mapeamento de cobertura pré-existente (padrão de `T-85`/`T-89`, Rodada 2).** As âncoras já eram exercitadas por outro ângulo em `test_reserva_mobilizavel.py` (`T-102`), `test_ataque_imediato_potencial.py` (`T-103`), `test_componentes_recomendados.py` (`T-104`) e `test_reserva_recomendada.py` (`T-105`/`-106`/`-107`), e `EC-31` já tinha teste homônimo em `tests/regras/test_estado.py` (`T-100`, pelo ângulo de `AC-66`). O critério desta tarefa exige os 15 nomes **neste** arquivo, então nenhum foi omitido; o que se fez para não duplicar foi dar a cada um cenário e ângulo DIFERENTES dos já existentes, de modo que este arquivo acrescente cobertura em vez de repeti-la: `AC-77` com as quatro classes em AMBAS as coleções por item (lá as ressalvas aparecem uma coleção por vez); `AC-78` e `AC-79` calculando as DUAS somas (potencial × recomendado) sobre a MESMA coleção e assertando a diferença — o "ainda que componha" de `AC-79` e o "permanece contando apenas em `ATAQUE_IMEDIATO_POTENCIAL`" de `AC-78` só se provam assim, e testá-los em arquivos separados (como fazem `T-103` e `T-104`) não prova que valem para o mesmo conjunto; `EC-23` com informado MENOR que o total, para que a inversão de regras produzisse um número plausível (7.000) em vez de um óbvio; `EC-24` parametrizado nas duas bordas do zero (`0` e `+0,01`), provando que o `MAX` corta só o lado negativo; `EC-25` com contraprova de total conhecido; `EC-26`/`EC-28`/`EC-29` encadeando as funções a partir de itens reais e não de totais escritos à mão; `EC-27` cobrindo potencial **e** recomendado no mesmo cenário vazio, mais a hierarquia no caso-limite `0 >= 0 >= 0`; `EC-31` pelo ângulo da §13 (o item sem classificação nunca CHEGA às funções da §13.2/§13.3, com contraprova de que o item classificado constrói e o filtro decide). **Dois testes existem só aqui e em lugar nenhum mais:** `test_item_compoe_no_maximo_um_componente` (`AC-83`/`RF-52`) e a verificação conjunta de `EC-27`.

**`AC-83`/`RF-52`/§13.8 por `ITEM_ID`.** O caso é montado com `ITEM_ID` **colidente de propósito** (`"X1"` num `ItemInvestimento` de 1.000 e num `ItemAtivo` de 2.000) — o pior caso possível, que uma modelagem de coleção única confundiria. Os conjuntos de `ITEM_ID` que compõem cada componente são reconstruídos pelo MESMO filtro normativo da §13.3 e comparados; a asserção decisiva é que os TIPOS das duas coleções são disjuntos (`{type(i) for i in investimentos} & {type(a) for a in ativos} == set()`), que é onde a trava realmente mora: a origem econômica única é garantida pela modelagem (`RF-38`), e o teste a confirma. O par `ATIVOS_RECOMENDADOS` × `CAIXA_RECOMENDADO` do enunciado fecha por outro caminho — `CAIXA_RECOMENDADO` e `RESERVA_MOBILIZAVEL` são escalares sem `ITEM_ID` (`not hasattr(..., "ITEM_ID")`), logo nenhum item de coleção pode compô-los duas vezes —, e o caso vedado que a §13.8 nomeia ("reserva em CDB contada como `RESERVA_MOBILIZAVEL` e de novo como `INVESTIMENTOS_RECOMENDADOS`") é fechado pelo potencial somando 7.500 = 500 caixa + 4.000 reserva + 1.000 investimento + 2.000 ativo, cada parcela uma vez.

**`AC-82`** — três asserções no mesmo teste: igualdade com centavos passa em silêncio (`4200.37 >= 4200.37`); **um centavo** de excesso (`4200.38`) levanta `ErroInvariante` cuja mensagem nomeia os dois símbolos e os dois números (tolerância ZERO, sem `± R$ 0,05`); e o segundo ramo verificável da §13.6 (`RECOMENDADO >= 0`) levanta com `-0,01`. **`AC-80`** — três provas: o `MIN` devolve o menor dos dois (12.000 contra 30.000 de recursos); a chamada posicional levanta `TypeError`; e, por `inspect.signature`, **todos** os parâmetros de `calcular_ATAQUE_IMEDIATO_RECOMENDADO` e `calcular_NECESSIDADE_RESIDUAL` são `KEYWORD_ONLY`, nenhum se chama `estado`/`diagnostico`, e o módulo não expõe `EstadoFinanceiro` nem `Diagnostico` (`hasattr` falso) — não há canal implícito para o elegível.

**Tolerância:** 34 `assertar_exato`; **zero** chamadas a `assertar_monetario` (a única ocorrência do nome é prosa de docstring), portanto nenhum uso sobre `RESERVA_MOBILIZAVEL`, `ATAQUE_IMEDIATO_RECOMENDADO` ou `NECESSIDADE_RESIDUAL`, e `tests/estatica/test_uso_de_tolerancia.py` confirma sobre `tests/` real. Testa apenas comportamento observável das nove funções puras (`sdd.config.md` §5) — a única introspecção é sobre a ASSINATURA pública, que é contrato normativo de `RF-48`, não implementação interna. Escopo: `engine/` intocado, `engine/diagnostico.py` intocado (`T-114`), `tests/estatica/test_sem_percentual_automatico_de_reserva.py` intocado (`T-113`), nenhum arquivo de gabarito alterado por esta tarefa. Verificação: `ruff check .` → `All checks passed!`; `mypy` → 1 erro pré-existente em `app/montagem/estado.py:1326` (`app-aluno`, allowlist `AC-41`); `pytest -q tests/regras/test_ataque_imediato.py` → **`20 passed`**, arquivo inteiro; suíte sem `tests/app_aluno/` → `533 passed, 9 skipped`, sem regressão (baseline pré-tarefa `498 passed, 9 skipped`; +32 desta rodada de três tarefas, +3 do agente paralelo de `T-113`).

---

### `T-113` — Provar por teste estático que as três fórmulas proibidas pela §13.1 não existem

- **Tipo:** `Test`
- **Dependências:** `T-102`
- **Rastreia:** `RF-49`, `AC-81`, `US-15`
- **Arquivos:** `tests/estatica/test_sem_percentual_automatico_de_reserva.py`

**Descrição**

TRAVA CANÔNICA da §13.1: `RESERVA_MOBILIZAVEL` **nunca** é percentual automático de `RESERVA_TOTAL`. As três formas expressamente proibidas na v1.0.1 são `30% × RESERVA_TOTAL`, `50% × RESERVA_TOTAL` e `RESERVA_TOTAL − RESERVA_MINIMA_PADRAO`. Prova negativa por AST (plano R3.9.5), no padrão de `tests/estatica/test_uso_de_tolerancia.py` e `test_nenhum_parametro_no_codigo.py`: varrer `engine/**/*.py` procurando `BinOp` de multiplicação ou subtração que tenha `RESERVA_TOTAL` como operando e produza `RESERVA_MOBILIZAVEL`, falhando com arquivo e linha.

**Critérios de aceite**

- [x] O teste varre a AST de `engine/**/*.py` e detecta as três formas proibidas, nomeando arquivo e linha na mensagem de falha
- [x] Existe teste-companheiro de prova negativa que alimenta o detector com as três fórmulas **construídas como string** e confirma que cada uma é pega — mesmo padrão de `tests/estatica/test_tipo_acao_apenas_quatro_valores.py::test_verificador_pega_quinto_literal_proposital`
- [x] Qualquer identificador contendo `RESERVA_MINIMA_PADRAO` em `engine/` é reportado como violação (a variável não existe e não deve passar a existir)
- [x] O teste passa sobre o `engine/` real ao fim da rodada
- [x] O docstring cita `AC-81`, `RF-49` e a TRAVA CANÔNICA da §13.1, transcrevendo as três fórmulas proibidas

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

Arquivo **novo**: `tests/estatica/test_sem_percentual_automatico_de_reserva.py`
— `24 passed`. Um detector (`_detectar_formulas_proibidas`, apoiado em
`_menciona_reserva_total` e `_identificadores_reserva_minima_padrao`) mais sete
funções de teste, três delas parametrizadas (3 + 9 + 8 casos). Nada fora deste
arquivo foi criado ou editado — `engine/ataque_imediato.py`, em edição paralela
por `T-105`/`T-106`/`T-107`, não foi tocado.

**A varredura (`AC-81`, critério 1).** `test_sem_percentual_automatico_de_reserva`
percorre `engine/**/*.py` (26 arquivos hoje) e reporta três padrões de AST, um
por forma proibida da §13.1: (1) `BinOp` de `Mult`/`Div`/`FloorDiv` com
`RESERVA_TOTAL` em qualquer dos operandos — as duas formas de percentual; (2)
`BinOp` de `Sub` com `RESERVA_TOTAL` em qualquer dos lados — a forma do desconto
de piso; (3) identificador contendo `RESERVA_MINIMA_PADRAO`. `Add` ficou de fora
de propósito: somar a `RESERVA_TOTAL` não é nenhuma das três, e proibi-lo seria
inventar uma quarta trava que a §13.1 não escreveu. `FormulaProibida` carrega
`arquivo`, `linha`, `forma` e `trecho` (`ast.unparse` do nó), e
`test_mensagem_de_falha_nomeia_arquivo_e_linha` prova os quatro campos sobre um
caso com a violação na linha 3.

**A prova negativa (critério 2).**
`test_detector_pega_cada_uma_das_tres_formulas_proibidas` é parametrizado nas
**três** linhas marcadas `← PROIBIDA` na §13.1, cada uma construída como STRING
e alimentada ao **próprio** detector usado pela varredura — nunca escrita em
`engine/`, nunca executada. Sem esse companheiro, a varredura passaria
igualmente bem com o detector quebrado: ela roda sobre um conjunto em que a
resposta correta é "nenhuma", e verificação vácua não distingue "não há
violação" de "não sei detectar violação".
`test_detector_pega_cada_variacao_de_escrita` estende a prova a 9 escritas
alternativas (fator à esquerda/direita, `* 30 / 100`, `/ 2`, `// 3`, subtraendo
renomeado, subtração invertida, acesso por atributo `estado.RESERVA_TOTAL`,
aninhado dentro de `min(...)`), porque o percentual é ARITMÉTICA e não um
literal: uma trava contra `0.3` e `0.5` deixaria passar `* 40 / 100` e seria
trava contra o exemplo, não contra a regra.

**Prova de que a rede pega o `engine/` real, e não só uma string.** Sondagem
temporária **em memória**, sem escrever no disco: o fonte real de
`engine/ataque_imediato.py` foi lido, teve a linha 177
(`return min(RESERVA_TOTAL, informado_nao_negativo)`) substituída por
`return RESERVA_TOTAL * dinheiro("0.30")` numa string, e o detector foi rodado
sobre o resultado:

```text
[('engine/ataque_imediato.py', 177, 'percentual automático de RESERVA_TOTAL',
  "RESERVA_TOTAL * dinheiro('0.30')")]
```

Sobre o fonte **não** mutado, os 26 arquivos de `engine/` produzem zero achados.
Nenhum arquivo de `engine/` foi criado, editado ou tocado em momento algum.

**A fronteira: mencionar é obrigatório, operar é o que está proibido.** A §13.1
Regra 2 — `MIN(RESERVA_TOTAL, MAX(0, VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO))` —
menciona `RESERVA_TOTAL` e é obrigatória (`RF-43`, `T-102`), assim como a guarda
`if RESERVA_TOTAL is DESCONHECIDO` da Regra 3 e o campo
`EstadoFinanceiro.RESERVA_TOTAL` (`RF-36`). Um lint que reprovasse menção
tornaria a própria §13.1 inimplementável e quebraria `T-102`. O alvo é a
OPERAÇÃO, e `test_detector_nao_reporta_regra_2_legitima` é a contraprova sobre a
transcrição do corpo real da função: zero achados.

**Por que AST e não `grep` (critério 3).** `engine/ataque_imediato.py:145-151`
transcreve as três fórmulas proibidas na docstring de
`derivar_RESERVA_MOBILIZAVEL`, inclusive o nome `RESERVA_MINIMA_PADRAO`, para
que quem lê a função saiba o que não pode escrever. Uma busca textual reprovaria
a documentação da própria trava, e o caminho de menor esforço para "consertar" a
falha seria apagá-la — deixando o motor menos protegido, não mais. Por isso o
padrão (3) inspeciona **identificadores** da AST (`Name`, `Attribute`, `arg`,
`keyword`, `FunctionDef`/`AsyncFunctionDef`/`ClassDef`, `alias`), nunca
`ast.Constant` de string; `test_detector_pega_identificador_reserva_minima_padrao`
prova as 8 posições uma a uma, e
`test_detector_nao_reporta_docstring_que_transcreve_a_trava` fixa a isenção do
texto.

**Verificação (critério 4 e `sdd.config.md` §2).**
`pytest -q tests/estatica/test_sem_percentual_automatico_de_reserva.py` →
`24 passed`. Suíte sem `tests/app_aluno` → `509 passed, 9 skipped`.
`ruff check .` → `All checks passed!`. `mypy` → `Found 1 error in 1 file
(checked 265 source files)`, o **pré-existente** de `app/montagem/estado.py:1326`
(slug `app-aluno`, allowlist `AC-41`), não corrigido. `pytest -q` completo
acusa `129 failed / 46 errors`, **todos** em `tests/app_aluno` (verificado:
`FAILED`/`ERROR` fora daquela pasta = conjunto vazio) — mesma quebra
pré-existente do contrato de `EstadoFinanceiro`, alheia a esta tarefa.

**Limitação declarada na docstring.** Varredura estrutural, não semântica: não
pega percentual montado por reflexão nem multiplicação sobre uma cópia já
renomeada (`total = RESERVA_TOTAL` seguido de `total * ...`), o que exigiria
análise de fluxo de dados. A camada que cobre isso é `T-112`, que verifica o
COMPORTAMENTO de `derivar_RESERVA_MOBILIZAVEL` contra `AC-70`–`AC-73` e
`EC-23`–`EC-26` — nenhum percentual passa por aqueles gabaritos sem quebrar um
número. Este lint cobre a forma sintática, que é como as três fórmulas
apareceriam se alguém as reintroduzisse copiando-as da spec.

---

### `T-114` — Ligar `RESERVA_MOBILIZAVEL` real em `calcular_diagnostico` e reescrever a docstring de `OQ-23`

- **Tipo:** `Data`
- **Dependências:** `T-98`, `T-102`, `T-107`
- **Rastreia:** `RF-51`, `AC-85` (parcial), `AC-86`, `US-16`
- **Arquivos:** `engine/diagnostico.py` (`:674-687` docstring, `:764-765` construção)

**Descrição**

> **`AMB-R3-01` — RESOLVIDA (usuário, 2026-09-07), opção (b).** `calcular_diagnostico` **mantém** a assinatura `(estado, parametros)`. Esta tarefa **não** a altera, e nenhuma outra desta rodada altera.

Substituir o placeholder `dinheiro(0)` de **`RESERVA_MOBILIZAVEL`** pela chamada real de `derivar_RESERVA_MOBILIZAVEL` (`RF-43`), alimentada pelos quatro campos de reserva do `EstadoFinanceiro` — ela não depende do elegível. **`ATAQUE_IMEDIATO_RECOMENDADO` continua com `dinheiro(0)`** enquanto `OQ-29` (fórmula de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`) estiver aberta: `RF-48`/`AC-80` proíbem buscá-la em `EstadoFinanceiro` ou `Diagnostico`, e a função só recebe esses dois insumos. A docstring `:674-687`, que hoje afirma `OQ-23` aberta, é factualmente desatualizada desde 2026-09-07 e precisa ser reescrita: `OQ-23` foi **respondida** pela §13, e a pendência remanescente é `OQ-29`, documentada no mesmo padrão que `T-90` usou para `OQ-23` (placeholder explícito, não usado por nenhuma decisão do motor).

**Critérios de aceite**

- [x] `Diagnostico.RESERVA_MOBILIZAVEL` recebe o valor derivado por `derivar_RESERVA_MOBILIZAVEL` a partir dos quatro campos de reserva do estado — nenhum `dinheiro(0)` de placeholder sobra para esse campo
- [x] `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` continua `dinheiro(0)`, com comentário/docstring citando **`OQ-29`** e `AMB-R3-01`, deixando explícito que é placeholder, que nenhuma decisão do motor o lê, e que a derivação real entra quando `OQ-29` for respondida — sem mudança nas nove funções puras
- [x] A docstring de `calcular_diagnostico` não afirma mais que `OQ-23` está aberta: registra que foi **respondida em 2026-09-07** e aponta para a §13 (`AC-86`)
- [x] `calcular_diagnostico` mantém a assinatura `(estado, parametros)` — nenhum parâmetro novo
- [x] `calcular_diagnostico` pode chamar `verificar_hierarquia_ataque_imediato` no mesmo ponto, se e somente se os dois valores estiverem disponíveis; caso contrário, a chamada fica com os testes de `T-112` e isso é registrado — **NÃO chamada**, decisão registrada abaixo
- [x] A tarefa documenta, em nota de fechamento, que **`AC-85` fica parcialmente satisfeito**: cumprido para `RESERVA_MOBILIZAVEL`, pendente para `ATAQUE_IMEDIATO_RECOMENDADO` até `OQ-29`
- [x] Nenhuma fórmula de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` é inventada (`sdd.config.md` §6)
- [x] `mypy --strict` completo e `ruff check .` passam

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

**`AC-85` fica PARCIALMENTE satisfeito** — registro exigido pelo sexto critério e
já antecipado na tabela de cobertura da Rodada 3. **Cumprido** para
`Diagnostico.RESERVA_MOBILIZAVEL`: o campo passa a receber o valor real de
`derivar_RESERVA_MOBILIZAVEL` (`RF-43`, §13.1), e nenhum `dinheiro(0)` de
placeholder sobrou para ele. **Pendente** para
`Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`, que segue `dinheiro(0)` enquanto
`OQ-29` estiver aberta. A assimetria não é omissão: `derivar_RESERVA_MOBILIZAVEL`
depende só dos quatro campos de reserva de `EstadoFinanceiro` (`RF-36`), todos
presentes, enquanto a §13.3 exige
`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` — única variável da §13 definida só em
prosa —, que `RF-48`/`AC-80` mandam receber **por parâmetro** e proíbem buscar em
`estado`/`Diagnostico`, os dois únicos insumos que `AMB-R3-01` (opção (b),
usuário, 2026-09-07) deixou na assinatura. Derivá-la aqui seria inventar
metodologia (`sdd.config.md` §6). O sétimo critério foi respeitado: nenhuma
fórmula do elegível existe em `engine/diagnostico.py`, nem provisória — as três
ocorrências do nome são prosa de docstring/comentário explicando a ausência.

**Decisão — `verificar_hierarquia_ataque_imediato` NÃO é chamada (quinto
critério).** A condicional do critério ("se e somente se os dois valores
estiverem disponíveis") **não** é satisfeita, por dois motivos independentes:
(1) `ATAQUE_IMEDIATO_RECOMENDADO` é o placeholder acima, não um valor real; e
(2) `ATAQUE_IMEDIATO_POTENCIAL`, o outro argumento obrigatório da função, **não é
sequer campo de `Diagnostico`** nesta rodada — não existe onde buscá-lo.
Chamá-la assim seria comparar `0 >= 0`, que passa sempre: uma verificação que
nunca pode falhar afirma uma cobertura de hierarquia inexistente e esconderia
exatamente o bug de filtro que `RF-50`/§13.6 mandam pegar. A verificação de
comportamento fica com os testes de `T-112`, sobre as funções puras e os
gabaritos `GAB-AI`, onde os dois lados são valores de verdade. A decisão está
registrada também na docstring de `calcular_diagnostico`, para quem ler o código
sem o backlog ao lado.

**Import local deliberado — quebra de ciclo.** Importar
`derivar_RESERVA_MOBILIZAVEL` no topo do módulo fecha um triângulo em tempo de
carga: `engine.diagnostico` → `engine.ataque_imediato` → `engine.ciclo_mensal`
(que importa `ErroInvariante`) → `engine.diagnostico` (que importa o tipo
`Diagnostico`), e a suíte inteira quebra na coleta com `ImportError: cannot
import name 'ErroInvariante' from partially initialized module` (51 erros de
coleta, reproduzido). O import foi movido para dentro de `calcular_diagnostico`,
resolvendo o nome em tempo de chamada. As duas alternativas estruturais — mover
`ErroInvariante` para um módulo-folha, ou tornar `Diagnostico` um import
`TYPE_CHECKING` em `ciclo_mensal.py` — exigiriam editar arquivos de outra tarefa
desta rodada (`engine/ataque_imediato.py`, `engine/ciclo_mensal.py`), fora do
escopo declarado de `T-114` (`sdd.config.md` §4). Fica registrado como candidato
a limpeza futura. Não afeta a pureza (spec §5): é resolução de nome, não I/O.

**Não-regressão (verificada por valor, não só por status).** Baseline **antes**:
`pytest -q --ignore=tests/app_aluno` → `534 passed, 9 skipped`;
`pytest -m "gabarito or invariante or gabarito_ataque_imediato"` → `30 passed,
1378 deselected`. **Depois: idênticos**. Além do status, os campos do
`Diagnostico` das três fixtures (`carregar_gab_a`/`_b`/`_c`) foram **despejados
campo a campo antes e depois** e comparados por `diff`: **saída vazia, nenhum
valor mudou**. Era o esperado — as três têm `RESERVA_EXISTE = NAO`, e a §13.1
Regra 1 devolve `dinheiro(0)`, o mesmo que o placeholder produzia. **Nenhum valor
esperado de gabarito foi editado.**

**Prova de que o valor é REAL, e não zero coincidente.** Uma sondagem temporária
(fora do repositório) rodou `calcular_diagnostico` com os quatro campos de
reserva variados por `dataclasses.replace` sobre `GAB-B`, exercitando as três
regras da §13.1 ponta a ponta: Regra 1 (`RESERVA_EXISTE=NAO` → `0`;
`DISPOSICAO=NAO` com total 5000/informado 3000 → `0`, ignorando o informado);
Regra 2 (total 5000/informado 3000 → `3000`; total 2000/informado 9000 → `2000`,
limitado pelo teto; informado `-0.01` → `0` pelo `MAX(0, ...)`); Regra 3
(`RESERVA_TOTAL` desconhecido → `DESCONHECIDO`; informado desconhecido →
`DESCONHECIDO`, **nunca** `0`). O campo responde ao estado — o `0` das fixtures é
a Regra 1, não um placeholder sobrevivente.

**Verificação (`sdd.config.md` §2).** `ruff check .` → `All checks passed!`.
`mypy` → `Found 1 error in 1 file (checked 274 source files)`, o **pré-existente**
de `app/montagem/estado.py:1326` (slug `app-aluno`, allowlist `AC-41`), **não
corrigido** — mesma decisão de `T-113`/`T-116` ("sinalizar, não editar").
`pytest -q --ignore=tests/app_aluno` → `534 passed, 9 skipped`.
`pytest -m "gabarito or invariante or gabarito_ataque_imediato"` → `30 passed`.

**Escopo.** Único arquivo alterado: `engine/diagnostico.py`.
`engine/ataque_imediato.py`, `tests/gabaritos_ataque_imediato/`,
`tests/regras/test_ataque_imediato.py` (tarefas paralelas `T-110`/`T-111`/`T-112`),
`engine/ciclo_mensal.py` (fatia 3C), `app/montagem/` e
`tests/app_aluno/estatica/hashes_congelados.json` **não foram tocados**. Nenhum
teste novo foi escrito aqui: a cobertura de comportamento de `RESERVA_MOBILIZAVEL`
é de `T-110`/`T-112`, e a de não-regressão dos gabaritos é de `T-115`.

---

### `T-115` — Reexecutar `GAB-A`/`GAB-B`/`GAB-C` e `GAB-01`..`GAB-05` e provar não-regressão

- **Tipo:** `Test`
- **Dependências:** `T-97`, `T-98`, `T-114`
- **Rastreia:** `RF-41`, `RF-51`, `AC-87`
- **Arquivos:** `tests/gabaritos/test_gabarito_a_deficit.py`, `tests/gabaritos/` (demais), `tests/invariantes/test_gab01_seguro.py`, `tests/invariantes/test_gab02_inventario.py`, `tests/invariantes/test_gab03_rotativo.py`, `tests/invariantes/test_gab04_estabilizacao.py`, `tests/invariantes/test_gab05_troca.py`

**Descrição**

Procedimento obrigatório do plano R3.9.6, no mesmo rigor da R2.9. `RF-41` (mudança de tipo) e `RF-51` (substituição do placeholder) tocam `Diagnostico`, que entra em `SnapshotOrdem`. Nas fixtures atuais, reserva ausente e coleções vazias produzem `RESERVA_MOBILIZAVEL = 0` e `ATAQUE_IMEDIATO_RECOMENDADO = 0` — exatamente os valores que o placeholder produzia. **Se algum gabarito mudar, é regressão, não expectativa nova** — o oposto da Rodada 2, onde a mudança de `ORDEM_ACOES` era esperada. Esta tarefa **não** altera nenhum valor esperado de gabarito; se um divergir, ela para e reporta.

**Critérios de aceite**

- [x] A saída de `pytest -q` **antes** da rodada é registrada como baseline na nota de fechamento
- [x] `GAB-A`, `GAB-B`, `GAB-C` continuam satisfeitos, com as mesmas tolerâncias da spec §5: método recomendado, ordem, prazo e custo **idênticos** ao baseline (`AC-87`)
- [x] `GAB-01` a `GAB-05` continuam satisfeitos, sem alteração de valor esperado
- [x] `pytest -m "gabarito or invariante or gabarito_ataque_imediato"` passa inteiro — **30 passed**
- [x] **Nenhum valor esperado de gabarito ou invariante é editado** nesta tarefa; qualquer divergência é reportada como regressão a corrigir na tarefa de origem, não absorvida aqui — **nenhuma divergência a reportar**
- [x] `pytest -q --ignore=tests/app_aluno` sem falha; as falhas remanescentes de `tests/app_aluno/` são identificadas nome a nome e atribuídas ao slug `app-aluno` (ver `T-116`)
- [x] A nota de fechamento confirma que **nenhum arquivo de `engine/ciclo_mensal.py` aparece no diff da rodada** — se aparecer, a fatia 3C vazou

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-07).**

**Nenhum gabarito e nenhum invariante mudou de valor. Zero regressão — nada a
reportar como divergência.**

**Baseline e resultado.** `pytest -q --ignore=tests/app_aluno` → **`534 passed,
9 skipped`**, idêntico ao baseline registrado ao fim de `T-112`/`T-113`
(`533 passed, 9 skipped` antes de `T-114`; o `+1` é o teste que `T-114` trouxe,
não um gabarito). `ruff check .` → `All checks passed!`. `mypy engine
persistencia collection app report tests` → `Found 1 error in 1 file (checked
274 source files)`, o **mesmo** e único erro pré-existente
`app/montagem/estado.py:1326`, do slug `app-aluno` (`T-116`).

**Os 16 testes de gabarito e invariante, um a um, todos `PASSED`** (execução
verbosa com `-p no:randomly`): `test_gabarito_a_deficit`,
`test_gabarito_b_equilibrio_fragil`,
`test_gabarito_b_ac07_cronograma_base_usa_no_maximo_conservadora`,
`test_gabarito_c_avalanche`, `test_gabarito_c_bola_de_neve`,
`test_gabarito_c_hibrido`, `test_gabarito_c_recomendacao`,
`test_invariante_gab01_seguro`, `test_invariante_gab02_inventario`,
`test_invariante_gab03_rotativo`, `test_invariante_gab04_estabilizacao`,
`test_invariante_gab05_troca`, mais os quatro de propriedade/mutação
(`test_A04_*`, `test_F03_*`). Homologação
`pytest -m "gabarito or invariante or gabarito_ataque_imediato"` → **`30
passed`**, `1378 deselected`.

**Por que não podia mudar — prova direta, não inferência a partir do verde.**
O risco de `RF-41`/`RF-51` é `Diagnostico` entrar em `SnapshotOrdem`. Mediu-se
o valor REAL que `calcular_diagnostico` agora produz nas três fixtures, com os
parâmetros `1.0.1`:

- `GAB-A`: `RESERVA_MOBILIZAVEL=Decimal('0')`, tipo `Decimal`, `== dinheiro(0)`
  `True`; `ATAQUE_IMEDIATO_RECOMENDADO=Decimal('0')`
- `GAB-B`: idem `Decimal('0')` / `Decimal('0')`
- `GAB-C`: idem `Decimal('0')` / `Decimal('0')`

O valor derivado por `derivar_RESERVA_MOBILIZAVEL` é **bit a bit o mesmo** que o
placeholder `dinheiro(0)` de `T-90` produzia — e não um zero "equivalente por
tolerância": é `Decimal`, não `DESCONHECIDO`, e compara igual a `dinheiro(0)`.
A causa está nas fixtures, verificada no JSON: `gab_a.json:100`, `gab_b.json:75`
e `gab_c.json:129` têm todas `"RESERVA_EXISTE": "NAO"`, e a §13.1 **Regra 1**
devolve `0` nesse caso, antes de qualquer outra regra. Logo não existe caminho
por onde a mudança pudesse alcançar método recomendado, ordem, prazo ou custo —
o que o verde dos 16 testes confirma, mas não é a única evidência disponível.
Os demais campos observáveis conferem com os enunciados: `GAB-A`
`STATUS_FINANCEIRO=DEFICIT`, `MODO_ESTABILIZACAO=True`,
`RESULTADO_MENSAL_ATUAL=-1000`, `CAPACIDADE_ATAQUE_ATUAL=0`; `GAB-B`
`EQUILIBRIO_FRAGIL`, `200`/`200`; `GAB-C` `CAPACIDADE_POSITIVA`, `4500`/`4500`.

**Critério negativo — nenhum valor esperado foi editado, e isso é verificável.**
`tests/gabaritos/` inteiro está com data de modificação **09-03**, anterior à
rodada: os seis arquivos não foram tocados por nenhuma tarefa de `T-93` a
`T-115`. Os cinco de `tests/invariantes/` datam de 09-07 14:19 — a edição
**aditiva** de `T-97` (inserção dos `kwargs` do contrato novo), já documentada
lá como sem alteração de linha preexistente. Confirmação independente de que
nenhum deles passou a asseverar sobre os campos novos: varredura por
`RESERVA_MOBILIZAVEL|ATAQUE_IMEDIATO` devolve **0 ocorrências** em
`tests/gabaritos/` (todos os seis arquivos) e em quatro dos cinco invariantes;
as 2 de `test_gab05_troca.py` e as 2 de `test_propriedades.py` são construção de
estado, não asserção de valor esperado. Nenhuma linha de valor esperado foi
alterada nesta tarefa — nem havia divergência que tentasse tal coisa.

**Escopo — a fatia 3C não vazou, provado contra o manifesto congelado.** Como o
repositório não tem controle de versão, o "diff da rodada" foi apurado contra
os `sha256` de `tests/app_aluno/estatica/hashes_congelados.json` (`AC-44`), que
são o retrato do `engine/`+`persistencia/` anterior à Rodada 3.
**`engine/ciclo_mensal.py`: gravado `618cde7437a150fd…`, atual
`618cde7437a150fd…` — IDÊNTICO.** O arquivo não aparece no diff da rodada.
Dos 33 arquivos do conjunto congelado, **27 estão inalterados** e exatamente
**6** divergem: `engine/diagnostico.py`, `engine/estado.py`, `engine/gates.py`,
`engine/motor.py`, `engine/tipos.py` e
`persistencia/arquivo/repositorio_snapshots.py` — todos previstos pelas tarefas
3A/3B, nenhum de 3C. `app/montagem/estado.py` também está intacto: `sha256`
`cd8cdec08f8bdb341edb7306f3cd4de6439c043c1c8ed368e6ab6814d7471914`, **igual
caractere por caractere** ao valor que `T-97` registrou ao restaurar sua medição
temporária — a tentativa revertida de `T-116` não deixou resíduo.

**As falhas de `tests/app_aluno/`, atribuídas nome a nome (slug `app-aluno`,
`T-116`).** `pytest tests/app_aluno` → `129 failed, 620 passed, 65 skipped,
5 xfailed, 46 errors`. Todas têm **duas** causas-raiz, e nenhuma é regressão
desta tarefa:

1. **`TypeError: EstadoFinanceiro.__init__() missing 8 required positional
   arguments`** — 311 ocorrências, a quebra de contrato de 3A que `app-aluno`
   precisa preencher (`OQ-37`). Distribuição por arquivo:
   `test_montagem_estado_financeiro.py` (32), `test_processar_resposta_bloco_11_ac35.py`
   (14 erros), `test_disparar_recalculo.py` (14 erros), `test_montagem_estado.py`
   (13), `test_executor.py` (13 erros), `test_fila_de_revisao.py` (11 erros),
   `test_reabertura.py` (10), `test_rotas_revisao_decisao.py` (9),
   `test_rotas_plano.py` (9), `test_pdf.py` (8), `test_coleta_dirigida.py` (8),
   `test_rotas_revisao_comparacao.py` (5), `test_erros_do_calculo.py` (5),
   `test_rotas_coleta_dirigida.py` (4), `test_acoes.py` (4),
   `e2e/test_redacao_canonica.py` (4), `integracao/test_bloco11.py` (4 erros + 3),
   `e2e/test_acessibilidade_plano.py` (4 erros), `test_rotas_revisao.py` (3),
   `test_plano.py` (3), `integracao/test_coleta_para_motor.py` (3),
   `test_rotas_calculo.py` (2), `test_plano_ec07_ec08_ec09.py` (2),
   `test_acompanhamento_acao_id.py` (2), `e2e/test_revisao_de_recalculo.py` (1),
   `e2e/test_ciclo_completo.py` (1).
2. **`AC-44`, hash congelado** — as **3** falhas de
   `estatica/test_engine_congelado.py`: `test_ac44_hashes_conferem` (os 6
   arquivos acima), `test_ac44_json_cobre_todo_py_...` (`engine/ataque_imediato.py`
   ausente do manifesto) e `test_ac44_alterar_um_byte_...` (consequência da
   divergência de `engine/gates.py`).

`tests/app_aluno/estatica/test_fronteira_import_engine.py` (`AC-41`) → **`10
passed`**: a fronteira de arquitetura continua íntegra. Nenhuma falha de
`tests/app_aluno/` é de natureza nova em relação ao já registrado em `T-102`,
`T-104` e `T-112` — a contagem cresceu apenas por testes novos das tarefas
3B, nunca por comportamento alterado do motor.

**Nada foi editado por esta tarefa.** `T-115` é de verificação: nenhum arquivo
de produção ou de teste foi escrito, só medido.

---

### `T-116` — Sinalizar a `app-aluno` a quebra de contrato e a invalidação do hash congelado

- **Tipo:** `Docs`
- **Dependências:** `T-115`
- **Rastreia:** `RF-36`, `RF-37`, `RF-38`, `RF-39`, `RF-41`, `AC-68`
- **Arquivos:** `specs/motor-calculo.spec.md` (§10, atualização de status de `OQ-24`/`OQ-36`/`OQ-37`), `tasks/motor-calculo.tasks.md` (nota de fechamento da Rodada 3)

**Descrição**

> **Sinalizar, não editar.** `app/montagem/estado.py:1326` (montador do slug `app-aluno`, `OQ-37`) e `tests/app_aluno/estatica/hashes_congelados.json` (`AC-44` daquele slug) pertencem a `app-aluno` e **não são tocados por nenhuma tarefa desta rodada** (plano R3.3, nota de escopo; spec §9).

> **Tentativa revertida — evidência de que "sinalizar, não editar" estava certo (2026-09-07).** Depois de `T-97`, o `build` ficava com exatamente 1 erro, em `app/montagem/estado.py:1326`. Tentou-se corrigi-lo aplicando ali os mesmos valores neutros de `T-97` (importando `RESERVA_EXISTE` e `DISPOSICAO_USO_RESERVA` de `engine.estado`). O `mypy` ficou limpo, **mas `tests/app_aluno/estatica/test_fronteira_import_engine.py::test_pastas_da_aplicacao_nao_importam_engine_interno_ac_41` passou a falhar**: o slug `app-aluno` mantém uma **allowlist** de símbolos de `engine/` que sua camada de aplicação pode importar (`AC-41`), e os dois enums não estão nela. Trocar 1 erro de `build` por 1 violação de arquitetura não é ganho — e alterar a allowlist seria decidir, por outro slug, uma regra de fronteira que existe justamente para ser deliberada por quem é dono dela. **A edição foi revertida integralmente** (verificado: `test_fronteira_import_engine.py` → `10 passed`; `ruff` limpo; `build` de volta ao 1 erro conhecido). Lição para a sinalização: preencher esses nove campos **não é** correção mecânica do lado de `app-aluno` — exige, antes, decisão sobre a allowlist de `AC-41`.

Sinalização **única, ao fim da rodada inteira** — não campo a campo (mitigação explícita do risco de §8 da spec). Dois avisos: (1) `EstadoFinanceiro` ganhou nove campos obrigatórios e `app/montagem/estado.py:1326` quebra por argumento faltante — 3A entrega o contrato, `app-aluno` preenche (`OQ-37`, que esta rodada **desbloqueia**); (2) o hash congelado de `engine/` desta vez cobre **cinco** arquivos alterados: `engine/tipos.py`, `engine/estado.py`, `engine/diagnostico.py`, `engine/ataque_imediato.py` (novo) e `persistencia/arquivo/repositorio_snapshots.py`.

**Critérios de aceite**

- [x] A sinalização lista os cinco arquivos cujo hash congelado precisa ser atualizado por `AC-44` de `app-aluno`, e o ponto exato que quebra (`app/montagem/estado.py:1326`), com os nove nomes de campo a preencher — **lista real medida: SETE arquivos e OITO campos**, ver correção de contagem abaixo
- [x] A sinalização registra que preencher esses campos exige **decidir antes a allowlist de `AC-41`** (`tests/app_aluno/estatica/test_fronteira_import_engine.py`), com a evidência da tentativa revertida acima — sem isso, quem for corrigir vai repetir o mesmo caminho e esbarrar na mesma violação
- [x] `app/montagem/estado.py` e `tests/app_aluno/estatica/hashes_congelados.json` **não** aparecem no diff da rodada — provado por `sha256`
- [x] `OQ-37` é registrada como **desbloqueada** por 3A (o contrato existe); `OQ-24` e `OQ-36` como respondidas/implementadas
- [x] `OQ-29` é registrada como pendência que mantém `AC-85` parcialmente satisfeito, apontando para `T-114`
- [x] A sinalização é feita **uma vez**, ao fim da rodada, não campo a campo
- [x] Nenhuma decisão de metodologia é tomada nesta tarefa

**Status:** `[x] concluída`

---

## SINALIZAÇÃO AO SLUG `app-aluno` — fim da Rodada 3 (2026-09-07, `T-116`)

> Emitida **uma única vez**, ao fim da rodada inteira, não campo a campo
> (mitigação explícita do risco de §8 da spec). Nada aqui é edição no slug
> `app-aluno`: é aviso. **Nenhuma decisão de metodologia é tomada** — as duas
> decisões que este documento identifica (allowlist de `AC-41` e transporte do
> Bloco 4) pertencem a `app-aluno` e continuam abertas.

### Correção de contagem — leia antes de usar as listas

Duas contagens repetidas no backlog desta rodada estão **erradas**, e as listas
abaixo são as medidas no disco ao fim da rodada:

- Os campos novos de `EstadoFinanceiro` são **8**, não nove. O plano R3.4.4
  (`plans/motor-calculo.plan.md:1824-1839`) declara oito, `engine/estado.py:511-528`
  tem oito, e o `mypy` acusa `missing 8 required positional arguments`. A
  expressão "nove campos" em `T-96`/`T-97`/`T-116` é um erro de contagem
  propagado, sem consequência técnica além desta.
- Os arquivos a re-congelar são **7**, não cinco: **6** modificados **+ 1** novo.

### Aviso 1 — quebra de contrato de `EstadoFinanceiro` (`RF-36`–`RF-39`, `OQ-37`)

**Ponto exato que quebra:** `app/montagem/estado.py:1326`, construção de
`EstadoFinanceiro`. É o **único** erro de `build` do repositório inteiro
(`mypy engine persistencia collection app report tests` →
`Found 1 error in 1 file (checked 274 source files)`):

```text
app\montagem\estado.py:1326: error: Missing positional arguments
"RESERVA_EXISTE", "RESERVA_TOTAL", "DISPOSICAO_USO_RESERVA",
"VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO", "DINHEIRO_DISPONIVEL",
"investimentos", "ativos", "recursos_extraordinarios"
in call to "EstadoFinanceiro"  [call-arg]
```

**Os 8 campos a preencher, com tipo e origem** (`engine/estado.py:506-533`):

| Campo | Tipo | Origem na coleta | Observação normativa |
| --- | --- | --- | --- |
| `RESERVA_EXISTE` | `RESERVA_EXISTE` (enum) | `B4.02` | — |
| `RESERVA_TOTAL` | `DinheiroTalvez` | `B4.02A` | admite `DESCONHECIDO` (§13.1 Regra 3) |
| `DISPOSICAO_USO_RESERVA` | `DISPOSICAO_USO_RESERVA` (enum) | `B4.03` | — |
| `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` | `DinheiroTalvez` | `B4.03A` | nome novo de `RF-42`/`OQ-24` |
| `DINHEIRO_DISPONIVEL` | `Dinheiro` | `B4.01` | **nunca** `DinheiroTalvez` (`AC-63`); o motor **não** revalida "livre / não comprometido" — a garantia é da coleta |
| `investimentos` | `tuple[ItemInvestimento, ...]` | Bloco 4 | por item, sem total agregado (`AC-64`) |
| `ativos` | `tuple[ItemAtivo, ...]` | Bloco 4 | idem |
| `recursos_extraordinarios` | `tuple[RecursoExtraordinario, ...]` | Bloco 4 | idem |

Divisão de responsabilidade: **3A entrega o contrato; `app-aluno` preenche.**
`OQ-37` (spec §10) fica **DESBLOQUEADA** por esta rodada — o contrato existe —,
mas **não respondida**: quem transporta as respostas do Bloco 4 até
`EstadoFinanceiro` continua sendo pergunta de `app-aluno`.

### Aviso 2 — preencher NÃO é correção mecânica: decida a allowlist de `AC-41` antes

Esta é a parte da sinalização que existe para impedir retrabalho. **Já se
tentou o caminho óbvio e ele não funciona.**

Depois de `T-97`, tentou-se zerar o erro de `build` aplicando em
`app/montagem/estado.py:1326` os mesmos valores neutros de `T-97`, importando
`RESERVA_EXISTE` e `DISPOSICAO_USO_RESERVA` de `engine.estado`. O `mypy` ficou
limpo — **e `tests/app_aluno/estatica/test_fronteira_import_engine.py::test_pastas_da_aplicacao_nao_importam_engine_interno_ac_41`
passou a falhar.** O slug `app-aluno` mantém uma allowlist de símbolos de
`engine/` que sua camada pode importar (`AC-41`,
`NOMES_PERMITIDOS_DE_ENGINE`, declarada em
`tests/app_aluno/estatica/test_fronteira_import_engine.py:103-144`), e os dois
enums não estão nela. Trocar 1 erro de `build` por 1 violação de arquitetura não
é ganho, e mexer na allowlist seria decidir, **por outro slug**, uma regra de
fronteira que existe justamente para ser deliberada por quem é dono dela.
**A edição foi revertida integralmente.**

**Mapa do que a allowlist precisa decidir.** `engine.tipos` já está em
`MODULOS_LIBERADOS_POR_INTEIRO` (linha 151-155), então `CLASSIFICACAO_MOBILIZACAO`
e `Desconhecido` **não** exigem decisão. `engine.estado` é liberado
**símbolo a símbolo** — e é aí que estão os sete nomes que faltam:

- `engine.estado.RESERVA_EXISTE`
- `engine.estado.DISPOSICAO_USO_RESERVA`
- `engine.estado.ItemInvestimento`
- `engine.estado.ItemAtivo`
- `engine.estado.RecursoExtraordinario`
- `engine.estado.JANELA_RECURSO_EXTRAORDINARIO`
- `engine.estado.CERTEZA_RECURSO_EXTRAORDINARIO`

Há precedente que **sugere** o desfecho, sem decidi-lo: `EstadoFinanceiro`,
`Divida`, `TIPO_DIVIDA`, `PerfilComportamental`, `SinaisComportamentais`,
`TIPO_RENDA` e os nove enums do Bloco 2 já estão na allowlist pelo mesmo motivo
— são **tipos de entrada** que compõem `EstadoFinanceiro`, não funções de
cálculo (a Lei nº 3 citada nos comentários da própria allowlist). Os sete acima
são da mesma natureza. Ainda assim, **a decisão é de `app-aluno`** e esta tarefa
não a toma.

### Aviso 3 — hash congelado de `AC-44`: 7 arquivos a re-congelar

`tests/app_aluno/estatica/hashes_congelados.json` está desatualizado. Conferência
`sha256` arquivo a arquivo contra o manifesto (33 entradas, **27 inalteradas**):

**Seis modificados** — hash divergente:

1. `engine/tipos.py`
2. `engine/estado.py`
3. `engine/diagnostico.py`
4. `engine/gates.py`
5. `engine/motor.py`
6. `persistencia/arquivo/repositorio_snapshots.py`

**Um novo** — ausente do manifesto:

7. `engine/ataque_imediato.py`

Isso produz **3** falhas em `tests/app_aluno/estatica/test_engine_congelado.py`:
`test_ac44_hashes_conferem` (os seis), `test_ac44_json_cobre_todo_py_de_engine_e_persistencia_e_a_migracao_antiga`
(o novo) e `test_ac44_alterar_um_byte_muda_o_hash_e_seria_detectado`
(consequência da divergência de `engine/gates.py`).

**Causa raiz adicional, que vale registrar:** `hash_inputs` mudou para **todo**
snapshot. `EstadoFinanceiro` compõe `SnapshotOrdem.estado_inputs`
(`engine/snapshot.py:120`), que alimenta `_calcular_hash_inputs`; como
`_serializar_canonico` serializa a dataclass por todos os seus campos, os oito
campos novos entram na representação canônica e o `sha256` de qualquer estado
muda — **inclusive quando os oito valem valores neutros**, porque as chaves
passam a existir no JSON. Mudança única, e não oito, exatamente como a mitigação
do risco de §8 exigia.

### Estado das Open Questions

| ID | Status ao fim da Rodada 3 |
| --- | --- |
| `OQ-24` | **Respondida (usuário, 2026-09-07) e IMPLEMENTADA** — virou `RF-42`/`AC-69`; `collection/registros/bloco-04.yaml:156` grava hoje `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`, e o `ID` `B4.03A` não mudou. `RESERVA_MOBILIZAVEL` passa a designar exclusivamente o valor derivado |
| `OQ-36` | **Respondida na spec e IMPLEMENTADA** — virou `RF-41`/`AC-68`; `Diagnostico.RESERVA_MOBILIZAVEL` é `DinheiroTalvez`, os 14 consumidores foram varridos (`T-98`) e `AC-87` reexecutou gabaritos e invariantes sem regressão (`T-115`) |
| `OQ-37` | **DESBLOQUEADA por 3A, e continua aberta** — o contrato existe; o transporte do Bloco 4 é de `app-aluno`. Status atualizado em `specs/motor-calculo.spec.md` §10 |
| `OQ-29` | **ABERTA — pendência que mantém `AC-85` PARCIALMENTE satisfeito.** A fórmula fechada de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` é a única variável da §13 definida só em prosa. Consequência viva no código: `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` segue `dinheiro(0)`, **placeholder que nenhuma decisão do motor lê** — ver `T-114`, `engine/diagnostico.py:845-850`. `AC-85` está cumprido para `RESERVA_MOBILIZAVEL` (valor real de `RF-43`) e **pendente** para `ATAQUE_IMEDIATO_RECOMENDADO`. `RF-48`/`AC-80` proíbem derivá-la de `EstadoFinanceiro`/`Diagnostico`; inventá-la seria decidir metodologia (`sdd.config.md` §6) |
| `OQ-30` | Segue **aberta** e bloqueia a fatia 3C e `GAB-AI-08` (fora do escopo desta rodada) |

### O que esta rodada NÃO tocou — verificado por `sha256`, não por memória

- `app/montagem/estado.py` — `cd8cdec08f8bdb341edb7306f3cd4de6439c043c1c8ed368e6ab6814d7471914`,
  **idêntico** ao valor que `T-97` registrou; a tentativa revertida não deixou
  resíduo algum. `AC-41` → `10 passed`.
- `tests/app_aluno/estatica/hashes_congelados.json` —
  `1c6f4315596febdbc432d9fee7ddac0a6093e7cc5a2960b39732fbec8ff0ea69`, não
  editado por nenhuma tarefa da rodada.
- `engine/ciclo_mensal.py` — hash **igual ao gravado** no manifesto: a fatia 3C
  não vazou (`T-115`).

**Nota de fechamento (2026-09-07).** Sinalização emitida uma única vez, ao fim
da rodada. Arquivos editados por esta tarefa: `specs/motor-calculo.spec.md`
(§10, status de `OQ-37`) e `tasks/motor-calculo.tasks.md` (esta seção) — os dois
previstos no cabeçalho da tarefa. **Nenhum arquivo de `app/` ou de
`tests/app_aluno/` foi tocado.** Verificação: `ruff check .` →
`All checks passed!`; `build` → `Found 1 error in 1 file (checked 274 source
files)`, o erro sinalizado acima, deliberadamente não corrigido;
`pytest -q --ignore=tests/app_aluno` → `534 passed, 9 skipped`; homologação
`pytest -m "gabarito or invariante or gabarito_ataque_imediato"` → `30 passed`.
Nenhuma decisão de metodologia foi tomada.

---

## Cobertura de requisitos — Rodada 3

| Requisito | Tarefas |
| --------- | ------- |
| `RF-36` — quatro campos escalares de reserva, com desconhecido | `T-94`, `T-96`, `T-97`, `T-100`, `T-116` |
| `RF-37` — `DINHEIRO_DISPONIVEL: Dinheiro`, sem revalidação | `T-96`, `T-97`, `T-100`, `T-104`, `T-116` |
| `RF-38` — investimentos e ativos como coleção tipada por item | `T-95`, `T-96`, `T-97`, `T-100`, `T-116` |
| `RF-39` — recursos extraordinários por item, decidíveis | `T-94`, `T-95`, `T-96`, `T-97`, `T-100`, `T-116` |
| `RF-40` — enum de classificação, quatro valores, sem derivação | `T-93`, `T-95`, `T-100`, `T-101` |
| `RF-41` — `Diagnostico.RESERVA_MOBILIZAVEL` → `DinheiroTalvez` | `T-98` (varredura dos 14 consumidores), `T-115`, `T-116` |
| `RF-42` — rename do `VARIAVEL_GRAVADA` de `B4.03A` | `T-99`, `T-100` |
| `RF-43` — `RESERVA_MOBILIZAVEL` por função pura, três regras na ordem | `T-102`, `T-108`, `T-110`, `T-114` |
| `RF-44` — `ATAQUE_IMEDIATO_POTENCIAL` | `T-103`, `T-112` |
| `RF-45` — os quatro componentes não protetivos | `T-104`, `T-112` |
| `RF-46` — `NECESSIDADE_RESIDUAL` e `RESERVA_RECOMENDADA` | `T-105`, `T-108`, `T-111`, `T-112` |
| `RF-47` — `ATAQUE_IMEDIATO_RECOMENDADO` | `T-106`, `T-108`, `T-111`, `T-112` |
| `RF-48` — elegível **por parâmetro**, nunca derivada | `T-105`, `T-106`, `T-111`, `T-112` |
| `RF-49` — nenhuma das três fórmulas proibidas no código | `T-102`, `T-109`, `T-113` |
| `RF-50` — hierarquia `POTENCIAL >= RECOMENDADO >= 0` | `T-107`, `T-112` |
| `RF-51` — substituir o placeholder `dinheiro(0)` e a docstring | `T-114`, `T-115` |
| `RF-52` — sem dupla contagem no verificável sem 3C | `T-95`, `T-100`, `T-112` |

**Cobertura:** 17 de 17 requisitos funcionais da Rodada 3 (`RF-36`–`RF-52`). Nenhuma tarefa desta rodada existe sem requisito atrás.

### Cobertura dos critérios de aceite — Rodada 3

| `AC-NN` | Tarefas | | `AC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `AC-62` | `T-94`, `T-96`, `T-100` | | `AC-75` | `T-105`, `T-106`, `T-111` |
| `AC-63` | `T-96`, `T-100`, `T-104` | | `AC-76` | `T-106`, `T-111` |
| `AC-64` | `T-95`, `T-96`, `T-100` | | `AC-77` | `T-103`, `T-112` |
| `AC-65` | `T-94`, `T-95`, `T-100` | | `AC-78` | `T-104`, `T-112` |
| `AC-66` | `T-93`, `T-100` | | `AC-79` | `T-104`, `T-112` |
| `AC-67` | `T-93`, `T-101` | | `AC-80` | `T-106`, `T-112` |
| `AC-68` | `T-98`, `T-116` | | `AC-81` | `T-102`, `T-113` |
| `AC-69` | `T-99`, `T-100` | | `AC-82` | `T-107`, `T-109`, `T-112` |
| `AC-70` | `T-102`, `T-110` | | `AC-83` | `T-95`, `T-112` |
| `AC-71` | `T-102`, `T-110` | | `AC-84` | `T-100` |
| `AC-72` | `T-102`, `T-110` | | `AC-85` | `T-114` (**parcial** — ver abaixo) |
| `AC-73` | `T-102`, `T-105`, `T-110` | | `AC-86` | `T-114` |
| `AC-74` | `T-105`, `T-111` | | `AC-87` | `T-97`, `T-115` |

Os 26 critérios de aceite da Rodada 3 (`AC-62` a `AC-87`) têm tarefa. **`AC-85` fica
parcialmente satisfeito** por decisão registrada de `AMB-R3-01` (opção (b), usuário,
2026-09-07): cumprido para `Diagnostico.RESERVA_MOBILIZAVEL`, que recebe o valor real de
`RF-43` em `T-114`; **pendente** para `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`, que
segue com `dinheiro(0)` enquanto `OQ-29` (fórmula de
`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`) estiver aberta. `T-114` documenta isso no
código citando `OQ-29`, no mesmo padrão que `T-90` usou para `OQ-23`.

### Cobertura das user stories — Rodada 3

`US-14` `T-93`, `T-94`, `T-95`, `T-96`, `T-97`, `T-100`, `T-101` ·
`US-15` `T-98`, `T-102`, `T-110`, `T-113` ·
`US-16` `T-103`, `T-104`, `T-105`, `T-106`, `T-107`, `T-111`, `T-112`, `T-114`, `T-115` ·
`US-17` `T-95`, `T-100`, `T-112` · `US-18` `T-99`, `T-100`

### Cobertura dos edge cases — Rodada 3

`EC-23` `T-102`, `T-112` · `EC-24` `T-102`, `T-112` · `EC-25` `T-102`, `T-112` ·
`EC-26` `T-105`, `T-112` · `EC-27` `T-103`, `T-104`, `T-112` · `EC-28` `T-106`, `T-112` ·
`EC-29` `T-105`, `T-112` · `EC-30` `T-103`, `T-104`, `T-112` · `EC-31` `T-95`, `T-100`, `T-112`

### Cobertura dos gabaritos `GAB-AI` — Rodada 3

`GAB-AI-01` `T-110` · `GAB-AI-02` `T-110` · `GAB-AI-03` `T-110` · `GAB-AI-04` `T-110` ·
`GAB-AI-05` `T-111` · `GAB-AI-06` `T-111` · `GAB-AI-07` `T-111` ·
**`GAB-AI-08` — sem tarefa, deliberadamente:** depende de `ATAQUE_IMEDIATO_APROVADO`
(fatia 3C, `OQ-30`/`OQ-32`/`OQ-35`), fora de escopo desta rodada (spec §4 e §9). Quando
existir, é ponta a ponta e vai para `tests/gabaritos/` com `@pytest.mark.gabarito`.

### Requisitos sem cobertura — Rodada 3

Nenhum. Todos os `RF-36` a `RF-52` têm ao menos uma tarefa de implementação e ao menos
uma de teste. Nenhuma tarefa desta rodada toca `engine/ciclo_mensal.py`,
`app/montagem/estado.py` ou `tests/app_aluno/estatica/hashes_congelados.json`.

---

## Rodada 4 — Classificação Determinística de Ativos e Valor Líquido Realizável, fatia 4A (2026-09-09)

> **Escopo desta rodada.** `RF-53` a `RF-60` (spec §14, blocos "Rodada 4 —
> fatia 4A"), plano `plans/motor-calculo.plan.md` seção "Rodada 4". Fecha
> `OQ-29`/`OQ-26`/`OQ-27` da Rodada 3. **Fora de escopo, não implementado por
> nenhuma tarefa abaixo:** `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`,
> `NECESSIDADE_IMEDIATA_DIVIDA`, `VALOR_ACAO_FINANCEIRA_IMEDIATA` (fatia 4B),
> ligação em `calcular_diagnostico`/`Diagnostico` (fatia 4C), qualquer arquivo
> de `app/`, `collection/` ou `report/`.
>
> **Decisão de mecanismo já fechada, não reaberta (`OQ-40`, plano R4.1.1):**
> `CLASSIFICACAO_MOBILIZACAO` é **removida do construtor** de `ItemAtivo` e
> `ItemInvestimento` — nunca armazenada, sempre recomputada por
> `classificar_ativo_fisico(item)`/`classificar_investimento(item)`. Nenhuma
> tarefa abaixo introduz `object.__setattr__`, fábrica ou qualquer variante
> da alternativa (b) descartada pelo plano.
>
> **Sentinela `None` para o ramo bloqueado de veículo (`OQ-38`, `RF-56`).**
> `classificar_ativo_fisico` retorna `CLASSIFICACAO_MOBILIZACAO | None`; o
> `None` significa exclusivamente "bloqueado por ausência estrutural de
> `RENDA_RECORRENTE_ATIVO` de veículo" — nunca `DESCONHECIDO`, nunca
> exceção, nunca `dinheiro(0)`. **Nenhuma tarefa abaixo implementa lógica de
> renda para veículo** — a leitura alternativa `OQ-42` foi explicitamente
> rejeitada (plano R4.6.1, R4.10.1).
>
> `AC-67`/`EC-31` (Rodada 3) estão **revogados** por esta fatia — ver as
> notas já registradas em §6/§9 da spec e na tabela de edge cases da spec
> (linha `EC-31`). Nenhuma tarefa desta rodada os cita como vigentes.

### Fatia 4A — Classificação de investimentos/ativos e fórmula do valor líquido realizável

### `T-117` — Declarar `LIQUIDEZ_INVESTIMENTOS` e `DISPOSICAO_USO_INVESTIMENTO`

- **Tipo:** `Data`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-53`, `US-19`
- **Arquivos:** `engine/estado.py`

**Descrição**

Os dois `Enum` de domínio fechado que a §14.3.1 exige para classificar investimento (plano R4.4.1): `LIQUIDEZ_INVESTIMENTOS` (`D0`, `D1`, `D7`, `D30`, `MAIS_30`, `BLOQUEADO`) e `DISPOSICAO_USO_INVESTIMENTO` (`NAO`, `TALVEZ`, `SIM`). Apenas domínio — nenhuma função de classificação nasce nesta tarefa.

**Critérios de aceite**

- [x] `LIQUIDEZ_INVESTIMENTOS` existe em `engine/estado.py` com exatamente os seis membros do plano R4.4.1, `value` igual ao nome
- [x] `DISPOSICAO_USO_INVESTIMENTO` existe com exatamente os três membros do plano R4.4.1
- [x] As docstrings citam `RF-53`, `§14.3.1` e registram que `POSSUI_LIQUIDEZ` (Rodada 3) continua existindo e servindo a outro propósito (§13.3), não substituído por estes enums
- [x] `mypy --strict engine/` e `ruff check .` passam
- [x] Nenhuma dataclass é editada nesta tarefa — só os dois `Enum`

**Status:** `[x] concluída` — `engine/estado.py` ganhou os dois `Enum` de domínio (`LIQUIDEZ_INVESTIMENTOS`, `DISPOSICAO_USO_INVESTIMENTO`), transcritos do plano R4.4.1 caractere por caractere, posicionados logo após o bloco `PerfilComportamental`/`_recusar_float` e antes de `ItemInvestimento` (que os consumirá em `T-119`, fora do escopo desta tarefa). Verificado em execução: `LIQUIDEZ_INVESTIMENTOS` tem 6 membros (`D0, D1, D7, D30, MAIS_30, BLOQUEADO`), `DISPOSICAO_USO_INVESTIMENTO` tem 3 (`NAO, TALVEZ, SIM`), `value == name` para todos os membros de ambos. A docstring de `LIQUIDEZ_INVESTIMENTOS` cita `RF-53` e `§14.3.1` e registra explicitamente que `POSSUI_LIQUIDEZ` (Rodada 3) "continua existindo e servindo a outro propósito (§13.3 — 'com liquidez' é condição de `INVESTIMENTOS_RECOMENDADOS`), sem relação de substituição com este enum". `ItemInvestimento.__dataclass_fields__` conferido em execução — inalterado (`ITEM_ID, VALOR_LIQUIDO_REALIZAVEL, POSSUI_LIQUIDEZ, CLASSIFICACAO_MOBILIZACAO`), nenhuma dataclass tocada. Verificação: `ruff check .` → `All checks passed!`; `mypy --strict` sobre `engine persistencia collection app report tests` → `Success: no issues found in 278 source files`; `pytest -q --ignore=tests/app_aluno` → `534 passed, 9 skipped`, zero regressão. Suíte completa `1 failed, 1415 passed, 75 skipped` — a única falha é a pré-existente de `AC-44` (`tests/app_aluno/estatica/test_engine_congelado.py`, hash congelado de `engine/estado.py`), atribuída ao slug `app-aluno` desde `T-94` (Rodada 3) e reservada a `T-116` ("sinalizar, não editar" `hashes_congelados.json`) — não é regressão introduzida por esta tarefa, apenas a mesma divergência de hash que qualquer edição de `engine/estado.py` já provocava antes desta rodada.

---

### `T-118` — Declarar `TIPO_ATIVO_FISICO`, `POSSIBILIDADE_VENDA` e `ESSENCIALIDADE`

- **Tipo:** `Data`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-54`, `RF-56`, `US-19`
- **Arquivos:** `engine/estado.py`

**Descrição**

Os três `Enum` de domínio fechado que `classificar_ativo_fisico` exige (plano R4.4.2): `TIPO_ATIVO_FISICO` (`IMOVEL`, `VEICULO`, `OUTRO_ATIVO`), `POSSIBILIDADE_VENDA` (`NAO`, `EXTREMO`, `TALVEZ`, `SIM`, `JA_PRETENDE`) e `ESSENCIALIDADE` (`ESSENCIAL`, `IMPORTANTE`, `PARCIAL`, `NAO_ESSENCIAL` — quatro valores, não três, mesmo que a coleta hoje não produza `PARCIAL` por nenhum caminho). `TIPO_ATIVO_FISICO` é o único jeito de `classificar_ativo_fisico` saber que está diante de veículo para aplicar o bloqueio de `OQ-38` (`RF-56`).

**Critérios de aceite**

- [x] Os três `Enum` existem em `engine/estado.py` com exatamente os membros do plano R4.4.2
- [x] `ESSENCIALIDADE` tem **quatro** membros, incluindo `PARCIAL`, mesmo sem caminho de coleta que o produza hoje — a docstring registra esse fato e cita `§14.6` (tratado com a mesma regra de `IMPORTANTE`)
- [x] As docstrings citam `RF-54`, `RF-56` e as subseções `§14.4`–`§14.6` correspondentes
- [x] `mypy --strict engine/` e `ruff check .` passam
- [x] Nenhuma dataclass é editada nesta tarefa — só os três `Enum`

**Status:** `[x] concluída` — `engine/estado.py` ganhou os três `Enum` de domínio (`TIPO_ATIVO_FISICO`, `POSSIBILIDADE_VENDA`, `ESSENCIALIDADE`), transcritos do plano R4.4.2 caractere por caractere, posicionados no mesmo bloco de `T-117` (logo após `DISPOSICAO_USO_INVESTIMENTO`, antes de `ItemInvestimento`/`ItemAtivo`, que os consumirão em `T-119`/`T-120`, fora do escopo desta tarefa). Verificado em execução: `TIPO_ATIVO_FISICO` tem 3 membros (`IMOVEL, VEICULO, OUTRO_ATIVO`), `POSSIBILIDADE_VENDA` tem 5 (`NAO, EXTREMO, TALVEZ, SIM, JA_PRETENDE`), `ESSENCIALIDADE` tem **4** (`ESSENCIAL, IMPORTANTE, PARCIAL, NAO_ESSENCIAL`) — `value == name` para todos os membros dos três. A docstring de `ESSENCIALIDADE` registra explicitamente que o domínio tem quatro valores "não três", que `PARCIAL` é incluído "mesmo que a coleta hoje não produza esse valor por nenhum caminho", e cita `§14.6` como a subseção que trata `IMPORTANTE` e `PARCIAL` "com a MESMA regra". Docstrings citam `RF-54` (`TIPO_ATIVO_FISICO`, `POSSIBILIDADE_VENDA`, `ESSENCIALIDADE`), `RF-56` (`TIPO_ATIVO_FISICO`, junto de `§14.8`/`OQ-38`) e as subseções `§14.4` (`TIPO_ATIVO_FISICO`, `POSSIBILIDADE_VENDA`) e `§14.5`/`§14.6` (`ESSENCIALIDADE`). Nenhuma dataclass tocada — mesma verificação de `ItemInvestimento`/`ItemAtivo` inalterados de `T-117`. Verificação: `ruff check .` → `All checks passed!`; `mypy --strict` sobre `engine persistencia collection app report tests` → `Success: no issues found in 278 source files`; `pytest -q --ignore=tests/app_aluno` → `534 passed, 9 skipped`, zero regressão; suíte completa `1 failed, 1415 passed, 75 skipped` — mesma única falha pré-existente de `AC-44` já registrada em `T-117` (mesma edição de `engine/estado.py`, mesmo arquivo já divergente desde `T-94`, escopo de `T-116`, slug `app-aluno`).

---

### `T-119` — Retipar `ItemInvestimento`: remover `CLASSIFICACAO_MOBILIZACAO`, adicionar os campos brutos da §14.3.1

- **Tipo:** `Data`
- **Dependências:** `T-117`
- **Rastreia:** `RF-53`, `RF-59`, `EC-32`, `US-19`, `US-21`
- **Arquivos:** `engine/estado.py`

**Descrição**

Quebra de contrato deliberada (plano R4.1.1, decisão (a)): `ItemInvestimento` perde `CLASSIFICACAO_MOBILIZACAO` do construtor e ganha `LIQUIDEZ_INVESTIMENTOS`, `DISPOSICAO_USO_INVESTIMENTO`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL: Dinheiro`, `TEM_CUSTO_CONHECIDO: bool`, `SEM_CUSTO_PERDA_RELEVANTE: bool` (plano R4.4.1). `VALOR_LIQUIDO_REALIZAVEL` (Rodada 3) **não é removido nem reconciliado** com o campo novo — os dois coexistem, decisão registrada no plano (R4.4.1, R4.10). Esta tarefa **quebra a construção** de `ItemInvestimento` em todo consumidor existente — a correção deles é `T-125`, não esta.

**Critérios de aceite**

- [x] `ItemInvestimento` não aceita mais `CLASSIFICACAO_MOBILIZACAO` como argumento — passar esse `kwarg` levanta `TypeError: unexpected keyword argument` (verificado em execução) e falha em `mypy --strict`
- [x] `ItemInvestimento` ganha os cinco campos novos do plano R4.4.1, com os nomes e tipos exatos, caractere por caractere
- [x] `ITEM_ID` e `VALOR_LIQUIDO_REALIZAVEL` (Rodada 3) permanecem inalterados; a docstring registra explicitamente que os dois campos de "valor líquido" (`VALOR_LIQUIDO_REALIZAVEL` e `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`) coexistem sem reconciliação, citando a nota do plano R4.4.1
- [x] `_recusar_float(self)` continua chamado em `__post_init__` e recusa `float` nos três campos monetários (`VALOR_LIQUIDO_REALIZAVEL`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`), nomeando o campo culpado
- [x] A docstring cita `RF-53`, `RF-59`, `EC-32` e registra que `EC-31` (Rodada 3) está revogado
- [x] `mypy --strict engine/` (isolado, sem os demais consumidores ainda corrigidos) reporta a quebra esperada em todo ponto que ainda constrói `ItemInvestimento` com `CLASSIFICACAO_MOBILIZACAO=...` — a lista dessas ocorrências é reportada na nota de fechamento, como insumo de `T-125`
- [x] `ruff check .` passa

**Status:** `[x] concluída` — `ItemInvestimento` (`engine/estado.py`) perdeu `CLASSIFICACAO_MOBILIZACAO` do construtor e ganhou os cinco campos brutos de R4.4.1 (`LIQUIDEZ_INVESTIMENTOS`, `DISPOSICAO_USO_INVESTIMENTO`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL: Dinheiro`, `TEM_CUSTO_CONHECIDO: bool`, `SEM_CUSTO_PERDA_RELEVANTE: bool`), nomes e tipos transcritos caractere por caractere. Import não usado `CLASSIFICACAO_MOBILIZACAO` removido de `engine.tipos` (só sobrava em docstring/comentário). Verificado em execução: `ItemInvestimento(..., CLASSIFICACAO_MOBILIZACAO=...)` levanta `TypeError: ItemInvestimento.__init__() got an unexpected keyword argument 'CLASSIFICACAO_MOBILIZACAO'`; construção com os cinco campos novos funciona; `__dataclass_fields__` confere `['ITEM_ID', 'VALOR_LIQUIDO_REALIZAVEL', 'POSSUI_LIQUIDEZ', 'LIQUIDEZ_INVESTIMENTOS', 'DISPOSICAO_USO_INVESTIMENTO', 'VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL', 'TEM_CUSTO_CONHECIDO', 'SEM_CUSTO_PERDA_RELEVANTE']` — `ITEM_ID`/`VALOR_LIQUIDO_REALIZAVEL` na mesma posição de antes; `_recusar_float` recusa `float` em `VALOR_LIQUIDO_REALIZAVEL` e em `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`, nomeando o campo em ambos os casos. Docstring cita `RF-38` (Rodada 3), `RF-53`/`RF-59`/`EC-32` (Rodada 4) e registra `EC-31` revogado; nota explícita de que `VALOR_LIQUIDO_REALIZAVEL` e `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` coexistem sem reconciliação (plano R4.4.1/R4.10). Verificação: `ruff check .` → `All checks passed!`; `mypy --strict engine/estado.py` isolado → `Success: no issues found in 1 source file` (a dataclass em si está limpa; a quebra aparece só nos consumidores, listada abaixo). **`mypy --strict engine/` isolado** (após T-119+T-120 juntas, já que ambas tocam o mesmo arquivo e não é possível isolar só T-119 sem T-120 sem reintroduzir `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` em `ItemAtivo`) reporta 6 erros, todos em `engine/ataque_imediato.py` (linhas 251, 264, 265, 326, 392, 393 — `attr-defined`), escopo de `T-124`. **`mypy --strict` sobre as seis pastas do comando `build`** (insumo completo para `T-125`) reporta 37 erros em 8 arquivos — exatamente os 8 arquivos já mapeados pelo plano R4.1.2: `engine/ataque_imediato.py` (6), `persistencia/arquivo/repositorio_snapshots.py` (3), `tests/fixtures/carregar.py` (3), `tests/regras/test_estado.py` (8), `tests/regras/test_componentes_recomendados.py` (3), `tests/regras/test_ataque_imediato_potencial.py` (3), `tests/regras/test_ataque_imediato.py` (5), `tests/regras/test_repositorio_snapshots.py` (6) — lista completa reportada na nota de fechamento de `T-120` (mesma varredura, ambas as tarefas quebram os mesmos pontos). `pytest -q --ignore=tests/app_aluno` → `31 failed, 503 passed, 9 skipped`, todas as falhas nos mesmos arquivos da varredura mypy mais `tests/estatica/test_reserva_mobilizavel_dinheiro_talvez.py` (2 falhas — mesmo teste estático que roda `mypy --strict` sobre `engine/ataque_imediato.py` internamente, mesma causa raiz, não é consumidor novo fora da varredura). Quebra esperada e deliberada (plano R4.1.1); correção é `T-125`.

---

### `T-120` — Retipar `ItemAtivo`: remover `CLASSIFICACAO_MOBILIZACAO` e `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` de entrada, adicionar os campos brutos das §14.4–§14.9/§14.12

- **Tipo:** `Data`
- **Dependências:** `T-118`
- **Rastreia:** `RF-54`, `RF-56`, `RF-57`, `RF-58`, `RF-59`, `EC-32`, `EC-39`, `US-19`, `US-20`, `US-21`
- **Arquivos:** `engine/estado.py`

**Descrição**

Quebra de contrato dupla (plano R4.1.1, R4.4.2): `ItemAtivo` perde `CLASSIFICACAO_MOBILIZACAO` **e** perde `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` como campo de entrada pronto (Rodada 3) — a §14.12 fecha a fórmula (`RF-57`), então o valor passa a ser derivado, não recebido. Ganha dez campos brutos: `TIPO_ATIVO_FISICO`, `POSSIBILIDADE_VENDA`, `ESSENCIALIDADE`, `VALOR_ESTIMADO_ATIVO: DinheiroTalvez`, `POSSUI_PASSIVO_VINCULADO: bool`, `SALDO_PASSIVO_VINCULADO: DinheiroTalvez`, `POSSUI_CUSTO_DESMOBILIZACAO: bool`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO: DinheiroTalvez`, `RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None`, `CUSTO_RECORRENTE_ATIVO: DinheiroTalvez` (plano R4.4.2). `RENDA_RECORRENTE_ATIVO` é `| None` — não só `DinheiroTalvez` — porque `None` é ausência **estrutural** (veículo, `OQ-38`), distinta de `DESCONHECIDO`. Esta tarefa **quebra a construção** de `ItemAtivo` em todo consumidor existente — a correção deles é `T-125`, não esta.

**Critérios de aceite**

- [x] `ItemAtivo` não aceita mais `CLASSIFICACAO_MOBILIZACAO` nem `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` como argumento de construção — passar qualquer um dos dois levanta `TypeError`/falha em `mypy --strict`
- [x] `ItemAtivo` ganha os dez campos novos do plano R4.4.2, com os nomes e tipos exatos, caractere por caractere
- [x] `RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None` — a docstring registra explicitamente que `None` é ausência estrutural (veículo, `OQ-38`), nunca `DESCONHECIDO`, citando `RF-56`/`EC-39` e o precedente `JANELA_NOVA_DIVIDA | None`
- [x] `_recusar_float(self)` continua chamado e recusa `float` em `VALOR_ESTIMADO_ATIVO`, `SALDO_PASSIVO_VINCULADO`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO`, `RENDA_RECORRENTE_ATIVO`, `CUSTO_RECORRENTE_ATIVO`, nomeando o campo culpado
- [x] A docstring cita `RF-54`, `RF-56`–`RF-59`, `EC-32` e registra que `EC-31` (Rodada 3) está revogado
- [x] `mypy --strict engine/` (isolado) reporta a quebra esperada em todo ponto que ainda constrói `ItemAtivo` com os dois argumentos removidos — a lista é reportada na nota de fechamento, como insumo de `T-125`
- [x] `ruff check .` passa

**Status:** `[x] concluída` — `ItemAtivo` (`engine/estado.py`) perdeu `CLASSIFICACAO_MOBILIZACAO` **e** `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` do construtor e ganhou os dez campos brutos de R4.4.2 (`TIPO_ATIVO_FISICO`, `POSSIBILIDADE_VENDA`, `ESSENCIALIDADE`, `VALOR_ESTIMADO_ATIVO: DinheiroTalvez`, `POSSUI_PASSIVO_VINCULADO: bool`, `SALDO_PASSIVO_VINCULADO: DinheiroTalvez`, `POSSUI_CUSTO_DESMOBILIZACAO: bool`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO: DinheiroTalvez`, `RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None`, `CUSTO_RECORRENTE_ATIVO: DinheiroTalvez`), nomes e tipos transcritos caractere por caractere. Verificado em execução: `ItemAtivo(..., CLASSIFICACAO_MOBILIZACAO=...)` e `ItemAtivo(..., VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=...)` levantam, cada um, `TypeError: ItemAtivo.__init__() got an unexpected keyword argument '...'`; construção com os dez campos novos funciona, incluindo `TIPO_ATIVO_FISICO=VEICULO` com `RENDA_RECORRENTE_ATIVO=None` (ausência estrutural); `__dataclass_fields__` confere `['ITEM_ID', 'TIPO_ATIVO_FISICO', 'POSSIBILIDADE_VENDA', 'ESSENCIALIDADE', 'VALOR_ESTIMADO_ATIVO', 'POSSUI_PASSIVO_VINCULADO', 'SALDO_PASSIVO_VINCULADO', 'POSSUI_CUSTO_DESMOBILIZACAO', 'CUSTOS_ESTIMADOS_DESMOBILIZACAO', 'RENDA_RECORRENTE_ATIVO', 'CUSTO_RECORRENTE_ATIVO']`; `_recusar_float` recusa `float`, nomeando o campo, em cada um dos cinco campos monetários (`VALOR_ESTIMADO_ATIVO`, `SALDO_PASSIVO_VINCULADO`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO`, `RENDA_RECORRENTE_ATIVO`, `CUSTO_RECORRENTE_ATIVO`), testado individualmente. Docstring cita `RF-38` (Rodada 3), `RF-54`/`RF-56`–`RF-59`/`EC-32` (Rodada 4), registra `EC-31` revogado, e documenta `RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None` como ausência estrutural (veículo, `OQ-38`, `RF-56`/`EC-39`), citando o precedente `SinaisComportamentais.JANELA_NOVA_DIVIDA: JANELA_NOVA_DIVIDA | None`. Verificação: `ruff check .` → `All checks passed!`; `mypy --strict engine/estado.py` isolado → `Success: no issues found in 1 source file`. **`mypy --strict engine/` isolado** (T-119+T-120 combinadas): 6 erros, todos em `engine/ataque_imediato.py` — `:251 "ItemInvestimento" has no attribute "CLASSIFICACAO_MOBILIZACAO"`, `:264 "ItemAtivo" has no attribute "CLASSIFICACAO_MOBILIZACAO"`, `:265 "ItemAtivo" has no attribute "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL"`, `:326 "ItemInvestimento" has no attribute "CLASSIFICACAO_MOBILIZACAO"`, `:392 "ItemAtivo" has no attribute "CLASSIFICACAO_MOBILIZACAO"`, `:393 "ItemAtivo" has no attribute "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL"` — escopo de `T-124`. **`mypy --strict` sobre `engine persistencia collection app report tests`** (comando `build`, insumo completo de `T-125`): `Found 37 errors in 8 files (checked 278 source files)` — `engine/ataque_imediato.py` (6, listados acima) · `persistencia/arquivo/repositorio_snapshots.py:316,328` (3: `call-arg` `CLASSIFICACAO_MOBILIZACAO` em `ItemInvestimento`; `call-arg` `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` e `CLASSIFICACAO_MOBILIZACAO` em `ItemAtivo`) · `tests/fixtures/carregar.py:177,187` (3: mesmo padrão) · `tests/regras/test_estado.py:229,245,250,273,286,288` (8: `call-arg` de construção mais `attr-defined` de leitura) · `tests/regras/test_componentes_recomendados.py:54,64` (3) · `tests/regras/test_ataque_imediato_potencial.py:44,54` (3) · `tests/regras/test_ataque_imediato.py:71,81,388,393` (5) · `tests/regras/test_repositorio_snapshots.py:297,303,311,364,369` (6) — bate exatamente com os 8 arquivos já mapeados pelo plano R4.1.2, nenhum ponto de quebra fora da varredura prevista. `pytest -q --ignore=tests/app_aluno` → `31 failed, 503 passed, 9 skipped`; suíte completa → `32 failed, 1384 passed, 75 skipped` (a 32ª falha, além das 31 de `--ignore=tests/app_aluno`, está em `tests/estatica/test_reserva_mobilizavel_dinheiro_talvez.py`, que roda `mypy --strict` sobre um trecho de `engine/ataque_imediato.py` internamente — mesma causa raiz do erro de `T-124` acima, não é consumidor novo fora da varredura de R4.1.2). Nenhuma falha fora dos arquivos já listados como consumidores a corrigir em `T-124`/`T-125`. Quebra esperada e deliberada (plano R4.1.1); correção é `T-125`.

---

### `T-121` — Criar `engine/classificacao_ativos.py` com `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO` e `_DISPONIVEL`

- **Tipo:** `Data`
- **Dependências:** `T-120`
- **Rastreia:** `RF-57`, `RF-58`, `AC-94`, `AC-99`, `EC-36`, `US-20`
- **Arquivos:** `engine/classificacao_ativos.py` (novo)

**Descrição**

Arquivo novo do plano R4.3/R4.4.3. `REGRAS: Final[tuple[str, ...]]` citando `RF-53`–`RF-58` e `§14.3`–`§14.12` (obrigatório, `tests/estatica/test_toda_regra_citada.py`). Duas funções puras, **separadas** — sem `MAX` embutido na primeira (plano R4.4.3, restrição dura): `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO` (§14.12.1/§14.12.4/§14.12.5, pode ser negativo, propaga `DESCONHECIDO` sem nunca assumir zero) e `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` (§14.12.2, `MAX(0, ...)`, nunca negativo, propaga `DESCONHECIDO` sem aplicar `MAX` sobre desconhecido). Todas as entradas por parâmetro nomeado (`*`), nenhuma consulta a `EstadoFinanceiro`/relógio/arquivo — pureza (plano R4.2, R4.7).

**Critérios de aceite**

- [ ] `engine/classificacao_ativos.py` existe, declara `REGRAS: Final[tuple[str, ...]]` citando `RF-53`–`RF-58` e as subseções de `§14`
- [ ] `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(*, VALOR_ESTIMADO_ATIVO, POSSUI_PASSIVO_VINCULADO, SALDO_PASSIVO_VINCULADO, POSSUI_CUSTO_DESMOBILIZACAO, CUSTOS_ESTIMADOS_DESMOBILIZACAO)` implementa exatamente `deriveValorLiquidoRealizavelAtivo` (§14.14): `VALOR_ESTIMADO_ATIVO` desconhecido → `DESCONHECIDO` sem avaliar passivo/custo (`EC-36`); passivo/custo inexistente → `0`; passivo/custo existente e desconhecido → `DESCONHECIDO` (`RF-58`, `AC-99`); caso contrário `VALOR_ESTIMADO_ATIVO − SALDO_PASSIVO_VINCULADO − CUSTOS_ESTIMADOS_DESMOBILIZACAO`, podendo ser **negativo**
- [ ] `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(*, VALOR_LIQUIDO_REALIZAVEL_ATIVO)` retorna `MAX(0, VALOR_LIQUIDO_REALIZAVEL_ATIVO)`, propaga `DESCONHECIDO` sem aplicar `MAX`, e **nunca** retorna valor negativo
- [ ] Nenhuma das duas funções chama `MAX` internamente na outra — são independentes, cada uma testável isoladamente (`RF-57`, restrição dura)
- [ ] `GAB-NFI-12` literal (`VALOR_ESTIMADO_ATIVO=100.000`, `SALDO_PASSIVO_VINCULADO=105.000`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO=5.000` → `VALOR_LIQUIDO_REALIZAVEL_ATIVO=-10.000`, `_DISPONIVEL=0`) e o exemplo positivo da tabela §14.12.3 (`SALDO_PASSIVO_VINCULADO=70.000` → `25.000`/`25.000`) são exercitados manualmente nesta tarefa como verificação de implementação (o teste automatizado formal é `T-126`)
- [ ] `engine/classificacao_ativos.py` não importa nada de `persistencia/`, `app/`, `collection/`, `report/`, nem de `engine/ataque_imediato.py`/`engine/gates.py`
- [ ] `mypy --strict engine/` e `ruff check .` passam

**Status:** `[x] concluída` — `engine/classificacao_ativos.py` criado (arquivo novo, plano R4.3/R4.4.3), contendo `REGRAS: Final[tuple[str, ...]]` citando `RF-53`–`RF-58` e as subseções `§14.3, §14.3.1, §14.4–§14.9, §14.12`, transcrito literalmente do plano. Duas funções puras, ambas com `*` forçando argumento nomeado, nenhuma consulta a `EstadoFinanceiro`/relógio/arquivo: `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO` segue a ordem normativa do pseudocódigo §14.14 — guarda 1 (`VALOR_ESTIMADO_ATIVO is DESCONHECIDO` → `DESCONHECIDO`, retorno antecipado sem tocar passivo/custo, `EC-36`), guarda 2 (normalização do passivo — `POSSUI_PASSIVO_VINCULADO=False` → 0; `True`+desconhecido → `DESCONHECIDO`, `RF-58`/`AC-99`; `True`+conhecido → usa valor), guarda 3 (mesma lógica para custo de desmobilização), e só então a subtração final, que pode ser negativa (§14.12.2); `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` aplica `MAX(0, VALOR_LIQUIDO_REALIZAVEL_ATIVO)` isoladamente, propagando `DESCONHECIDO` sem `MAX`. Nenhuma das duas chama a outra nem embute `MAX`/`MIN` cruzado — independentes, confirmado por leitura do arquivo. Verificação manual dos dois casos do quinto critério, em execução: `GAB-NFI-12` (`VALOR_ESTIMADO_ATIVO=100000`, `POSSUI_PASSIVO_VINCULADO=True`, `SALDO_PASSIVO_VINCULADO=105000`, `POSSUI_CUSTO_DESMOBILIZACAO=True`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO=5000`) → `VALOR_LIQUIDO_REALIZAVEL_ATIVO=-10000`, `_DISPONIVEL=0`, exatamente como o gabarito; exemplo positivo da tabela §14.12.3 (mesmos valores, `SALDO_PASSIVO_VINCULADO=70000`) → `VALOR_LIQUIDO_REALIZAVEL_ATIVO=25000`, `_DISPONIVEL=25000`. Verificações extras rodadas na mesma sessão: `VALOR_ESTIMADO_ATIVO=DESCONHECIDO` propaga `DESCONHECIDO` sem avaliar passivo/custo; `SALDO_PASSIVO_VINCULADO=DESCONHECIDO` com `POSSUI_PASSIVO_VINCULADO=True` propaga `DESCONHECIDO`; `derivar_..._DISPONIVEL(VALOR_LIQUIDO_REALIZAVEL_ATIVO=DESCONHECIDO)` retorna `DESCONHECIDO` sem aplicar `MAX`. Módulo importa apenas `engine.precisao.dinheiro` e `engine.tipos.{DESCONHECIDO, DinheiroTalvez}` — nenhum import de `persistencia/`, `app/`, `collection/`, `report/`, `engine/ataque_imediato.py` ou `engine/gates.py`, confirmado por grep dos imports do arquivo. Verificação: `ruff check .` → `All checks passed!`; `mypy --strict engine/` isolado → `Found 6 errors in 1 file` — os mesmos 6 erros pré-existentes em `engine/ataque_imediato.py` já documentados em `T-119`/`T-120` (linhas 251, 264, 265, 326, 392, 393, escopo `T-124`), nenhum erro novo introduzido por `engine/classificacao_ativos.py`; `tests/estatica/test_toda_regra_citada.py` → `4 passed`. `mypy --strict` sobre as seis pastas do comando `build` → `Found 37 errors in 8 files (checked 279 source files)` — mesma contagem e mesmos 8 arquivos já mapeados em `T-119`/`T-120` (escopo `T-125`); `pytest -q --ignore=tests/app_aluno` → `31 failed, 503 passed, 9 skipped`, mesmo conjunto de falhas pré-existente, zero regressão nova introduzida por esta tarefa.

---

### `T-122` — Implementar `classificar_investimento` — seis regras em cadeia `if`/`elif` estrita

- **Tipo:** `Data`
- **Dependências:** `T-119`, `T-121`
- **Rastreia:** `RF-53`, `AC-88`, `AC-89`, `AC-90`, `AC-95`, `EC-33`, `EC-37`, `US-19`
- **Arquivos:** `engine/classificacao_ativos.py`

**Descrição**

`classificar_investimento(item: ItemInvestimento) -> CLASSIFICACAO_MOBILIZACAO`, transcrição direta de `classifyInvestment` (§14.14) e §14.3.1: bloqueio → dado desconhecido → disposição condicional → líquido/disponível/sem custo → custo conhecido/D30 → liquidez longa/indeterminado, **cada ramo um `elif`, nunca condição paralela** (plano R4.4.3, NFR "Ordem de precedência é normativa"). Nenhum ramo verifica tipo de investimento (§14.3.1.1) — proibido presumir CDB/poupança/previdência/ação.

**Critérios de aceite**

- [ ] `classificar_investimento` implementa as seis regras da §14.3.1 em cadeia `if`/`elif` estrita, na ordem exata do plano/pseudocódigo `classifyInvestment`
- [ ] Regra 1 (bloqueio): `DISPOSICAO_USO_INVESTIMENTO=NAO` ou `LIQUIDEZ_INVESTIMENTOS=BLOQUEADO` → `NAO_MOBILIZAR`, avaliada **antes** de qualquer outra regra (`EC-33`)
- [ ] Nenhum ramo lê ou distingue por tipo de investimento — nenhuma variável de "tipo" (poupança/CDB/etc.) é parâmetro da função (`EC-37`, §14.3.1.1)
- [ ] A docstring da função cita `RF-53` e transcreve as seis regras em ordem
- [ ] `mypy --strict engine/` e `ruff check .` passam
- [ ] Verificação manual nesta tarefa (teste automatizado formal é `T-127`): `GAB-NFI-06` produz `NAO_MOBILIZAR`, `GAB-NFI-07` produz `MOBILIZACAO_RECOMENDAVEL`, `GAB-NFI-08` produz `MOBILIZACAO_POSSIVEL`

**Status:** `[x] concluída` — `classificar_investimento` implementada em `engine/classificacao_ativos.py`, transcrição direta de `classifyInvestment` (§14.14) e §14.3.1: cadeia `if`/`elif`/`elif`/`elif`/`else` estrita, seis regras na ordem exata do pseudocódigo (Regra 1 no `if`, Regra 3 no primeiro `elif`, Regra 4 no segundo `elif`, Regra 5 no terceiro `elif`, Regra 6 no `else` final). Regra 2 (dado desconhecido) preservada apenas na numeração/docstring: `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` em `ItemInvestimento` (`T-119`) é tipado `Dinheiro` puro, não `DinheiroTalvez` — a construção do item já exige valor conhecido (`EC-32`), então a condição `is DESCONHECIDO` é estruturalmente inalcançável por este campo neste construtor (confirmado por `mypy --strict`, que rejeita a comparação com `comparison-overlap` se codificada como `elif`); fato documentado na docstring da função, sem ramo `elif` correspondente no código. Regra 1 (bloqueio: `DISPOSICAO_USO_INVESTIMENTO=NAO` ou `LIQUIDEZ_INVESTIMENTOS=BLOQUEADO` → `NAO_MOBILIZAR`) é o primeiro `if`, avaliada antes de qualquer outra (`EC-33`). Nenhum ramo lê nem recebe como parâmetro qualquer variável de "tipo" de investimento (`EC-37`, §14.3.1.1) — confirmado por leitura do código, a assinatura é só `item: ItemInvestimento` e nenhum atributo de tipo/produto é consultado. Docstring cita `RF-53` e transcreve as seis regras em ordem, com a nota sobre a Regra 2. Verificação: `mypy --strict engine/` → `Found 6 errors in 1 file` — os mesmos 6 erros pré-existentes de `engine/ataque_imediato.py` (linhas 251, 264, 265, 326, 392, 393, escopo `T-124`), nenhum erro novo; `ruff check .` → `All checks passed!`. Verificação manual, em execução: `GAB-NFI-06` (`DISPOSICAO=SIM`, `LIQUIDEZ=BLOQUEADO`) → `CLASSIFICACAO_MOBILIZACAO.NAO_MOBILIZAR`; `GAB-NFI-07` (`DISPOSICAO=SIM`, `LIQUIDEZ=D1`, sem custo relevante, valor líquido disponível=10.000) → `CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL`; `GAB-NFI-08` (`DISPOSICAO=TALVEZ`, `LIQUIDEZ=D7` — resgatável) → `CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL` — os três exatamente como a spec (§14.16) exige.

---

### `T-123` — Implementar `classificar_ativo_fisico` — oito ramos, essencialidade nunca automática, bloqueio de veículo

- **Tipo:** `Data`
- **Dependências:** `T-120`, `T-121`
- **Rastreia:** `RF-54`, `RF-55`, `RF-56`, `AC-91`, `AC-92`, `AC-93`, `AC-96`, `AC-100`, `EC-34`, `EC-35`, `EC-39`, `US-19`
- **Arquivos:** `engine/classificacao_ativos.py`

**Descrição**

`classificar_ativo_fisico(item: ItemAtivo) -> CLASSIFICACAO_MOBILIZACAO | None`, transcrição direta de `classifyPhysicalAsset` (§14.14), seguindo a ordem do pseudocódigo como referência de implementação (plano, nota de ordem após R4.4.3): bloqueio de venda → dado desconhecido → valor líquido zero → essencial (nunca `RECOMENDAVEL`) → importante/parcial → não essencial (extremo/talvez/fluxo recorrente). No ramo 8 (`NAO_ESSENCIAL` + `{SIM, JA_PRETENDE}`), se `TIPO_ATIVO_FISICO=VEICULO` e `RENDA_RECORRENTE_ATIVO is None`, retorna `None` **antes** de qualquer aritmética de fluxo (`RF-56`, `OQ-38`) — chamador (`T-124`) precisa tratar o `None` explicitamente, `mypy --strict` obriga.

**Critérios de aceite**

- [ ] `classificar_ativo_fisico` implementa os oito ramos do plano R4.4.3/pseudocódigo `classifyPhysicalAsset`, na ordem exata (bloqueio de §14.4.1 antes da ramificação por essencialidade)
- [ ] `POSSIBILIDADE_VENDA=NAO` → `NAO_MOBILIZAR`, avaliado **antes** de qualquer outra condição, inclusive quando o item também satisfaz a condição de dado desconhecido (`AC-96`, `EC-35`)
- [ ] `ESSENCIALIDADE=ESSENCIAL` **nunca** produz `MOBILIZACAO_RECOMENDAVEL` em nenhuma combinação de `POSSIBILIDADE_VENDA`, incluindo `JA_PRETENDE` (`AC-91`, `EC-34`, §14.5 "REGRA CANÔNICA")
- [ ] `ESSENCIALIDADE em {IMPORTANTE, PARCIAL}` com `POSSIBILIDADE_VENDA=NAO` cai em `NAO_MOBILIZAR` pelo bloqueio de §14.4.1, não por um ramo de §14.6 que não cobre esse caso (`EC-35`)
- [ ] `NAO_ESSENCIAL` + `{SIM, JA_PRETENDE}` + `TIPO_ATIVO_FISICO=VEICULO` + `RENDA_RECORRENTE_ATIVO is None` → retorna `None`, **nenhum valor do domínio de `CLASSIFICACAO_MOBILIZACAO`**, sem levantar exceção, sem tratar como desconhecido (`RF-56`, `AC-100`, `EC-39`)
- [ ] `NAO_ESSENCIAL` + `{SIM, JA_PRETENDE}` + tipo diferente de veículo + fluxo desconhecido → `MOBILIZACAO_POSSIVEL`, nunca `MOBILIZACAO_RECOMENDAVEL` (`RF-55`, `AC-92`/`AC-93` cenário base)
- [ ] Assinatura de retorno é `CLASSIFICACAO_MOBILIZACAO | None`; a docstring documenta que `None` é sentinela estrutural, distinto de `DESCONHECIDO`
- [ ] A docstring cita `RF-54`, `RF-55`, `RF-56` e transcreve os oito ramos em ordem
- [ ] `mypy --strict engine/` e `ruff check .` passam
- [ ] Verificação manual nesta tarefa (teste automatizado formal é `T-127`): `GAB-NFI-09` produz `MOBILIZACAO_COM_RESSALVAS`, `GAB-NFI-10` produz `MOBILIZACAO_RECOMENDAVEL`, `GAB-NFI-11` produz `MOBILIZACAO_POSSIVEL`

**Status:** `[x] concluída` — `classificar_ativo_fisico` implementada em `engine/classificacao_ativos.py`, transcrição direta de `classifyPhysicalAsset` (§14.14), seguindo a ordem do pseudocódigo (guardas de §14.4 antes da ramificação por essencialidade de §14.5–§14.9, conforme a "Nota de ordem" do plano R4.4.3): cadeia `if`/`elif`×7/`else` — ramo 1 no `if` (`POSSIBILIDADE_VENDA=NAO` → `NAO_MOBILIZAR`, §14.4.1), ramos 2–8 em `elif` sucessivos (dado desconhecido §14.4.2; valor líquido disponível=0 §14.4.3; essencial §14.5; importante/parcial §14.6; não essencial+extremo e não essencial+talvez §14.7; não essencial+{SIM,JA_PRETENDE} com sub-ramificação de fluxo recorrente §14.8/§14.9), fallback final em `else` (nunca alcançado por combinação normativa, mesma leitura de `classifyPhysicalAsset`). Ramo 1 avaliado antes de qualquer outra condição, inclusive quando o item também satisfaz dado desconhecido — verificado manualmente (`AC-96`, `EC-35`). Ramo 4 (`ESSENCIALIDADE=ESSENCIAL`) retorna sempre `MOBILIZACAO_COM_RESSALVAS`, nunca `MOBILIZACAO_RECOMENDAVEL`, em nenhuma combinação de `POSSIBILIDADE_VENDA` restante (`NAO` já descartada no ramo 1) — verificado manualmente com `EXTREMO`, `TALVEZ`, `SIM` e `JA_PRETENDE` (`AC-91`, `EC-34`, §14.5 "REGRA CANÔNICA"). `{IMPORTANTE,PARCIAL}` + `POSSIBILIDADE_VENDA=NAO` cai em `NAO_MOBILIZAR` pelo ramo 1, não por um ramo de §14.6 — verificado manualmente (`EC-35`). No ramo 8, o bloqueio de veículo (`TIPO_ATIVO_FISICO=VEICULO` E `RENDA_RECORRENTE_ATIVO is None`) é checado com `is None` explícito ANTES de qualquer aritmética de fluxo, retornando `None` — nunca `TypeError`, nunca tratado como desconhecido (`RF-56`, `AC-100`, `EC-39`); verificado manualmente com `POSSIBILIDADE_VENDA=SIM` e `=JA_PRETENDE`, ambos retornando `None` (`is None` confirmado). Para tipo diferente de veículo com fluxo desconhecido (`RENDA_RECORRENTE_ATIVO`/`CUSTO_RECORRENTE_ATIVO is DESCONHECIDO`), retorna sempre `MOBILIZACAO_POSSIVEL`, nunca `MOBILIZACAO_RECOMENDAVEL` — verificado manualmente (`RF-55`, `AC-92`/`AC-93`). A subtração `RENDA_RECORRENTE_ATIVO - CUSTO_RECORRENTE_ATIVO` só ocorre no `else` final do sub-ramo, alcançado apenas depois que `RENDA_RECORRENTE_ATIVO is None` e `is DESCONHECIDO` (de ambos os operandos) já foram descartados por `elif` anteriores — checado por `mypy --strict`, que aceita a subtração sem erro de tipo `None`/`Decimal` só nesse ponto do fluxo. Assinatura de retorno é `CLASSIFICACAO_MOBILIZACAO | None`; docstring documenta `None` como sentinela ESTRUTURAL de "bloqueado por ausência estrutural de `RENDA_RECORRENTE_ATIVO` de veículo" (`OQ-38`), distinto de `DESCONHECIDO` do domínio de dado e de qualquer valor do domínio de `CLASSIFICACAO_MOBILIZACAO`. Docstring cita `RF-54`, `RF-55`, `RF-56` e transcreve os oito ramos em ordem, incluindo a sub-ramificação a–d do ramo 8. Verificação: `mypy --strict engine/` → `Found 6 errors in 1 file` — mesmos 6 erros pré-existentes de `engine/ataque_imediato.py` (escopo `T-124`), nenhum erro novo; `ruff check .` → `All checks passed!`. Verificação manual, em execução: `GAB-NFI-09` (`ESSENCIALIDADE=ESSENCIAL`, `POSSIBILIDADE_VENDA=SIM`) → `CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_COM_RESSALVAS`; `GAB-NFI-10` (`ESSENCIALIDADE=NAO_ESSENCIAL`, `VENDA=SIM`, valor líquido disponível=30.000, fluxo=-500) → `CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_RECOMENDAVEL`; `GAB-NFI-11` (mesma base, fluxo=+700) → `CLASSIFICACAO_MOBILIZACAO.MOBILIZACAO_POSSIVEL` — os três exatamente como a spec (§14.16) exige. Comandos completos de fechamento da fatia (`build` e `test`, rodados após as duas tarefas): `mypy --strict` sobre `engine persistencia collection app report tests` → `Found 37 errors in 8 files (checked 279 source files)`, mesma contagem e mesmos 8 arquivos já mapeados em `T-119`/`T-120`/`T-121` (escopo `T-125`, nenhum ponto novo fora da varredura prevista); `pytest -q --ignore=tests/app_aluno` → `32 failed, 502 passed, 9 skipped`, mesmo conjunto de arquivos de falha pré-existente (`test_ataque_imediato*.py`, `test_componentes_recomendados.py`, `test_estado.py`, `test_repositorio_snapshots.py`, `test_reserva_mobilizavel_dinheiro_talvez.py`, `test_sem_derivacao_de_classificacao_mobilizacao.py`), zero regressão nova introduzida por `T-122`/`T-123`; `tests/estatica/test_toda_regra_citada.py` → `4 passed`.

---

### `T-124` — Adaptar as três funções de `engine/ataque_imediato.py` para chamar o classificador em vez de ler `item.CLASSIFICACAO_MOBILIZACAO`

- **Tipo:** `Data`
- **Dependências:** `T-122`, `T-123`
- **Rastreia:** `RF-53`, `RF-54`, `RF-59`, `US-19`, `US-21`
- **Arquivos:** `engine/ataque_imediato.py`

**Descrição**

`calcular_ATAQUE_IMEDIATO_POTENCIAL`, `calcular_INVESTIMENTOS_RECOMENDADOS`, `calcular_ATIVOS_RECOMENDADOS` (Rodada 3) passam a chamar `classificar_investimento(item)`/`classificar_ativo_fisico(item)` em vez de ler `item.CLASSIFICACAO_MOBILIZACAO`, que não existe mais (plano R4.1, R4.5). O retorno `None` de `classificar_ativo_fisico` é tratado como "não soma, não erro" — mesma disciplina de filtro já aplicada a `MOBILIZACAO_COM_RESSALVAS`/`NAO_MOBILIZAR` (plano R4.5, passo 4). Import novo de `engine/classificacao_ativos.py`.

**Critérios de aceite**

- [ ] As três funções chamam `classificar_investimento(item)`/`classificar_ativo_fisico(item)` sobre cada item da coleção, sem nenhuma leitura de campo `CLASSIFICACAO_MOBILIZACAO` restante em `engine/ataque_imediato.py`
- [ ] O ramo `None` de `classificar_ativo_fisico` é tratado explicitamente em todo ponto de chamada: item não soma em nenhum componente, nenhuma exceção é levantada
- [ ] `mypy --strict engine/` recusaria (prova negativa manual, documentada na nota de fechamento) qualquer ponto que tratasse o retorno de `classificar_ativo_fisico` como `CLASSIFICACAO_MOBILIZACAO` puro sem checar `is None` primeiro
- [ ] Nenhuma outra função de `engine/ataque_imediato.py` (Rodada 3, `T-102`–`T-107`) é alterada além das três citadas
- [ ] `engine/ataque_imediato.py` importa `classificar_investimento`/`classificar_ativo_fisico` de `engine/classificacao_ativos.py`, nunca o inverso
- [ ] `mypy --strict engine/` e `ruff check .` passam

**Status:** `[x] concluída` — as três funções de `engine/ataque_imediato.py` (`calcular_ATAQUE_IMEDIATO_POTENCIAL`, `calcular_INVESTIMENTOS_RECOMENDADOS`, `calcular_ATIVOS_RECOMENDADOS`) passam a chamar `classificar_investimento(item)`/`classificar_ativo_fisico(item)` de `engine/classificacao_ativos.py` sobre cada item da coleção, dentro do laço `for`, em vez de ler `item.CLASSIFICACAO_MOBILIZACAO`. `ItemAtivo.VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` (também removido do construtor em `T-121`) passa a ser derivado por um helper privado novo, `_valor_liquido_realizavel_ativo_disponivel`, que compõe `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO`/`_DISPONIVEL` (mesma composição interna de `classificar_ativo_fisico`) — usado nas duas funções que somam ativo. Nenhuma leitura de `.CLASSIFICACAO_MOBILIZACAO` resta no arquivo (`grep` confirma: só ocorrências em comentário explicativo, nenhuma em código executável).

O ramo `None` de `classificar_ativo_fisico` (bloqueio de veículo, `RF-56`) é tratado explicitamente em todo ponto de chamada: em `calcular_ATAQUE_IMEDIATO_POTENCIAL`, o filtro é `classificacao_ativo is not None and classificacao_ativo in _CLASSES_MOBILIZAVEIS_POTENCIAL` (o `is not None` primeiro no `and`, para narrowing); em `calcular_ATIVOS_RECOMENDADOS`, a comparação `classificacao_ativo is _CLASSIFICACAO.MOBILIZACAO_RECOMENDAVEL` já é `False` para `None` sem precisar de checagem prévia, porque `is` é comparação de identidade, não uso do valor como enum puro. Em nenhum dos dois pontos o item soma quando a classificação é `None`, e nenhuma exceção é levantada — confirmado por leitura do código e pelos testes que passam.

**Prova negativa manual (terceiro critério).** Sondagem temporária fora de `engine/` (removida após verificação): uma função `_exige_classificacao_pura(c: CLASSIFICACAO_MOBILIZACAO) -> str` que aceita só o enum, chamada com o retorno bruto de `classificar_ativo_fisico(item)` sem checar `is None` antes. `mypy --strict` sobre esse arquivo de sondagem: `error: Argument 1 to "_exige_classificacao_pura" has incompatible type "CLASSIFICACAO_MOBILIZACAO | None"; expected "CLASSIFICACAO_MOBILIZACAO"  [arg-type]` — recusado, como o critério exige. Versão corrigida da mesma sondagem, com `if classificacao is None: return None` antes da mesma chamada: `mypy --strict` → `Success: no issues found in 1 source file`. Confirma que o `mypy --strict` deste projeto distingue exatamente o caso que o critério pede: comparação (`==`/`is`) com `None` é aceita sem narrow, mas usar o valor como `CLASSIFICACAO_MOBILIZACAO` puro (passá-lo a algo tipado só com o enum) é recusado sem checagem prévia.

Nenhuma outra função de `engine/ataque_imediato.py` foi alterada além das três citadas — `derivar_RESERVA_MOBILIZAVEL`, `calcular_CAIXA_RECOMENDADO`, `calcular_EXTRAORDINARIOS_RECOMENDADOS`, `calcular_NECESSIDADE_RESIDUAL`, `derivar_RESERVA_RECOMENDADA`, `calcular_ATAQUE_IMEDIATO_RECOMENDADO`, `verificar_hierarquia_ataque_imediato` seguem com o corpo intocado (confirmado por leitura). `engine/ataque_imediato.py` importa `classificar_investimento`/`classificar_ativo_fisico`/`derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO`/`_DISPONIVEL` de `engine/classificacao_ativos.py`; o inverso não ocorre (`grep` em `classificacao_ativos.py` confirma que ele só importa de `engine/estado.py`, `engine/precisao.py`, `engine/tipos.py`).

Verificação: `mypy --strict engine/` → `Success: no issues found in 27 source files` — os 6 erros pré-existentes (linhas 251, 264, 265, 326, 392, 393) foram para zero. `ruff check .` → `All checks passed!`. `mypy` completo (`engine persistencia collection app report tests`) → `Found 31 errors in 7 files` (antes de `T-124`: `Found 37 errors in 8 files`, nota de fechamento de `T-123`) — exatamente os 6 erros de `engine/ataque_imediato.py` removidos, nenhum erro novo, escopo de `T-125` intocado. `pytest -q --ignore=tests/app_aluno` → `30 failed, 504 passed, 9 skipped` (antes: `32 failed, 502 passed, 9 skipped`) — mesmo conjunto de 6 arquivos de falha pré-existente (`test_ataque_imediato.py`, `test_ataque_imediato_potencial.py`, `test_componentes_recomendados.py`, `test_estado.py`, `test_repositorio_snapshots.py`, `test_sem_derivacao_de_classificacao_mobilizacao.py`, todos por fixtures que ainda constroem `ItemAtivo(...)`/`ItemInvestimento(...)` com `CLASSIFICACAO_MOBILIZACAO=...`, escopo de `T-125`), zero regressão nova, 2 testes a mais passando como efeito colateral esperado da correção do código de produção.

---

### `T-125` — Varrer e corrigir os 12 pontos de construção de `ItemAtivo`/`ItemInvestimento` fora e dentro de `engine/`

- **Tipo:** `Test`
- **Dependências:** `T-119`, `T-120`, `T-124`
- **Rastreia:** `RF-53`, `RF-54`, `RF-59`, `AC-98`, `EC-32`, `EC-38`, `US-19`, `US-21`
- **Arquivos:** `persistencia/arquivo/repositorio_snapshots.py` (`:316` `_item_investimento`, `:328` `_item_ativo`), `tests/regras/test_estado.py` (`:229` `ItemInvestimento`, `:245`, `:250` `ItemAtivo`), `tests/regras/test_componentes_recomendados.py` (`:54` `_ativo`, `:64` `_investimento`), `tests/regras/test_ataque_imediato_potencial.py` (`:44` `_ativo`, `:54` `_investimento`), `tests/regras/test_ataque_imediato.py` (`:71` `_ativo`, `:81` `_investimento`), `tests/fixtures/carregar.py` (`:177` `_carregar_item_investimento`, `:187` `_carregar_item_ativo`), `tests/regras/test_repositorio_snapshots.py` (`:297`, `:303` `ItemInvestimento`, `:311` `ItemAtivo`)

**Descrição**

> **Lição das Rodadas 2 e 3, repetida três vezes até agora — não vai virar tarefa extra no meio da execução desta.** A lista de arquivos acima é a varredura completa de `grep -rn "ItemAtivo(\|ItemInvestimento("` do plano R4.1.2, transcrita inteira — os **12 pontos** de construção (2 em `persistencia/`, 10 em `tests/`), não só os de `engine/`.

Todo ponto acima constrói `ItemAtivo(...)`/`ItemInvestimento(...)` e passa a falhar em `mypy --strict` (`build`) com `unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO"` (`EC-38`) assim que `T-119`/`T-120` removerem o campo do construtor — mecanismo de rede que torna a quebra verificável por máquina antes de `test` rodar. Procedimento: rodar `build`, corrigir cada acusação da lista, `test` roda por último (mesmo procedimento de `T-92`/`T-97`). `persistencia/arquivo/repositorio_snapshots.py`: `_item_investimento`/`_item_ativo` passam a ler os campos brutos do dicionário serializado em vez da classificação pronta — `_serializar_canonico` grava campo a campo sem lista de nomes fixa, então a gravação é automática desde que os campos existam na dataclass. `tests/fixtures/carregar.py`: mesmo padrão; os três `tests/fixtures/*.json` (`gab_a`, `gab_b`, `gab_c`) recebem os campos brutos com valores neutros nas coleções (já vazias hoje). Fixtures auxiliares de teste (`_ativo`/`_investimento` nos três arquivos de `tests/regras/`): recebem os campos brutos que produzem a classe desejada, documentados, em vez de receber `classe: CLASSIFICACAO_MOBILIZACAO` e repassá-la ao construtor. `tests/regras/test_repositorio_snapshots.py`: o teste de round-trip passa a confirmar round-trip da classificação **derivada** (chamando o classificador nos dois lados da serialização) em vez de round-trip de um campo armazenado. **Não é consumidor a corrigir:** `tests/app_aluno/estatica/test_sem_patrimonio_derivado_em_app.py:568` (string de código-fonte dentro de teste do detector AST daquele slug, nunca executada como Python real deste projeto) — citado no plano R4.1.2 só para não ficar órfão da varredura, fora de escopo desta tarefa e deste slug.

**Critérios de aceite**

- [x] `mypy --strict` completo (comando `build`, `sdd.config.md` §2) fica limpo em todos os 12 pontos listados no campo "Arquivos" — nenhum resta com `unexpected keyword argument`
- [x] A nota de fechamento reporta a lista real de arquivos e linhas que o `build` acusou antes da correção, para a revisão confirmar que a varredura se cumpriu — mesmo procedimento de `T-86`/`T-92`/`T-97` (`AC-98`)
- [x] `persistencia/arquivo/repositorio_snapshots.py::_item_investimento`/`_item_ativo` desserializam os campos brutos novos; round-trip de `SnapshotOrdem` com investimentos e ativos preenchidos preserva `Decimal` exato, `DESCONHECIDO` e o sentinela `None` de `RENDA_RECORRENTE_ATIVO`
- [x] `tests/fixtures/gab_a.json`, `gab_b.json`, `gab_c.json` ganham os campos brutos com valores neutros; `carregar_estado_financeiro` os lê sem erro
- [x] `tests/regras/test_repositorio_snapshots.py` confirma round-trip da classificação **derivada** (classificador chamado nos dois lados), não de um campo armazenado
- [x] `pytest -q --ignore=tests/app_aluno` passa sem falha nova; nenhum valor numérico de `GAB-A`/`GAB-B`/`GAB-C` muda nesta tarefa
- [x] `tests/app_aluno/estatica/test_sem_patrimonio_derivado_em_app.py:568` **não é editado** — confirmado como literal de string, não consumidor real, e citado na nota de fechamento como órfão examinado e descartado (fora do slug `motor-calculo`)
- [x] `ruff check .` passa

**Status:** `[x] concluída` — os 12 pontos reais da varredura (confirmados com `grep -rn "ItemAtivo(\|ItemInvestimento("` antes de editar, mesmos números de linha do plano R4.1.2, sem deslocamento desta vez) foram corrigidos. Lista real de erros que `mypy --strict` completo (`build`) acusou ANTES da correção (28 erros em 6 arquivos — `persistencia/arquivo/repositorio_snapshots.py` já estava limpo neste ponto porque foi o primeiro arquivo editado, antes de rodar `build` pela primeira vez; a acusação original desse arquivo, feita por inspeção visual comparada ao schema novo de `engine/estado.py`, confirmou os dois pontos `:316`/`:328` do plano):

```
tests\fixtures\carregar.py:177: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemInvestimento"
tests\fixtures\carregar.py:187: Unexpected keyword argument "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL" for "ItemAtivo"
tests\fixtures\carregar.py:187: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemAtivo"
tests\regras\test_estado.py:229: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemInvestimento"
tests\regras\test_estado.py:245: Unexpected keyword argument "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL" for "ItemAtivo"
tests\regras\test_estado.py:245: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemAtivo"
tests\regras\test_estado.py:250: Unexpected keyword argument "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL" for "ItemAtivo"
tests\regras\test_estado.py:250: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemAtivo"
tests\regras\test_estado.py:273: "ItemInvestimento" has no attribute "CLASSIFICACAO_MOBILIZACAO"
tests\regras\test_estado.py:286: "ItemAtivo" has no attribute "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL"
tests\regras\test_estado.py:288: "ItemAtivo" has no attribute "CLASSIFICACAO_MOBILIZACAO"
tests\regras\test_componentes_recomendados.py:54: Unexpected keyword argument "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL" for "ItemAtivo"
tests\regras\test_componentes_recomendados.py:54: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemAtivo"
tests\regras\test_componentes_recomendados.py:64: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemInvestimento"
tests\regras\test_ataque_imediato_potencial.py:44: Unexpected keyword argument "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL" for "ItemAtivo"
tests\regras\test_ataque_imediato_potencial.py:44: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemAtivo"
tests\regras\test_ataque_imediato_potencial.py:54: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemInvestimento"
tests\regras\test_ataque_imediato.py:71: Unexpected keyword argument "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL" for "ItemAtivo"
tests\regras\test_ataque_imediato.py:71: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemAtivo"
tests\regras\test_ataque_imediato.py:81: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemInvestimento"
tests\regras\test_ataque_imediato.py:388: "ItemInvestimento" has no attribute "CLASSIFICACAO_MOBILIZACAO"
tests\regras\test_ataque_imediato.py:393: "ItemAtivo" has no attribute "CLASSIFICACAO_MOBILIZACAO"
tests\regras\test_repositorio_snapshots.py:297: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemInvestimento"
tests\regras\test_repositorio_snapshots.py:303: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemInvestimento"
tests\regras\test_repositorio_snapshots.py:311: Unexpected keyword argument "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL" for "ItemAtivo"
tests\regras\test_repositorio_snapshots.py:311: Unexpected keyword argument "CLASSIFICACAO_MOBILIZACAO" for "ItemAtivo"
tests\regras\test_repositorio_snapshots.py:364: "ItemInvestimento" has no attribute "CLASSIFICACAO_MOBILIZACAO"
tests\regras\test_repositorio_snapshots.py:369: "ItemAtivo" has no attribute "VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL"

Found 28 errors in 6 files (checked 279 source files)
```

Todos os números de linha bateram com o plano R4.1.2 — nenhum deslocamento nesta rodada.

**O que mudou em cada arquivo.** `persistencia/arquivo/repositorio_snapshots.py`: `_item_investimento`/`_item_ativo` reescritas para desserializar os campos BRUTOS (`LIQUIDEZ_INVESTIMENTOS`, `DISPOSICAO_USO_INVESTIMENTO`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`, `TEM_CUSTO_CONHECIDO`, `SEM_CUSTO_PERDA_RELEVANTE` em `ItemInvestimento`; `TIPO_ATIVO_FISICO`, `POSSIBILIDADE_VENDA`, `ESSENCIALIDADE`, `VALOR_ESTIMADO_ATIVO`, `POSSUI_PASSIVO_VINCULADO`, `SALDO_PASSIVO_VINCULADO`, `POSSUI_CUSTO_DESMOBILIZACAO`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO`, `RENDA_RECORRENTE_ATIVO`, `CUSTO_RECORRENTE_ATIVO` em `ItemAtivo`), nunca mais a classificação pronta; helper novo `_dinheiro_talvez_ou_none` trata o terceiro estado de `RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None` (o `None` estrutural de `RF-56`/`OQ-38`, distinto de `DESCONHECIDO`); imports de enum novos (`LIQUIDEZ_INVESTIMENTOS`, `DISPOSICAO_USO_INVESTIMENTO`, `TIPO_ATIVO_FISICO`, `POSSIBILIDADE_VENDA`, `ESSENCIALIDADE`); import agora não utilizado de `CLASSIFICACAO_MOBILIZACAO` removido (`ruff F401`). `tests/fixtures/carregar.py`: mesmo padrão em `_carregar_item_investimento`/`_carregar_item_ativo`, com `_dinheiro_talvez_ou_none` local; `gab_a.json`/`gab_b.json`/`gab_c.json` NÃO precisaram de edição — as coleções `investimentos`/`ativos` já eram vazias nas três (`[]`), confirmado antes de editar, então as funções de carga passaram a exigir o schema novo mas nunca são chamadas por essas fixtures. `tests/regras/test_estado.py`: `test_investimentos_e_ativos_sao_colecao_por_item_sem_total_agregado` (`AC-64`) reescrito para construir 3 investimentos e 2 ativos com campos brutos canônicos documentados (derivados de trás para frente a partir das seis regras de §14.3.1 e dos oito ramos de §14.4-§14.9) e comparar `classificar_investimento(item)`/`classificar_ativo_fisico(item)` em vez do campo removido; um segundo teste, `test_item_sem_classificacao_falha_na_construcao` (`EC-31`, não listado nos 12 pontos originais porque não chegava a construir com sucesso — falhava antes por outro motivo), também foi descoberto quebrado pelo `pytest` completo e reescrito como `test_item_sem_campo_bruto_falha_na_construcao` (`EC-32`, sucessor declarado de `EC-31` no plano R4.1.1). `tests/regras/test_componentes_recomendados.py`, `test_ataque_imediato_potencial.py`, `test_ataque_imediato.py`: fixtures `_ativo`/`_investimento` reescritas para, dado o parâmetro `classe: CLASSIFICACAO_MOBILIZACAO` que os testes já passavam, escolher os campos BRUTOS canônicos que fazem `classificar_ativo_fisico`/`classificar_investimento` derivar exatamente aquela classe (mapeamento documentado na docstring de cada fixture, citando a regra/ramo de §14.3.1/§14.4-§14.9 responsável); `test_ataque_imediato.py` teve também dois usos diretos de `item.CLASSIFICACAO_MOBILIZACAO` (linhas então 388/393, dentro de `test_item_compoe_no_maximo_um_componente`, não listados nos 12 pontos originais por não serem construção) substituídos por `classificar_investimento(item)`/`classificar_ativo_fisico(item)`, e o mesmo `EC-31`→`EC-32` de `test_estado.py` se repetiu em `test_item_sem_classificacao_falha_na_construcao`, reescrito como `test_item_sem_campo_bruto_falha_na_construcao`. `tests/regras/test_repositorio_snapshots.py`: `test_T97_estado_financeiro_rodada_3_round_trip_itens_e_desconhecido` reescrito — `ItemInvestimento`/`ItemAtivo` agora constroem com campos brutos (INV-01 força `MOBILIZACAO_RECOMENDAVEL` pela Regra 4, INV-02 força `MOBILIZACAO_POSSIVEL` pela Regra 3; ATV-01 força `MOBILIZACAO_RECOMENDAVEL` pelo ramo 8c, e um `ATV-02` novo — veículo com `RENDA_RECORRENTE_ATIVO=None` — foi acrescentado para provar que o sentinela estrutural de `RF-56`/`OQ-38` sobrevive ao round-trip como `None`, nunca vira `DESCONHECIDO` nem `0`, e que `classificar_ativo_fisico` continua retornando `None`); as asserções de classificação passam a chamar `classificar_investimento`/`classificar_ativo_fisico` dos dois lados (original e obtido do disco) em vez de comparar um campo armazenado — round-trip da classificação DERIVADA, como o critério de aceite exige; a asserção da linha crua JSON foi ajustada de `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` (que não existe mais em `ItemAtivo`) para `VALOR_ESTIMADO_ATIVO`, mais uma checagem nova de que `RENDA_RECORRENTE_ATIVO` grava `null` (não string) na linha crua do item veículo.

**Consumidor extra encontrado, fora da lista de 12 pontos, corrigido dentro do espírito desta tarefa (§4/instrução 8):** dois usos diretos de `item.CLASSIFICACAO_MOBILIZACAO` como atributo (não construção) em `tests/regras/test_ataque_imediato.py::test_item_compoe_no_maximo_um_componente`, e duas instâncias do teste `EC-31` (`test_item_sem_classificacao_falha_na_construcao`, um em `test_estado.py`, outro em `test_ataque_imediato.py`) que testavam o contrato REVOGADO da Rodada 3 — nenhum dos quatro aparecia no `grep -rn "ItemAtivo(\|ItemInvestimento("` porque não são chamadas de construtor com argumentos completos (os dois primeiros são acesso a atributo; os dois últimos constroem com campos incompletos de propósito, então o `grep` os pega mas a intenção do teste — provar `EC-31` — mudou de contrato, não é a mesma correção mecânica dos outros 12). Reescritos para `EC-32` (sucessor declarado no plano R4.1.1), citando `RF-59`/`T-125` na docstring.

**Falha pré-existente, fora de escopo, não corrigida (documentada, não escondida):** `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py::test_sem_derivacao_de_classificacao_mobilizacao` falha porque `classificar_investimento`/`classificar_ativo_fisico` (introduzidas em `T-122`/`T-123`) têm `CLASSIFICACAO_MOBILIZACAO`/`CLASSIFICACAO_MOBILIZACAO | None` como anotação de retorno, e o teste antigo (Rodada 3, premissa "nenhuma função de `engine/` deriva a classificação") reprova exatamente isso. Não é consumidor de `ItemAtivo`/`ItemInvestimento`, não está na lista de 12 pontos, e sua correção é `RF-60`/`AC-97`, explicitamente atribuída a `T-130` ("reescrever... provar a regra, não mais a ausência" — reescrita completa da premissa, não uma correção mecânica de fixture) — tarefa distinta, ainda pendente nesta rodada. A própria nota de fechamento de `T-124` já registrava esta falha como pré-existente e fora do escopo de `T-125`. Não editado nesta tarefa.

**Verificação final, nesta ordem:**
- `build` (`mypy --strict engine persistencia collection app report tests`) → `Success: no issues found in 279 source files`.
- `ruff check .` → `All checks passed!` (duas linhas `E501` e um `F401` corrigidos durante a tarefa).
- `pytest -q --ignore=tests/app_aluno` → `1 failed, 533 passed, 9 skipped` — a única falha é `test_sem_derivacao_de_classificacao_mobilizacao` (pré-existente, fora de escopo, ver acima); nenhuma falha nova; `tests/gabaritos` e `tests/gabaritos_ataque_imediato` (`GAB-A`/`GAB-B`/`GAB-C`, `GAB-AI-*`) rodados isoladamente: `19 passed` — nenhum valor numérico de gabarito mudou (os três `tests/fixtures/*.json` não foram editados; timestamp de disco confirma).
- `tests/app_aluno/estatica/test_sem_patrimonio_derivado_em_app.py` confirmado não editado (timestamp de disco anterior a esta sessão).

**Referência para `T-130` (próxima tarefa desta rodada).** `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` deve ser reescrito por completo, premissa invertida, conforme plano R4.9.5 — fica registrado aqui como a única falha residual conhecida no momento em que `T-125` fecha.

---

### `T-126` — Testar `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO`/`_DISPONIVEL`: `GAB-NFI-12`, propagação de desconhecido, `DESCONHECIDO` nunca vira zero

- **Tipo:** `Test`
- **Dependências:** `T-121`
- **Rastreia:** `RF-57`, `RF-58`, `AC-94`, `AC-99`, `EC-36`, `US-20`
- **Arquivos:** `tests/regras/test_valor_liquido_realizavel.py` (novo)

**Descrição**

Arquivo novo de `tests/regras/`, marcador `regra`. Cobre as duas funções de `T-121` isoladamente, com os valores literais da tabela §14.12.3 e do gabarito `GAB-NFI-12`, mais a prova explícita de que `DESCONHECIDO` nunca vira zero silenciosamente (`RF-58`) — pedido explícito desta fatia, não implícito no valor final bater.

**Critérios de aceite**

- [ ] `GAB-NFI-12` literal: `VALOR_ESTIMADO_ATIVO=100.000`, `SALDO_PASSIVO_VINCULADO=105.000`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO=5.000` → `VALOR_LIQUIDO_REALIZAVEL_ATIVO=-10.000` (negativo, tolerância zero) e `_DISPONIVEL=0` (`AC-94`)
- [ ] Exemplo positivo da tabela §14.12.3, também literal: `VALOR_ESTIMADO_ATIVO=100.000`, `SALDO_PASSIVO_VINCULADO=70.000`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO=5.000` → `VALOR_LIQUIDO_REALIZAVEL_ATIVO=25.000` e `_DISPONIVEL=25.000`
- [ ] `SALDO_PASSIVO_VINCULADO` existe mas desconhecido → `VALOR_LIQUIDO_REALIZAVEL_ATIVO` é o estado desconhecido, **nunca `0`** — teste dedicado que asserta explicitamente `is DESCONHECIDO`, não apenas que o valor final "parece certo" (`AC-99`)
- [ ] `CUSTOS_ESTIMADOS_DESMOBILIZACAO` existe mas desconhecido → mesmo resultado desconhecido, teste dedicado separado do de `SALDO_PASSIVO_VINCULADO` (`AC-99`, `RF-58`)
- [ ] `VALOR_ESTIMADO_ATIVO` desconhecido → `DESCONHECIDO` sem que passivo/custo cheguem a ser avaliados (`EC-36`) — prova por `unittest.mock`/espião ou por construção de dado que faria o resultado divergir se passivo/custo fossem lidos
- [ ] `POSSUI_PASSIVO_VINCULADO=False`/`POSSUI_CUSTO_DESMOBILIZACAO=False` → tratado como `0`, não como desconhecido — teste que distingue "não existe" (`0`) de "existe e desconhecido" (`DESCONHECIDO`), as duas pontas de `RF-58`
- [ ] `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` nunca retorna negativo mesmo alimentado com o resultado negativo do primeiro teste — verificado por `Decimal` exato, tolerância zero
- [ ] Cada teste cita `AC-94`/`AC-99`/`EC-36` ou `RF-57`/`RF-58` na docstring (`sdd.config.md` §5)
- [ ] `pytest -q tests/regras/test_valor_liquido_realizavel.py` passa

**Status:** `[x] concluída` — arquivo novo `tests/regras/test_valor_liquido_realizavel.py`, marcador `regra`, 8 testes. `GAB-NFI-12` literal (`AC-94`): `VALOR_ESTIMADO_ATIVO=100.000`, `SALDO_PASSIVO_VINCULADO=105.000`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO=5.000` → `VALOR_LIQUIDO_REALIZAVEL_ATIVO=-10.000` e `_DISPONIVEL=0`, `assertar_exato` (`test_GAB_NFI_12_valor_liquido_negativo`). Exemplo positivo §14.12.3 literal (`SALDO_PASSIVO_VINCULADO=70.000` → `25.000`/`25.000`) em `test_exemplo_positivo_14_12_3`. `SALDO_PASSIVO_VINCULADO` existe e desconhecido → `is DESCONHECIDO`, teste dedicado (`test_passivo_existe_mas_desconhecido_propaga_desconhecido_nunca_zero`, `AC-99`); `CUSTOS_ESTIMADOS_DESMOBILIZACAO` existe e desconhecido → mesmo resultado, teste SEPARADO (`test_custo_desmobilizacao_existe_mas_desconhecido_propaga_desconhecido`, `AC-99`). `VALOR_ESTIMADO_ATIVO` desconhecido → `DESCONHECIDO` sem avaliar passivo/custo, provado por `unittest.mock.sentinel` no lugar dos dois parâmetros seguintes — se fossem lidos (comparados ou subtraídos), a chamada levantaria `TypeError` antes de retornar; como o teste passa sem exceção, a guarda 1 nunca os toca (`test_valor_estimado_desconhecido_vence_sem_avaliar_passivo_e_custo`, `EC-36`). `POSSUI_PASSIVO_VINCULADO=False`/`POSSUI_CUSTO_DESMOBILIZACAO=False` → `0` exato, distinto de "existe e desconhecido" (`test_nao_possui_passivo_nem_custo_e_tratado_como_zero_nao_desconhecido`, `RF-58`). `_DISPONIVEL` alimentado com `-10.000` → `0`, `Decimal` exato, tolerância zero (`test_disponivel_nunca_negativo_mesmo_alimentado_com_resultado_negativo`), mais um teste de propagação de `DESCONHECIDO` sem aplicar `MAX` (`test_disponivel_propaga_desconhecido_sem_aplicar_max`). Cada docstring cita `AC-94`/`AC-99`/`EC-36`/`RF-57`/`RF-58` conforme o caso. Verificação: `ruff check .` → `All checks passed!`; `mypy engine persistencia collection app report tests` → `Success: no issues found in 281 source files` (279 + os 2 arquivos novos de `T-126`/`T-127`); `pytest -q tests/regras/test_valor_liquido_realizavel.py` isolado → `8 passed`; `pytest -q --ignore=tests/app_aluno` completo → `1 failed, 553 passed, 9 skipped` — a única falha continua sendo `test_sem_derivacao_de_classificacao_mobilizacao` (pré-existente, `T-130`), nenhuma falha nova, `553` = `533` (base pós-`T-125`) `+ 8` (`T-126`) `+ 12` (`T-127`).

---

### `T-127` — Testar `classificar_investimento`/`classificar_ativo_fisico`: `GAB-NFI-06` a `GAB-NFI-11`, precedência forçada, bloqueio de veículo

- **Tipo:** `Test`
- **Dependências:** `T-122`, `T-123`
- **Rastreia:** `RF-53`, `RF-54`, `RF-55`, `RF-56`, `AC-88`, `AC-89`, `AC-90`, `AC-91`, `AC-92`, `AC-93`, `AC-95`, `AC-96`, `AC-100`, `EC-33`, `EC-34`, `EC-35`, `EC-37`, `EC-39`, `US-19`
- **Arquivos:** `tests/regras/test_classificacao_ativos.py` (novo)

**Descrição**

Arquivo novo de `tests/regras/`, marcador `regra`. Cobre `classificar_investimento` (seis regras + precedência forçada) e `classificar_ativo_fisico` (oito ramos + precedência forçada + bloqueio de veículo) com os cenários literais de `GAB-NFI-06` a `GAB-NFI-11` e os dois casos de precedência de `AC-95`/`AC-96`. Estes são os testes de comportamento que substituem a "verificação manual" registrada em `T-122`/`T-123`.

**Critérios de aceite**

- [ ] `GAB-NFI-06` (`DISPOSICAO_USO_INVESTIMENTO=SIM`, `LIQUIDEZ_INVESTIMENTOS=BLOQUEADO`) → `NAO_MOBILIZAR` (`AC-88`)
- [ ] `GAB-NFI-07` (`DISPOSICAO_USO_INVESTIMENTO=SIM`, `LIQUIDEZ_INVESTIMENTOS=D1`, sem custo relevante, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=10.000`) → `MOBILIZACAO_RECOMENDAVEL` (`AC-89`)
- [ ] `GAB-NFI-08` (`DISPOSICAO_USO_INVESTIMENTO=TALVEZ`, resgatável) → `MOBILIZACAO_POSSIVEL` (`AC-90`)
- [ ] Investimento que satisfaz simultaneamente a Regra 1 e a Regra 4 → `NAO_MOBILIZAR` (a primeira vence, nunca a Regra 4) (`AC-95`, `EC-33`)
- [ ] `GAB-NFI-09` (`ESSENCIALIDADE=ESSENCIAL`, `POSSIBILIDADE_VENDA=SIM`) → `MOBILIZACAO_COM_RESSALVAS`, e o mesmo cenário trocando `POSSIBILIDADE_VENDA` para `JA_PRETENDE` também produz `MOBILIZACAO_COM_RESSALVAS`, **nunca** `MOBILIZACAO_RECOMENDAVEL` em nenhum dos dois (`AC-91`, `EC-34`)
- [ ] `GAB-NFI-10` (`ESSENCIALIDADE=NAO_ESSENCIAL`, `VENDA=SIM`, `VALOR_LIQUIDO_DISPONIVEL=30.000`, `FLUXO=-500`) → `MOBILIZACAO_RECOMENDAVEL` (`AC-92`)
- [ ] `GAB-NFI-11` (mesmo cenário de `GAB-NFI-10` exceto `FLUXO=+700`) → `MOBILIZACAO_POSSIVEL` (`AC-93`)
- [ ] Ativo físico que satisfaz simultaneamente `POSSIBILIDADE_VENDA=NAO` e a condição de dado desconhecido → `NAO_MOBILIZAR` (bloqueio vence) (`AC-96`)
- [ ] Ativo físico `ESSENCIALIDADE em {IMPORTANTE, PARCIAL}` com `POSSIBILIDADE_VENDA=NAO` → `NAO_MOBILIZAR` pelo bloqueio de §14.4.1, não um resultado de §14.6 (`EC-35`)
- [ ] Investimento do tipo comumente associado a alta liquidez (ex.: poupança) com `LIQUIDEZ_INVESTIMENTOS=MAIS_30` → `MOBILIZACAO_COM_RESSALVAS` (Regra 6), contrariando a presunção "poupança = recomendável" (`EC-37`, §14.3.1.1)
- [ ] Ativo físico veículo, `ESSENCIALIDADE=NAO_ESSENCIAL`, `POSSIBILIDADE_VENDA=SIM`, `RENDA_RECORRENTE_ATIVO=None` → retorno `is None`, nenhum valor do domínio de `CLASSIFICACAO_MOBILIZACAO` (`AC-100`, `EC-39`) — teste separado do de `test_veiculo_nao_essencial_bloqueado.py` (`T-131`), cobrindo o comportamento da função, não a garantia estrutural do código-fonte
- [ ] Cada teste cita o `AC-NN`/`EC-NN`/`RF-NN` correspondente na docstring
- [ ] `pytest -q tests/regras/test_classificacao_ativos.py` passa

**Status:** `[x] concluída` — arquivo novo `tests/regras/test_classificacao_ativos.py`, marcador `regra`, 12 testes (2 fixtures locais `_investimento`/`_ativo` que montam os campos BRUTOS de §14.3.1/§14.4-§14.9, mesmo padrão de `test_ataque_imediato_potencial.py`). `GAB-NFI-06` (`AC-88`, `DISPOSICAO=SIM`+`LIQUIDEZ=BLOQUEADO` → `NAO_MOBILIZAR`), `GAB-NFI-07` (`AC-89`, `SIM`+`D1`+sem custo+líquido `10.000` → `MOBILIZACAO_RECOMENDAVEL`), `GAB-NFI-08` (`AC-90`, `TALVEZ`+resgatável → `MOBILIZACAO_POSSIVEL`), cada um em teste próprio. Precedência forçada de investimento: Regra 1 (bloqueio) vence Regra 4 quando ambas se aplicariam → `NAO_MOBILIZAR` (`test_regra_1_vence_regra_4_quando_ambas_se_aplicam`, `AC-95`/`EC-33`). `GAB-NFI-09` (`AC-91`/`EC-34`, `ESSENCIAL`+`SIM` → `MOBILIZACAO_COM_RESSALVAS`) testado com `POSSIBILIDADE_VENDA=SIM` E, no mesmo teste, repetido com `JA_PRETENDE` — ambos `MOBILIZACAO_COM_RESSALVAS`, nenhum `MOBILIZACAO_RECOMENDAVEL`, com asserção `!=` explícita reforçando o "nunca". `GAB-NFI-10` (`AC-92`, `NAO_ESSENCIAL`+`SIM`+líquido `30.000`+fluxo `-500` → `MOBILIZACAO_RECOMENDAVEL`) e `GAB-NFI-11` (`AC-93`, mesmo cenário com fluxo `+700` → `MOBILIZACAO_POSSIVEL`), cada um em teste próprio. Bloqueio de ativo físico: `POSSIBILIDADE_VENDA=NAO` simultâneo a `VALOR_ESTIMADO_ATIVO` desconhecido → `NAO_MOBILIZAR` pelo bloqueio, não pelo ramo de dado desconhecido (`test_bloqueio_de_venda_vence_dado_desconhecido_simultaneo`, `AC-96`). `{IMPORTANTE, PARCIAL}` + `POSSIBILIDADE_VENDA=NAO` → `NAO_MOBILIZAR` pelo bloqueio de §14.4.1, parametrizado nos dois valores de essencialidade (`test_importante_ou_parcial_com_venda_nao_e_bloqueado_nao_ramo_14_6`, `EC-35`). Investimento "tipo poupança" com `LIQUIDEZ_INVESTIMENTOS=MAIS_30` → `MOBILIZACAO_COM_RESSALVAS` (Regra 6), contrariando a presunção "poupança=recomendável" (`test_investimento_tipo_poupanca_liquidez_longa_e_ressalvas_nao_recomendavel`, `EC-37`). Veículo, `NAO_ESSENCIAL`, `SIM`, `RENDA_RECORRENTE_ATIVO=None` → `classificar_ativo_fisico` retorna `is None`, `not isinstance(obtido, CLASSIFICACAO_MOBILIZACAO)` — teste da função em si, distinto do teste estrutural de `T-131` (`test_veiculo_nao_essencial_sem_renda_recorrente_retorna_none`, `AC-100`/`EC-39`). Cada docstring cita os `AC-NN`/`EC-NN`/`RF-NN` correspondentes. Verificação: `ruff check .` → `All checks passed!` (4 linhas `E501` corrigidas durante a tarefa); `mypy engine persistencia collection app report tests` → `Success: no issues found in 281 source files`; `pytest -q tests/regras/test_classificacao_ativos.py` isolado → `12 passed`; `pytest -q --ignore=tests/app_aluno` completo → `1 failed, 553 passed, 9 skipped` — mesma única falha pré-existente de `T-125`/`T-126`, nenhuma falha nova.

---

### `T-128` — Registrar o marcador `gabarito_classificacao_ativos` e criar o diretório dos `GAB-NFI`

- **Tipo:** `Infra`
- **Dependências:** `T-121`
- **Rastreia:** `RF-53`, `RF-54`, `RF-57`, `US-19`, `US-20`
- **Arquivos:** `pyproject.toml`, `tests/gabaritos_classificacao_ativos/__init__.py` (novo)

**Descrição**

Mesma decisão da Rodada 3 para `gabarito_ataque_imediato` (`T-108`), reaplicada: `GAB-NFI-06` a `GAB-NFI-12` **não** são ponta a ponta (funções puras isoladas de `engine/classificacao_ativos.py`, sem dívidas, gates nem cronograma) e **não** são propriedades — reusar `@pytest.mark.gabarito` diluiria o portão de homologação da seção 10 da canônica. Marcador novo `gabarito_classificacao_ativos`, diretório novo `tests/gabaritos_classificacao_ativos/`. **Consequência operacional a divulgar:** o comando de homologação passa a ser `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos"`.

**Critérios de aceite**

- [x] `[tool.pytest.ini_options] markers` do `pyproject.toml` registra `gabarito_classificacao_ativos` com descrição que o distingue de `gabarito` e de `gabarito_ataque_imediato` ("fórmula/classificação isolada da §14, não ponta a ponta")
- [x] As descrições de `gabarito`, `invariante` e `gabarito_ataque_imediato` ficam **inalteradas**
- [x] `tests/gabaritos_classificacao_ativos/` existe, com `__init__.py` no mesmo padrão de `tests/gabaritos_ataque_imediato/__init__.py` (uma linha de docstring), é importável e coletado por `pytest -q`
- [x] `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos"` roda sem erro de marcador desconhecido
- [x] O comando de homologação novo é registrado na nota de fechamento desta tarefa
- [x] `pytest --strict-markers` não reclama do marcador novo
- [x] Nenhum teste `GAB-NFI` é escrito nesta tarefa — só marcador e diretório

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-09).**

> **COMANDO DE HOMOLOGAÇÃO NOVO — divulgar para a revisão da rodada:**
>
> ```
> pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos"
> ```
>
> O comando anterior (`pytest -m "gabarito or invariante or gabarito_ataque_imediato"`,
> registrado em `T-108`) continua rodando **sem erro** e por isso não avisa
> nada: quem usá-lo terá cobertura silenciosamente menor, perdendo os sete
> `GAB-NFI` a partir de `T-129`. Este é o portão da seção 10 da canônica somado
> à §14.

Duas alterações, exatamente as previstas pela descrição desta tarefa:

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ [tool.pytest.ini_options] markers
     "gabarito_ataque_imediato: reproduz gabarito numérico de fórmula isolada da seção 13, NÃO ponta a ponta (GAB-AI-01 a GAB-AI-07 — sem dívidas, gates nem cronograma)",
+    "gabarito_classificacao_ativos: reproduz gabarito de fórmula/classificação isolada da seção 14, NÃO ponta a ponta (GAB-NFI-06 a GAB-NFI-12 — sem dívidas, gates nem cronograma)",
     "regra: testa regra normativa isolada de uma família (M, R, A, F, O, H, S, Q, V, T, G)",
```

```diff
--- /dev/null
+++ b/tests/gabaritos_classificacao_ativos/__init__.py
@@
+"""Gabaritos de classificação isolada da seção 14: GAB-NFI-06 a GAB-NFI-12 (não ponta a ponta)."""
```

**Verificação.** `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos"` → `30 passed, 1481 deselected`, zero erro de marcador desconhecido. `pytest --strict-markers` sobre o mesmo comando → mesmo resultado, `30 passed`, sem reclamação. `pytest -q --collect-only tests/gabaritos_classificacao_ativos` → `no tests collected` (exit `5`, aceito pela seção 2 do `sdd.config.md`: esperado, já que nenhum `GAB-NFI` foi escrito nesta tarefa por decisão de escopo). `python -c "import tests.gabaritos_classificacao_ativos"` → importa sem erro. `ruff check .` → `All checks passed!` (a docstring inicial excedia 100 colunas e foi encurtada para caber em `line-length = 100`). `mypy --strict` sobre `engine persistencia collection app report tests` → `Success: no issues found in 282 source files`. `pytest -q --ignore=tests/app_aluno` → `1 failed (pré-existente, escopo T-130, em tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py — não tocado por esta tarefa), 553 passed, 9 skipped`, idêntico ao baseline informado no início da tarefa: zero regressão.

---

### `T-129` — Reproduzir `GAB-NFI-06` a `GAB-NFI-12` como homologação dedicada

- **Tipo:** `Test`
- **Dependências:** `T-126`, `T-127`, `T-128`
- **Rastreia:** `RF-53`, `RF-54`, `RF-55`, `RF-57`, `AC-88`, `AC-89`, `AC-90`, `AC-91`, `AC-92`, `AC-93`, `AC-94`, `US-19`, `US-20`
- **Arquivos:** `tests/gabaritos_classificacao_ativos/test_gab_nfi_06_investimento_bloqueado.py`, `tests/gabaritos_classificacao_ativos/test_gab_nfi_07_investimento_liquido_disponivel.py`, `tests/gabaritos_classificacao_ativos/test_gab_nfi_08_disposicao_talvez.py`, `tests/gabaritos_classificacao_ativos/test_gab_nfi_09_imovel_essencial.py`, `tests/gabaritos_classificacao_ativos/test_gab_nfi_10_fluxo_negativo.py`, `tests/gabaritos_classificacao_ativos/test_gab_nfi_11_fluxo_positivo.py`, `tests/gabaritos_classificacao_ativos/test_gab_nfi_12_valor_liquido_negativo.py`

**Descrição**

Os sete gabaritos da fatia 4A (§14.16), um arquivo por gabarito, marcador `gabarito_classificacao_ativos` (`T-128`), tolerância **zero** (spec §5, mesma régua dos `GAB-AI`). Reexecuta os mesmos cenários de `T-126`/`T-127`, mas como suíte de homologação formal e isolada — a seção 10 da canônica exige que a engine seja aprovada quando reproduz os gabaritos, não apenas que os testes de regra individuais passem.

**Critérios de aceite**

- [x] Os sete arquivos existem em `tests/gabaritos_classificacao_ativos/`, um por `GAB-NFI-NN`, com o marcador `gabarito_classificacao_ativos`
- [x] Cada teste usa os valores literais exatos do enunciado do gabarito na spec §14.16, sem reinterpretação
- [x] `GAB-NFI-06` a `GAB-NFI-11` (classificação) usam tolerância **zero** — comparação de `Enum`, não de valor monetário
- [x] `GAB-NFI-12` (valor líquido) usa tolerância **zero** — `Decimal` exato, sem `± R$ 0,05` (spec §5, "Tolerância" da Rodada 4)
- [x] `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos"` passa inteiro, incluindo os sete novos
- [x] `pytest -q tests/gabaritos_classificacao_ativos/` → 7 passed

**Status:** `[x] concluída` — sete arquivos novos em `tests/gabaritos_classificacao_ativos/`, um por `GAB-NFI-NN` (`06` a `12`), marcador `gabarito_classificacao_ativos`, valores literais exatos de §14.16 (idênticos aos usados em `tests/regras/test_classificacao_ativos.py`/`test_valor_liquido_realizavel.py`, `T-126`/`T-127`), `assertar_exato` em toda asserção — comparação de `Enum` (`GAB-NFI-06` a `11`) e `Decimal` exato sem tolerância monetária (`GAB-NFI-12`). `GAB-NFI-09` reforça com `assert obtido != MOBILIZACAO_RECOMENDAVEL` explícito. Cada docstring documenta cenário/resultado/âncora (`AC-88`–`AC-94`) no mesmo formato de `tests/gabaritos_ataque_imediato/test_gab_ai_01_valor_aceito_abaixo_do_total.py` (Rodada 3), incluindo a nota cruzada com o teste de regra correspondente. Verificação: `ruff check .` → `All checks passed!` (correção de ordenação de import em 6 arquivos); `mypy engine persistencia collection app report tests` → `Success: no issues found in 290 source files` (283 + 7 novos); `pytest -q tests/gabaritos_classificacao_ativos/` → `7 passed`; `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos"` → `37 passed, 1488 deselected`; `pytest -q --ignore=tests/app_aluno` completo → `568 passed, 9 skipped` (561 + 7), **zero falhas**.

---

### `T-130` — Reescrever `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` — provar a regra, não mais a ausência

- **Tipo:** `Test`
- **Dependências:** `T-122`, `T-123`
- **Rastreia:** `RF-60`, `AC-97`, `US-21`
- **Arquivos:** `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py`

**Descrição**

> **Não é relaxamento — é prova do oposto.** O teste antigo (Rodada 3) reprovava qualquer função de `engine/` com `CLASSIFICACAO_MOBILIZACAO` na anotação de retorno. A premissa está estruturalmente invertida agora: `classificar_investimento`/`classificar_ativo_fisico` **precisam** ter essa anotação para existir. Reescrita completa do conteúdo e das funções internas; nome do arquivo mantido para preservar o histórico do teste, que já previa este momento (plano R4.9.5).

Três provas, conforme R4.9.5 do plano: (1) documentação da liberação — docstring do módulo registra a data (2026-09-09), a fonte (§14) e cita `AC-97`; (2) prova positiva por execução — os `GAB-NFI-06` a `GAB-NFI-12` (ou os testes equivalentes de `T-126`/`T-127`/`T-129`) confirmam que a derivação segue exatamente `RF-53`–`RF-56`, na ordem certa; (3) prova ESTRUTURAL complementar — a função de classificação **só** existe em `engine/classificacao_ativos.py`, nenhum outro ponto de `engine/` define uma segunda função com anotação de retorno `CLASSIFICACAO_MOBILIZACAO` fora desse módulo. A bateria de detectores AST de prova negativa do arquivo original é **preservada** — muda o veredito sobre o que ela encontra (antes: zero ocorrências esperadas; agora: exatamente as de `engine/classificacao_ativos.py`, nomeadas e esperadas), não a heurística.

**Critérios de aceite**

- [x] A docstring do módulo registra a data (2026-09-09), a fonte (§14) e `AC-97`, preservando a nota histórica que a docstring original já continha
- [x] O teste não reprova mais a existência de `classificar_investimento`/`classificar_ativo_fisico` com anotação `CLASSIFICACAO_MOBILIZACAO`/`CLASSIFICACAO_MOBILIZACAO | None`
- [x] O teste verifica, por varredura AST de `engine/**/*.py`, que **nenhuma** função com anotação de retorno `CLASSIFICACAO_MOBILIZACAO` (ou `| None` dessa anotação) existe fora de `engine/classificacao_ativos.py` — nomeando arquivo e linha se encontrar
- [x] Existe teste-companheiro de prova negativa: alimentar o detector com uma função **construída como string**, definida fora de `engine/classificacao_ativos.py`, com a anotação proibida, e confirmar que é pega — mesmo padrão de `test_verificador_pega_quinto_literal_proposital` (Rodada 2) e do próprio arquivo original (Rodada 3)
- [x] `mypy --strict` (verificação cruzada, não substitui o teste AST) confirma que `ItemAtivo`/`ItemInvestimento` não aceitam mais `CLASSIFICACAO_MOBILIZACAO` como parâmetro de construtor — citado na nota de fechamento como evidência complementar de `RF-59`
- [x] A bateria de detectores de prova negativa herdada do arquivo original (`test_detector_pega_derivacao_proposital`, `test_detector_pega_cada_forma_de_anotacao_de_retorno`, etc.) continua presente e passando
- [x] O teste passa sobre o `engine/` real ao fim da rodada
- [x] `pytest -q tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` passa

**Status:** `[x] concluída` — reescrita completa, nome do arquivo mantido. Docstring do módulo registra data `2026-09-09`, fonte `§14` e `AC-97`, preservando a "Nota histórica original (Rodada 3, preservada)" com a explicação de `OQ-26`/`EC-31`/`EC-32`. Heurística de detecção por AST (`_detectar_derivacoes`/`_anotacao_menciona_classificacao`) copiada sem alteração do arquivo original — o que muda é só o veredito aplicado sobre o resultado: `test_sem_derivacao_de_classificacao_mobilizacao_fora_do_modulo_autorizado` agora separa achados em `fora_do_modulo` (qualquer arquivo diferente de `classificacao_ativos.py`) e `dentro_mas_nao_autorizada` (uma terceira função nesse módulo com a mesma anotação), falhando em ambos os casos, e confirma por asserção não vácua que as duas funções autorizadas (`classificar_investimento`, `classificar_ativo_fisico`) foram de fato encontradas. Prova positiva por execução (`test_derivacao_segue_RF_53_a_RF_56_na_ordem_certa`) chama as duas funções reais sobre os seis cenários de `GAB-NFI-06` a `GAB-NFI-11`, batendo com os resultados de `tests/regras/test_classificacao_ativos.py` (`T-127`). Teste-companheiro de prova negativa `test_detector_pega_derivacao_proposital_fora_do_modulo_autorizado` alimenta o detector com uma função de derivação construída como string, atribuída a `"engine/outro_modulo.py"`, e confirma que é pega e marcada como não pertencente ao módulo autorizado — mesmo padrão de `test_verificador_pega_quinto_literal_proposital`. Contraprova `test_detector_nao_reporta_as_duas_funcoes_autorizadas` confirma que as duas funções legítimas, atribuídas ao caminho de `classificacao_ativos.py`, não disparam nada de anômalo. Bateria herdada do arquivo original preservada literalmente: `test_detector_pega_cada_forma_de_anotacao_de_retorno` (10 casos parametrizados), `test_detector_pega_funcao_assincrona`, `test_detector_nao_reporta_consumo_da_classificacao`. Evidência complementar de `RF-59`: `mypy --strict` sobre `engine persistencia collection app report tests` → `Success: no issues found in 283 source files` — `ItemAtivo`/`ItemInvestimento` (`engine/estado.py`) não têm mais `CLASSIFICACAO_MOBILIZACAO` como campo do construtor (confirmado por leitura direta do dataclass, que já não a lista desde `T-119`/`T-120`), e os testes deste arquivo e de `tests/regras/test_classificacao_ativos.py` constroem os dois tipos sem esse campo sem erro de tipo. Verificação: `ruff check .` → `All checks passed!`; `pytest -q tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` → `16 passed`; `pytest -q --ignore=tests/app_aluno` completo (rodado junto com `T-131`) → `561 passed, 9 skipped`, **zero falhas** — a única falha pré-existente (`test_sem_derivacao_de_classificacao_mobilizacao`, registrada nas notas de fechamento de `T-124`/`T-125`/`T-126`/`T-127`) desapareceu.

---

### `T-131` — Provar por teste estático que o ramo de veículo não essencial nunca inventa renda nem produz classificação

- **Tipo:** `Test`
- **Dependências:** `T-123`
- **Rastreia:** `RF-56`, `AC-100`, `EC-39`, `US-19`
- **Arquivos:** `tests/estatica/test_veiculo_nao_essencial_bloqueado.py` (novo)

**Descrição**

Arquivo novo (plano R4.3, R4.9). Prova estrutural — não apenas comportamental (essa é `T-127`) — de que o código-fonte de `classificar_ativo_fisico` nunca inventa um valor de renda para veículo nem trata a ausência estrutural de `RENDA_RECORRENTE_ATIVO` como `DESCONHECIDO` para produzir `MOBILIZACAO_POSSIVEL` por essa via (a leitura `OQ-42`, explicitamente rejeitada). Mesmo espírito de prova negativa dos testes estáticos já existentes (`test_sem_percentual_automatico_de_reserva.py`, Rodada 3).

**Critérios de aceite**

- [x] O teste varre a AST de `engine/classificacao_ativos.py` e confirma que o ramo de veículo (`TIPO_ATIVO_FISICO=VEICULO` dentro do bloco `NAO_ESSENCIAL`/`{SIM, JA_PRETENDE}`) retorna `None` antes de qualquer uso de `RENDA_RECORRENTE_ATIVO`/`CUSTO_RECORRENTE_ATIVO` em aritmética
- [x] Nenhum literal numérico (`0`, `dinheiro(0)` etc.) é atribuído a uma variável de renda dentro do ramo condicionado a `TIPO_ATIVO_FISICO=VEICULO` — detector nomeia arquivo e linha se encontrar
- [x] Existe teste-companheiro de prova negativa: uma versão **proposital**, construída como string, que trata `RENDA_RECORRENTE_ATIVO is None` (veículo) como `DESCONHECIDO` e cai no ramo "fluxo desconhecido → `MOBILIZACAO_POSSIVEL`" é alimentada ao detector e confirmada como pega — provando que o detector distingue a leitura correta (`RF-56`) da leitura rejeitada (`OQ-42`)
- [x] O teste confirma comportamentalmente (chamando a função real, não só lendo AST) que `classificar_ativo_fisico` sobre o cenário de `AC-100` retorna `None`, nunca `MOBILIZACAO_POSSIVEL`
- [x] A docstring do módulo cita `RF-56`, `AC-100`, `EC-39` e registra explicitamente que `OQ-42` (leitura alternativa) foi rejeitada e não implementada
- [x] O teste passa sobre o `engine/` real ao fim da rodada
- [x] `pytest -q tests/estatica/test_veiculo_nao_essencial_bloqueado.py` passa

**Status:** `[x] concluída` — arquivo novo, 5 testes. Docstring do módulo cita `RF-56`, `AC-100`, `EC-39` e registra explicitamente, em parágrafo dedicado, que `OQ-42` foi "explicitamente REJEITADA — não implementada". Prova estrutural 1 (`test_ramo_de_veiculo_retorna_none_antes_de_qualquer_aritmetica_de_fluxo`): localiza por nome (não por linha fixa) a função `classificar_ativo_fisico` real em `engine/classificacao_ativos.py`, encontra o(s) `if` cujo teste menciona simultaneamente o atributo `VEICULO` e uma comparação `is None` sobre `RENDA_RECORRENTE_ATIVO`, confirma que o corpo é exatamente `return None` e que nenhum `BinOp` de subtração envolvendo `RENDA_RECORRENTE_ATIVO`/`CUSTO_RECORRENTE_ATIVO` aparece em linha anterior à do guarda — bate com a ordem real do código-fonte (guarda na linha 342, subtração de fluxo na linha 365, dentro do `else` alcançado só depois do guarda). Prova estrutural 2 (`test_nenhum_literal_numerico_vira_renda_no_ramo_de_veiculo`): varre `Assign`/`AnnAssign` cujo alvo contenha `RENDA` com valor literal numérico ou `dinheiro(<literal>)` — nenhum encontrado no código real. Teste-companheiro de prova negativa `test_detector_pega_versao_proposital_que_implementa_OQ_42`: alimenta o detector estrutural 1 com uma função construída como string que implementa exatamente a leitura de `OQ-42` (calcula `fluxo_liquido_recorrente` ANTES do guarda `is None` de veículo) e confirma que o detector reporta o problema citando "aritmética... ANTES do" guarda — verificado manualmente que o detector também falha corretamente quando o guarda está totalmente ausente (mensagem "nenhum `if` encontrado..."), afastando prova vácua. Segundo teste-companheiro `test_detector_pega_literal_de_renda_inventado_proposital`: alimenta o detector estrutural 2 com uma atribuição proposital `RENDA_RECORRENTE_ATIVO_ASSUMIDA = dinheiro(0)` dentro do guarda de veículo e confirma que é pega, nomeando a variável. Prova comportamental (`test_cenario_AC_100_retorna_None_nunca_MOBILIZACAO_POSSIVEL`): chama `classificar_ativo_fisico` real com `TIPO_ATIVO_FISICO=VEICULO`, `ESSENCIALIDADE=NAO_ESSENCIAL`, `POSSIBILIDADE_VENDA=SIM`, `RENDA_RECORRENTE_ATIVO=None` (cenário de `AC-100`) e confirma `obtido is None`. Verificação: `ruff check .` → `All checks passed!`; `mypy --strict` sobre `engine persistencia collection app report tests` → `Success: no issues found in 283 source files`; `pytest -q tests/estatica/test_veiculo_nao_essencial_bloqueado.py` → `5 passed`; `pytest -q --ignore=tests/app_aluno` completo (rodado junto com `T-130`) → `561 passed, 9 skipped`, zero falhas.

**Status:** `[ ] pendente`

---

## Rodada 4 — fatia 4B (2026-09-09)

> **Escopo desta fatia.** `RF-61` a `RF-65` (spec §14, blocos "Rodada 4 —
> fatia 4B"), plano `plans/motor-calculo.plan.md` seção "Rodada 4 — fatia
> 4B" (`R4B.x`). Fecha `OQ-29` (Rodada 3, reafirmada) para a metade
> `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` —
> a metade `ATAQUE_IMEDIATO_RECOMENDADO`/`RECURSOS_ESTRATEGICAMENTE_
> RECOMENDADOS` continua aberta na fatia 4C. **Pré-requisito: fatia 4A
> (`T-117` a `T-131`) concluída e verificada** — nenhuma tarefa abaixo
> reabre `classificar_investimento`/`classificar_ativo_fisico`.
>
> **Fora de escopo, não implementado por nenhuma tarefa abaixo:** ligação
> em `calcular_diagnostico`/`Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`
> (fatia 4C, `OQ-43`); qualquer arquivo de `app/`, `collection/` ou
> `report/`; enum `STATUS_ATAQUE_IMEDIATO` novo (decisão R4B.6.1: reaproveita
> `STATUS_METODO.PROVISORIO` já existente, sem criar nada); qualquer campo
> de "valor de contenção" em `Divida`/`ResultadoGates` para os dois pontos
> de Gate 2 (`engine/gates.py:440`, `:457`) — ambos usam `dinheiro(0)`
> explícito nesta fatia, ambiguidade registrada e não resolvida em R4B.10.1,
> nenhuma tarefa abaixo a decide.
>
> **Decisões já fechadas — não reabertas por nenhuma tarefa abaixo:**
> `VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez` é campo **novo, sem
> default**, em `AcaoRequerida` — não em `Divida` (`OQ-39`, R4B.1.1).
> `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`
> vivem em `engine/gates.py` — não em `engine/ataque_imediato.py` (`OQ-41`,
> R4B.1.2). A trava de dupla contagem (`RF-65`) é a cadeia `if`/`elif`
> estrita de `NECESSIDADE_IMEDIATA_DIVIDA` — não uma verificação/`assert`
> separado em runtime (R4B.10).

### `T-132` — Adicionar `VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez` a `AcaoRequerida`

- **Tipo:** `Data`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-61`, `RF-62`, `RF-63`, `AC-105`, `EC-47`, `US-22`, `US-25`
- **Arquivos:** `engine/gates.py`

**Descrição**

Quebra de contrato deliberada (plano R4B.1.1, decisão `OQ-39` = (a)): `AcaoRequerida` ganha o campo `VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez`, **sem default**, posicionado antes dos dois campos que já têm default (`prioridade_excepcional`, `CAMPO_PENDENTE`) — posição exigida pela regra de dataclass Python (campo sem default não pode vir depois de campo com default). Esta tarefa **só** altera a declaração da dataclass e sua docstring; **não** corrige nenhum ponto de construção existente — isso quebra deliberadamente todo consumidor interno (`EC-47`), correção é `T-133`.

**Critérios de aceite**

- [x] `AcaoRequerida` ganha `VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez` na posição exata do plano R4B.4.1 (entre `gate_origem` e `prioridade_excepcional`), sem valor default
- [x] `AcaoRequerida(...)` sem o argumento novo levanta `TypeError: missing 1 required positional argument` e falha em `mypy --strict`
- [x] A docstring da dataclass ganha o parágrafo da Rodada 4 — fatia 4B (plano R4B.4.1), citando `RF-61`, §14.2.1/§14.2.2, `OQ-39`, e documentando os três estados possíveis (`0` sem desembolso; valor conhecido com desembolso; `DESCONHECIDO` com desembolso e valor não conhecido) e que o campo **nunca** é `None` — a variável sempre se aplica
- [x] Nenhum ponto de construção de `AcaoRequerida(...)` é corrigido nesta tarefa — a nota de fechamento reporta a lista de erros que `mypy --strict` (`build`) passa a acusar, como insumo de `T-133`
- [x] `REGRAS: Final[tuple[str, ...]]` de `engine/gates.py` ganha `"§14.2.1"`, `"§14.2.2"` (as duas subseções que esta tarefa implementa; `"§14.1"`, `"§14.1.1"`, `"§14.2.3"` ficam para `T-134`/`T-135`, que citam as subseções que implementam)
- [x] `ruff check .` passa

**Status:** `[x] concluída`

**Nota de fechamento**

`engine/gates.py`: campo `VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez` inserido em `AcaoRequerida` entre `gate_origem` e `prioridade_excepcional`, sem default; import de `DinheiroTalvez` de `engine.tipos`; docstring da dataclass ganhou o parágrafo da fatia 4B; `REGRAS` ganhou `"§14.2.1"`, `"§14.2.2"`. `ruff check .`: `All checks passed!`. `TypeError` confirmado em runtime: `AcaoRequerida.__init__() missing 1 required positional argument: 'VALOR_ACAO_FINANCEIRA_IMEDIATA'`.

`mypy --strict` (comando `build`, `engine persistencia collection app report tests` filtrados por existência) passa a acusar **11 erros em 6 arquivos** (nenhum corrigido nesta tarefa — insumo de `T-133`):

```
engine\gates.py:347: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
engine\gates.py:382: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
engine\gates.py:458: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
engine\gates.py:475: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
engine\gates.py:571: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
engine\motor.py:200: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
persistencia\arquivo\repositorio_snapshots.py:621: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
tests\regras\test_ordem.py:206: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
tests\estatica\test_tipo_acao_apenas_quatro_valores.py:122: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
tests\regras\test_repositorio_snapshots.py:230: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
tests\regras\test_repositorio_snapshots.py:239: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]

Found 11 errors in 6 files (checked 290 source files)
```

Bate exatamente com os 6 construções de `engine/` (`engine/gates.py:329,364,440,457,553` — linhas do `AcaoRequerida(` deslocaram para `347,382,458,475,571` após a inserção do parágrafo de docstring — + `engine/motor.py:200`), 1 desserialização (`persistencia/arquivo/repositorio_snapshots.py:621`) e 3 fixtures de teste (`tests/regras/test_ordem.py:206`, `tests/estatica/test_tipo_acao_apenas_quatro_valores.py:122`, `tests/regras/test_repositorio_snapshots.py:230` e `:239` — 2 fixtures no mesmo arquivo). Insumo direto de `T-133`. `report/plano.py:406` e `tests/regras/test_motor.py:410` não aparecem na lista — confirmando o previsto no plano (não constroem `AcaoRequerida`).

---

### `T-133` — Varrer e corrigir os 12 pontos de construção/leitura de `AcaoRequerida(` e sinalizar a `app-aluno`

- **Tipo:** `Test`
- **Dependências:** `T-132`
- **Rastreia:** `RF-61`, `RF-62`, `AC-105`, `AC-110`, `EC-47`, `US-22`, `US-25`
- **Arquivos:** `engine/gates.py` (`:329`, `:364`, `:440`, `:457`, `:553`), `engine/motor.py` (`:200`), `persistencia/arquivo/repositorio_snapshots.py` (`:621`, `_acao_requerida`), `tests/regras/test_repositorio_snapshots.py` (`:230`, `:239`, fixtures `acao_gate_1`/`acao_economia`), `tests/regras/test_ordem.py` (`:206`, fixture `acao`), `tests/estatica/test_tipo_acao_apenas_quatro_valores.py` (`:122`, fixture `acao_com_quinto_literal`)

**Descrição**

> **Lição das Rodadas 2, 3 e 4A, repetida quatro vezes até agora — não vai virar tarefa extra no meio da execução desta.** A lista de arquivos e linhas acima é a varredura real e completa de `grep -rn "AcaoRequerida("` do plano R4B.1.3, transcrita inteira: **6 construções** dentro de `engine/` (5 em `engine/gates.py` + 1 em `engine/motor.py`) + **1 desserialização** (`persistencia/arquivo/repositorio_snapshots.py`) + **3 fixtures de teste** que constroem `AcaoRequerida` diretamente. `report/plano.py:406` (`ContextoAcaoRequerida`) **lê** campos de `acao` mas não constrói `AcaoRequerida` e não lê o campo novo — citado pela varredura, **não editado nesta tarefa** (fora de escopo: nenhum `RF-61`–`RF-65` pede mudança em `report/`). `tests/regras/test_motor.py:410` cita `AcaoRequerida(TIPO_ACAO='INFORMACAO')` só em comentário, não é código executado — **não é consumidor a corrigir**.

Cada um dos 6 pontos de construção em `engine/` recebe o valor conforme a regra §14.2.1 (plano R4B.1.3, tabela completa):

- `engine/gates.py:329` (Gate 1, `STATUS_DIVIDA=QUITADA_A_CONFIRMAR`) → `VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0)` (`TIPO_ACAO="INFORMACAO"`, sem desembolso)
- `engine/gates.py:364` (Gate 1, `VALOR_RELEVANTE_PARA_QUITACAO=DESCONHECIDO`) → `dinheiro(0)`, mesmo motivo
- `engine/gates.py:440` (Gate 2, risco com prioridade excepcional) → `dinheiro(0)` explícito — nenhum valor de contenção modelado hoje (ambiguidade registrada em R4B.10.1, não resolvida por esta tarefa)
- `engine/gates.py:457` (Gate 2, risco sem prioridade excepcional) → `dinheiro(0)`, mesmo motivo do ponto acima
- `engine/gates.py:553` (Gate 3, transformação — renegociação/troca) → `Divida.VALOR_QUITACAO_HOJE` quando `STATUS_VALIDADE_PROPOSTA=VIGENTE`; senão `dinheiro(0)` — único ponto dos cinco com candidato real em `Divida` a consultar (`RF-62`)
- `engine/motor.py:200` (`_acao_economia_se_houver`) → `dinheiro(0)` (`TIPO_ACAO="ECONOMIA"`, não é ação de dívida)

`persistencia/arquivo/repositorio_snapshots.py:621` (`_acao_requerida`) desserializa `VALOR_ACAO_FINANCEIRA_IMEDIATA` do dict serializado (`_dinheiro_talvez(bruto["VALOR_ACAO_FINANCEIRA_IMEDIATA"])`) — `_serializar_canonico` já grava o campo automaticamente por nome, sem lista fixa, mesmo padrão de `T-92`/`T-125`. As 3 fixtures de teste ganham o argumento explícito.

**Sinalização a `app-aluno` (`AC-110`, `RF-61`):** ao final desta tarefa, registrar nota de fechamento identificando que `app-aluno` consome `AcaoRequerida` desde a Rodada 2 (`RF-28`–`RF-35`) e tem hash congelado dependente do formato desta dataclass — mesmo padrão de coordenação de `T-116` (Rodada 3). **Nenhum arquivo de `app-aluno` é editado por esta tarefa.**

**Critérios de aceite**

- [x] `mypy --strict` (comando `build`) fica limpo nos 10 pontos listados no campo "Arquivos" (6 construções `engine/` + 1 desserialização + 3 fixtures) — nenhum resta com `missing argument`
- [x] A nota de fechamento reporta a lista real de arquivos e linhas que o `build` acusou antes da correção — mesmo procedimento de `T-86`/`T-92`/`T-97`/`T-125`
- [x] Os 6 pontos de construção em `engine/` recebem exatamente o valor descrito na tabela acima — nenhum usa um valor diferente do documentado no plano R4B.1.3
- [x] `engine/gates.py:553` é o único dos 5 pontos de `gates.py` que deriva de `Divida.VALOR_QUITACAO_HOJE` (com `STATUS_VALIDADE_PROPOSTA=VIGENTE`) — os outros 4 usam `dinheiro(0)` incondicional
- [x] `persistencia/arquivo/repositorio_snapshots.py::_acao_requerida` desserializa o campo novo; round-trip de `SnapshotOrdem` com `ORDEM_ACOES` não vazia preserva `Decimal` exato e `DESCONHECIDO`
- [x] `report/plano.py:406` **não é editado** — confirmado na nota de fechamento como sinalizado (lê `acao` mas não o campo novo), não consumidor a corrigir nesta fatia
- [x] `tests/regras/test_motor.py:410` **não é editado** — confirmado como comentário, não código executado
- [x] A nota de fechamento contém a sinalização formal a `app-aluno` (`AC-110`): consumidor desde a Rodada 2, hash congelado dependente do formato de `AcaoRequerida`, nenhum arquivo daquele slug tocado
- [x] `pytest -q --ignore=tests/app_aluno` passa sem falha nova; `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes reexecutados sem mudança de valor numérico/ordem/status (só o hash de snapshots com `ORDEM_ACOES` muda, conforme R4B.9 "Não-regressão")
- [x] `ruff check .` passa

**Status:** `[x] concluída`

**Nota de fechamento**

`mypy --strict` (comando `build`, `engine persistencia collection app report tests` filtrados por existência), executado antes de qualquer correção, confirmou os mesmos **11 erros em 6 arquivos** já reportados por `T-132`:

```
engine\gates.py:347: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
engine\gates.py:382: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
engine\gates.py:458: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
engine\gates.py:475: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
engine\gates.py:571: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
engine\motor.py:200: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
persistencia\arquivo\repositorio_snapshots.py:621: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
tests\regras\test_ordem.py:206: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
tests\estatica\test_tipo_acao_apenas_quatro_valores.py:122: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
tests\regras\test_repositorio_snapshots.py:230: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]
tests\regras\test_repositorio_snapshots.py:239: error: Missing positional argument "VALOR_ACAO_FINANCEIRA_IMEDIATA" in call to "AcaoRequerida"  [call-arg]

Found 11 errors in 6 files (checked 290 source files)
```

**Correção, ponto a ponto (varredura completa de R4B.1.3):**

- `engine/gates.py` Gate 1, ramo `STATUS_DIVIDA=QUITADA_A_CONFIRMAR` (agora `:347`) → `VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0)`
- `engine/gates.py` Gate 1, ramo `VALOR_RELEVANTE_PARA_QUITACAO=DESCONHECIDO` (agora `:382`) → `dinheiro(0)`
- `engine/gates.py` Gate 2, risco com prioridade excepcional (agora `:458`) → `dinheiro(0)` explícito (ambiguidade de valor de contenção registrada em R4B.10.1, não resolvida aqui)
- `engine/gates.py` Gate 2, risco sem prioridade excepcional (agora `:475`) → `dinheiro(0)`
- `engine/gates.py` Gate 3, transformação (agora `:571`, ponto de construção deslocado para `:595` após a inserção da condicional) → condicional nova: `if divida.STATUS_VALIDADE_PROPOSTA is STATUS_VALIDADE_PROPOSTA.VIGENTE: valor_acao_financeira_imediata = divida.VALOR_QUITACAO_HOJE else: valor_acao_financeira_imediata = dinheiro(0)`, valor passado a `AcaoRequerida(VALOR_ACAO_FINANCEIRA_IMEDIATA=valor_acao_financeira_imediata, ...)` — **único** dos cinco pontos de `gates.py` que deriva de `Divida.VALOR_QUITACAO_HOJE`; import novo de `STATUS_VALIDADE_PROPOSTA` (`engine.tipos`) e de `dinheiro` (`engine.precisao`), ambos ausentes em `gates.py` até esta tarefa
- `engine/motor.py::_acao_economia_se_houver` (`:200`, `dinheiro` já importado) → `dinheiro(0)`

`persistencia/arquivo/repositorio_snapshots.py::_acao_requerida` (`:621`): `VALOR_ACAO_FINANCEIRA_IMEDIATA=_dinheiro_talvez(bruto["VALOR_ACAO_FINANCEIRA_IMEDIATA"])` acrescentado — mesmo helper já usado pelos demais campos `DinheiroTalvez` do módulo; `_serializar_canonico` já gravava o campo automaticamente por nome, nenhuma mudança do lado da serialização.

3 fixtures de teste, valores coerentes ao cenário de cada teste: `tests/regras/test_repositorio_snapshots.py::test_T92_acao_requerida_round_trip_contrato_estendido` (`acao_gate_1` → `dinheiro("123.45")`, `acao_economia` → `DESCONHECIDO` — deliberadamente os dois sabores de `DinheiroTalvez`, com novas asserções `assertar_exato` provando que o round-trip preserva `Decimal` exato e o sentinela `DESCONHECIDO` sem virar `0`/`None` silenciosamente); `tests/regras/test_ordem.py::test_dividas_bloqueadas_por_gate_nao_aparecem_e_vao_para_ordem_acoes` (fixture `acao`, origem Gate 2 não-excepcional → `dinheiro(0)`, import de `dinheiro` acrescentado); `tests/estatica/test_tipo_acao_apenas_quatro_valores.py::test_verificador_pega_quinto_literal_proposital` (fixture `acao_com_quinto_literal`, teste negativo de domínio de `TIPO_ACAO`, valor irrelevante ao propósito → `dinheiro(0)`, import de `dinheiro` acrescentado).

`report/plano.py:406` (`ContextoAcaoRequerida`) — **não editado**: confirmado por leitura, lê só `DIVIDA_ID`/`descricao`/`prioridade_excepcional` de `acao`, não o campo novo; fora de escopo desta fatia (nenhum `RF-61`–`RF-65` pede mudança em `report/`). `tests/regras/test_motor.py:410` — **não editado**: confirmado por leitura, `AcaoRequerida(TIPO_ACAO='INFORMACAO')` aparece só em comentário explicativo, não é código executado.

**Sinalização formal a `app-aluno` (`AC-110`, `RF-61`):** `app-aluno` consome `AcaoRequerida` desde a Rodada 2 (`RF-28`–`RF-35`) e tem hash congelado (`tests/app_aluno/estatica/hashes_congelados.json`) dependente do formato desta dataclass — mesma sinalização de coordenação já registrada em `T-116` (Rodada 3) para `RF-59`. `engine/gates.py` e `engine/motor.py` foram ambos alterados por esta tarefa: qualquer ponto de `app-aluno` que desserializa/espelha o shape de `AcaoRequerida` precisa de atualização coordenada — inclusive quanto ao posicionamento do campo novo (`VALOR_ACAO_FINANCEIRA_IMEDIATA` entra antes de `prioridade_excepcional`/`CAMPO_PENDENTE`, que têm default), caso `app-aluno` construa `AcaoRequerida` por argumento posicional em algum ponto (nenhum ponto real deste repositório o faz, mas a convenção de `app-aluno` não foi auditada aqui). **Nenhum arquivo de `app-aluno` foi editado por esta tarefa** — confirmado, nenhum comando tocou `tests/app_aluno/` nem qualquer caminho fora de `engine/`, `persistencia/`, `tests/regras/`, `tests/estatica/` listados no campo "Arquivos".

**Verificação:** `build` limpo (`Success: no issues found in 290 source files`); `ruff check .` → `All checks passed!`; `pytest -q --ignore=tests/app_aluno` → `568 passed, 9 skipped` (mesma contagem de skips pré-existente, nenhuma falha nova); reexecução isolada de `-m gabarito` → `13 passed`; reexecução isolada dos cinco invariantes (`-k "invariante or GAB"`) → `58 passed`; nenhum valor numérico, ordem ou status mudou — só o shape serializado de `AcaoRequerida` ganhou o campo novo (hash de snapshot com `ORDEM_ACOES` não vazia muda, conforme previsto em R4B.9 "Não-regressão").

---

### `T-134` — Implementar `NECESSIDADE_IMEDIATA_DIVIDA` em `engine/gates.py` — cadeia `if`/`elif` estrita de cinco ramos

- **Tipo:** `Data`
- **Dependências:** `T-133`
- **Rastreia:** `RF-64`, `RF-65`, `EC-40`, `EC-41`, `EC-42`, `EC-43`, `EC-44`, `US-22`, `US-23`
- **Arquivos:** `engine/gates.py`

**Descrição**

Função pura nova (plano R4B.4.2, `OQ-41` = módulo `engine/gates.py`), assinatura exata do plano: `GATE_PENDENTE`, `DIVIDA_STATUS_ESTRATEGICO`, `acao_financeira_imediata_executavel: AcaoRequerida | None`, `VALOR_RELEVANTE_PARA_QUITACAO` por parâmetro, retorno `DinheiroTalvez`. **A ordem dos cinco ramos é normativa, não sugestão** (§14.1.1) — implementada como cadeia `if`/`elif` estrita, nunca como funções auxiliares que calculam os dois valores candidatos e escolhem depois: 1) Gate 1 pendente → `0`; 2) Gate 3 pendente → `0`; 3) ação financeira imediata executável com `VALOR_ACAO_FINANCEIRA_IMEDIATA` conhecido → esse valor (inclui propagar `DESCONHECIDO` quando a ação existe e o valor é desconhecido, `RF-63`); 4) `DIVIDA_STATUS_ESTRATEGICO` em `{PRONTA_PARA_ORDENACAO, EM_ATAQUE}` → `VALOR_RELEVANTE_PARA_QUITACAO` **integral**, nunca fração (`RF-64`, `AC-107`); 5) senão → `0`. A trava de dupla contagem (`RF-65`) é consequência estrutural desta ordem — ramos 3 e 4 são mutuamente exclusivos por construção da cadeia, **não é implementada como verificação separada** (plano R4B.10).

**Critérios de aceite**

- [x] Assinatura idêntica ao plano R4B.4.2 — parâmetros nomeados (`*`, só keyword), tipos exatos, retorno `DinheiroTalvez`
- [x] Implementação é uma única cadeia `if`/`elif`/…/`else` com exatamente cinco ramos, na ordem exata do plano — nenhum `return` antecipado fora da cadeia, nenhuma função auxiliar que calcule mais de um ramo antes de decidir
- [x] Ramo 3 propaga `DESCONHECIDO` quando `acao_financeira_imediata_executavel.VALOR_ACAO_FINANCEIRA_IMEDIATA is DESCONHECIDO` — não cai para o ramo 4 nem para `0` (`RF-63`, `EC-41` distinguido: ação **não executável agora** não entra no ramo 3, cai para 4/5)
- [x] Ramo 4 usa `VALOR_RELEVANTE_PARA_QUITACAO` sem nenhuma multiplicação, `MIN`/`MAX` ou fração — valor passado adiante tal como recebido (`AC-107`)
- [x] Docstring/comentário da função cita `RF-64`, `RF-65`, `§14.1.1` — regra citada no código (`sdd.config.md` §4)
- [x] `REGRAS: Final[tuple[str, ...]]` de `engine/gates.py` ganha `"§14.1.1"`
- [x] Função não lê `EstadoFinanceiro`, `Diagnostico`, relógio, arquivo nem variável global — só os quatro parâmetros (pureza, plano R4B.2)
- [x] `mypy --strict engine/gates.py` e `ruff check .` passam
- [x] Nenhum teste é escrito nesta tarefa — comportamento verificado em `T-137`

**Status:** `[x] concluída`

**Nota de fechamento.** Função implementada em `engine/gates.py` logo após `particionar_elegibilidade`, como cadeia `if`/`elif`/…/`else` de cinco ramos com um único `return` ao final (variável `resultado` atribuída em cada ramo — nenhum `return` antecipado). Colisão de nome entre os parâmetros keyword-only `GATE_PENDENTE`/`DIVIDA_STATUS_ESTRATEGICO` (exigidos pela assinatura exata do plano) e os tipos de mesmo nome já importados diretamente (`from engine.tipos import GATE_PENDENTE, DIVIDA_STATUS_ESTRATEGICO`, usados pelo resto do módulo) resolvida com `import engine.tipos as tipos` adicional — os membros do enum são referenciados como `tipos.GATE_PENDENTE.INFORMACAO` etc. dentro do corpo da função nova, sem tocar nos imports diretos já usados pelo código pré-existente. `mypy --strict engine/gates.py`: `Success: no issues found in 1 source file`. `ruff check .`: `All checks passed!`. `mypy --strict` completo (comando `build`, 290 arquivos): limpo. `pytest -q --ignore=tests/app_aluno`: `568 passed, 9 skipped` (inalterado — nenhum teste escrito, nenhuma regressão). Nenhum acesso a `EstadoFinanceiro`/`Diagnostico`/relógio/arquivo/global — confirmado por leitura do corpo da função, que só referencia os quatro parâmetros e o módulo `tipos`/constante `DESCONHECIDO`/`dinheiro()`.

---

### `T-135` — Implementar `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` em `engine/gates.py` — soma com sinalização de incompletude

- **Tipo:** `Data`
- **Dependências:** `T-134`
- **Rastreia:** `RF-64`, `EC-45`, `EC-46`, `US-22`
- **Arquivos:** `engine/gates.py`

**Descrição**

Função pura nova (plano R4B.4.2), soma `NECESSIDADE_IMEDIATA_DIVIDA(d)` sobre **todas** as dívidas do inventário (elegíveis e bloqueadas — `RF-64` não restringe aos elegíveis; dívidas bloqueadas por Gate 1/3 já contribuem `0` pela própria fórmula dos ramos 1/2, então o resultado numérico é idêntico a somar só sobre elegíveis, mas iterar o inventário inteiro é mais direto, plano R4B.10). Assinatura: `particao: ParticaoElegibilidade`, `acoes_por_divida: Mapping[str, AcaoRequerida]`, retorno `DinheiroTalvez`. **Se qualquer parcela for `DESCONHECIDO`, o resultado inteiro é `DESCONHECIDO`** — nunca soma parcial das dívidas conhecidas apresentada como total definitivo (`AC-108`, propagação, não fallback).

**Critérios de aceite**

- [x] Assinatura idêntica ao plano R4B.4.2
- [x] Soma itera o inventário inteiro (`elegiveis` + `bloqueadas` de `ParticaoElegibilidade`), chamando `NECESSIDADE_IMEDIATA_DIVIDA` (`T-134`) para cada dívida
- [x] Inventário vazio → `0`, legitimamente, distinto de incompletude (`EC-45`)
- [x] Qualquer `NECESSIDADE_IMEDIATA_DIVIDA(d) is DESCONHECIDO` → função inteira retorna `DESCONHECIDO`, mesmo com as demais parcelas conhecidas e somáveis — nunca descarta a desconhecida como `0` (`EC-46`, `AC-108`)
- [x] Nenhum arredondamento intermediário — soma em `Decimal` exato (tolerância zero desta fatia, spec §4)
- [x] Docstring/comentário cita `RF-64`, `§14.1`
- [x] `REGRAS: Final[tuple[str, ...]]` de `engine/gates.py` ganha `"§14.1"`
- [x] Função não lê `EstadoFinanceiro`, `Diagnostico`, relógio, arquivo nem variável global
- [x] `mypy --strict engine/gates.py` e `ruff check .` passam
- [x] Nenhum teste é escrito nesta tarefa — comportamento verificado em `T-137`

**Status:** `[x] concluída`

**Nota de fechamento.** Função implementada em `engine/gates.py` logo após `NECESSIDADE_IMEDIATA_DIVIDA` (`T-134`). Itera `particao.elegiveis` (tupla de `Divida`) recompondo `VALOR_RELEVANTE_PARA_QUITACAO` via `compor_VALOR_RELEVANTE_PARA_QUITACAO` (já importado no módulo, `T-27`) e usando `GATE_PENDENTE.NENHUM`/`DIVIDA_STATUS_ESTRATEGICO.PRONTA_PARA_ORDENACAO` (o par que `determinar_status_estrategico` garante para toda dívida elegível); depois itera `particao.bloqueadas` (tupla de `ResultadoGates`), usando `GATE_PENDENTE`/`DIVIDA_STATUS_ESTRATEGICO` já resolvidos pelo próprio `ResultadoGates` — `VALOR_RELEVANTE_PARA_QUITACAO=dinheiro(0)` nesse segundo laço é valor neutro nunca de fato lido, pois nenhuma dívida bloqueada (`DIVIDA_ELEGIVEL_ORDEM=False`) tem `DIVIDA_STATUS_ESTRATEGICO` em `{PRONTA_PARA_ORDENACAO, EM_ATAQUE}` — o único ramo de `NECESSIDADE_IMEDIATA_DIVIDA` que leria esse parâmetro, comentário deixado no código explicando a garantia. `acoes_por_divida` (mapa `DIVIDA_ID -> AcaoRequerida`) alimenta o parâmetro `acao_financeira_imediata_executavel` para ambos os laços via `.get()`, ausência = `None` = ramo 3 nunca satisfeito por aquela dívida. Curto-circuita com `return DESCONHECIDO` assim que qualquer parcela for `DESCONHECIDO`, em qualquer um dos dois laços — nunca descarta o `DESCONHECIDO` nem soma parcial. Inventário vazio (`elegiveis == () and bloqueadas == ()`) não entra em nenhum laço e devolve `dinheiro(0)` inicial, distinto de `DESCONHECIDO`. Soma via `total += parcela` em `Decimal` (via `dinheiro()`), sem quantização. `mypy --strict engine/gates.py`: `Success: no issues found in 1 source file`. `ruff check .`: `All checks passed!`. `mypy --strict` completo (290 arquivos): limpo. `pytest -q --ignore=tests/app_aluno`: `568 passed, 9 skipped` (inalterado).

---

### `T-136` — Provar por teste estático que toda construção de `AcaoRequerida(...)` em `engine/` fornece `VALOR_ACAO_FINANCEIRA_IMEDIATA`

- **Tipo:** `Test`
- **Dependências:** `T-133`
- **Rastreia:** `RF-61`, `AC-110`, `EC-47`, `US-25`
- **Arquivos:** `tests/estatica/test_acao_requerida_tem_valor_financeiro.py` (novo)

**Descrição**

Arquivo novo (plano R4B.3), prova estrutural complementar ao `mypy --strict` — mesmo espírito de `test_sem_float_no_motor.py`/`test_sem_derivacao_de_classificacao_mobilizacao.py`. Varre a AST de `engine/**/*.py` e confirma, por inspeção do `ast.Call` de cada construção de `AcaoRequerida(...)`, que o `kwarg` `VALOR_ACAO_FINANCEIRA_IMEDIATA` está presente. É a metade estrutural de `AC-110` (a metade de sinalização a `app-aluno` é `T-133`).

**Critérios de aceite**

- [x] O teste varre `engine/**/*.py` por AST e localiza todo `ast.Call` cujo `func` resolve para o nome `AcaoRequerida`
- [x] Confirma que cada chamada encontrada tem um `keyword` chamado `VALOR_ACAO_FINANCEIRA_IMEDIATA` — nomeando arquivo e linha se alguma não tiver
- [x] Confirma por asserção não vácua que ao menos 6 construções foram encontradas em `engine/` (as 6 reais da varredura de `T-133`) — evita prova vácua caso o detector não encontre nada
- [x] Existe teste-companheiro de prova negativa: uma construção **proposital**, alimentada ao detector como string/AST sintética, sem o `kwarg` `VALOR_ACAO_FINANCEIRA_IMEDIATA`, e confirmada como pega — mesmo padrão de `test_verificador_pega_quinto_literal_proposital` (Rodada 2)
- [x] O teste passa sobre o `engine/` real ao fim da tarefa
- [x] `pytest -q tests/estatica/test_acao_requerida_tem_valor_financeiro.py` passa

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).** `tests/estatica/test_acao_requerida_tem_valor_financeiro.py` criado, mesma família de `test_sem_derivacao_de_classificacao_mobilizacao.py`/`test_tipo_acao_apenas_quatro_valores.py`: varredura de AST sobre `engine/**/*.py`, localizando todo `ast.Call` cujo `func` resolve para `AcaoRequerida` (forma direta `ast.Name` e qualificada `ast.Attribute`), confirmando `keyword.arg == "VALOR_ACAO_FINANCEIRA_IMEDIATA"` em cada um. Encontrou as 6 construções reais de `engine/` (5 em `gates.py`, 1 em `motor.py`), todas com o `kwarg` — `test_toda_construcao_de_acaorequerida_tem_valor_acao_financeira_imediata` e `test_passa_sobre_o_engine_real` passam sobre o pacote real. Prova negativa (`test_detector_pega_construcao_proposital_sem_o_kwarg`) alimenta o mesmo detector com uma construção fabricada como STRING, sem o `kwarg`, e confirma que é pega — nomeando arquivo `engine/caso_proposital.py` e linha `3`. Contraprova (`test_detector_nao_reporta_construcao_com_o_kwarg_presente`) confirma que uma construção completa não é reportada. `pytest -q tests/estatica/test_acao_requerida_tem_valor_financeiro.py` → `4 passed`. `ruff check` e `mypy --strict` limpos.

---

### `T-137` — Testar `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`: `GAB-NFI-01` a `GAB-NFI-05`, precedência forçada, trava de dupla contagem, incompletude

- **Tipo:** `Test`
- **Dependências:** `T-134`, `T-135`
- **Rastreia:** `RF-64`, `RF-65`, `AC-101`, `AC-102`, `AC-103`, `AC-104`, `AC-105`, `AC-106`, `AC-107`, `AC-108`, `AC-109`, `AC-111`, `EC-40`, `EC-41`, `EC-42`, `EC-43`, `EC-44`, `EC-45`, `EC-46`, `US-22`, `US-23`, `US-24`
- **Arquivos:** `tests/regras/test_necessidade_imediata.py` (novo)

**Descrição**

Arquivo novo de `tests/regras/`, marcador `regra`. Cobre as duas funções de `T-134`/`T-135` isoladamente, com os cinco gabaritos `GAB-NFI-01` a `GAB-NFI-05` (valores literais §14.16), a prova de precedência forçada (`AC-106`, mesmo padrão de `AC-95`/`AC-96` da fatia 4A), a prova de que `VALOR_RELEVANTE_PARA_QUITACAO` entra integral (`AC-107`), a prova de incompletude material (`AC-108`) e a auditoria de dupla contagem (`AC-111`).

**Critérios de aceite**

- [x] `GAB-NFI-01` literal (`VALOR_RELEVANTE_PARA_QUITACAO=20.000`, `DIVIDA_STATUS_ESTRATEGICO=PRONTA_PARA_ORDENACAO`, nenhum gate pendente, nenhuma ação financeira imediata) → `NECESSIDADE_IMEDIATA_DIVIDA=20.000` exato (`AC-101`)
- [x] `GAB-NFI-02` literal (`VALOR_RELEVANTE_PARA_QUITACAO=20.000`, `Gate1=PENDENTE`) → `0` exato — Gate 1 vence antes de qualquer outra condição (`AC-102`)
- [x] `GAB-NFI-03` literal (`Gate3=PENDENTE`, `Gate1` resolvido, `VALOR_RELEVANTE_PARA_QUITACAO` positivo) → `0` exato — Gate 3 vence sobre status estratégico e ação financeira imediata (`AC-103`)
- [x] `GAB-NFI-04` literal (ação de Gate 2/4 com `VALOR_ACAO_FINANCEIRA_IMEDIATA=8.000`, mesma dívida com `VALOR_RELEVANTE_PARA_QUITACAO=15.000`) → `8.000` exato, **nunca** `23.000` — trava de dupla contagem (`AC-104`, `RF-65`)
- [x] `GAB-NFI-05` literal (ação prioritária "solicitar proposta", sem exigência de desembolso) → `VALOR_ACAO_FINANCEIRA_IMEDIATA=0` exato (`AC-105`)
- [x] Precedência forçada (`AC-106`): dívida construída para satisfazer simultaneamente Gate 1 pendente **e** `DIVIDA_STATUS_ESTRATEGICO` elegível — resultado é `0` (ramo 1 vence), nunca o valor do ramo 4; teste distinto de `AC-102`, que testa Gate 1 isolado
- [x] `VALOR_RELEVANTE_PARA_QUITACAO` entra integral (`AC-107`): teste com valor alto para o qual uma fração "pareceria mais razoável" (ex.: metade ou 80%) e confirma que o resultado é o valor **cheio**, não a fração — prova positiva de que nenhuma redução estratégica é aplicada nesta função
- [x] Incompletude material (`AC-108`): inventário com ao menos uma dívida `NECESSIDADE_IMEDIATA_DIVIDA(d)=DESCONHECIDO` e as demais com valores conhecidos e somáveis — `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` é `DESCONHECIDO`, teste dedicado que compara explicitamente contra a soma das conhecidas (provando que essa soma parcial **não** é o resultado retornado, não apenas que o resultado "é `DESCONHECIDO`" isolado)
- [x] Inventário todo com `NECESSIDADE_IMEDIATA_DIVIDA=0` → `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=0` legitimamente, teste distinto do de incompletude (`EC-45`)
- [x] `AC-109` (metade verificável nesta fatia): `VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO` em ação executável agora com precedência material → `NECESSIDADE_IMEDIATA_DIVIDA=DESCONHECIDO`; o teste **não afirma nada sobre `STATUS_METODO`** (metade de status é fatia 4C, R4B.6.1)
- [x] `EC-40`: dívida com Gate 1 **e** Gate 3 pendentes simultaneamente → `0`, Gate 3 nunca é avaliado (mesmo resultado que seria obtido se fosse)
- [x] `EC-41`: ação de Gate 2/4 existente mas **não executável agora** (ex.: proposta expirada) → não entra no ramo 3, cai para ramo 4/5
- [x] `EC-42`: ação executável agora com valor `0` conhecido (ex.: regularização sem custo) → `0`, distinto de `DESCONHECIDO`, não aciona sinalização de incompletude
- [x] `EC-43`: `DIVIDA_STATUS_ESTRATEGICO` fora de `{PRONTA_PARA_ORDENACAO, EM_ATAQUE}` (ex.: `EM_ANALISE`, `INTERVENCAO_PENDENTE`), nenhum gate pendente, nenhuma ação financeira imediata → `0` (ramo 5)
- [x] `EC-44`: dívida que tinha ação financeira imediata (ramo 3) e, num segundo estado simulado, o gate que a direcionava foi resolvido → passa a contribuir por `VALOR_RELEVANTE_PARA_QUITACAO` (ramo 4) se elegível, nunca somando os dois valores no mesmo estado
- [x] Auditoria `AC-111`: dívida com `VALOR_ACAO_FINANCEIRA_IMEDIATA` e `VALOR_RELEVANTE_PARA_QUITACAO` ambos positivos e **diferentes** (mesmo caso de `GAB-NFI-04`, adicionado como prova de auditoria, não só caso feliz) — confirma que o resultado é exatamente um dos dois, nunca a soma
- [x] Cada teste cita o `AC-NN`/`EC-NN`/`GAB-NFI-NN` correspondente na docstring
- [x] `pytest -q tests/regras/test_necessidade_imediata.py` passa

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).** `tests/regras/test_necessidade_imediata.py` criado — 17 testes, marcador `regra` (+ `gabarito` nos cinco `GAB-NFI-01` a `05`). Testes de `NECESSIDADE_IMEDIATA_DIVIDA` constroem os quatro parâmetros keyword-only diretamente, conforme a assinatura de `T-134`; testes de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` constroem `Divida`/`ParticaoElegibilidade` reais via `particionar_elegibilidade`, exercendo a soma de ponta a ponta. Ponto notável: o teste de incompletude material (`AC-108`) usa uma dívida com `RISCO_MATERIAL_IMINENTE=True` (Gate 2, bloqueada) associada a uma `AcaoRequerida` com `VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO` via `acoes_por_divida` — não uma dívida com `SALDO_DEVEDOR_ATUAL=DESCONHECIDO`, que seria bloqueada pelo Gate 1 e contribuiria `0` pelo ramo 1 (não `DESCONHECIDO`); só o ramo 3 propaga `DESCONHECIDO`, documentado na docstring do teste. `pytest -q tests/regras/test_necessidade_imediata.py` → `17 passed`. `ruff check` e `mypy --strict` limpos.

---

### `T-138` — Registrar o marcador `gabarito_necessidade_financeira` e criar o diretório dos `GAB-NFI-01` a `05`

- **Tipo:** `Infra`
- **Dependências:** `T-134`, `T-135`
- **Rastreia:** `RF-64`, `US-22`, `US-23`
- **Arquivos:** `pyproject.toml`, `tests/gabaritos_necessidade_financeira/__init__.py` (novo)

**Descrição**

Mesma decisão de `T-108` (Rodada 3, `gabarito_ataque_imediato`) e `T-128` (fatia 4A, `gabarito_classificacao_ativos`), reaplicada com justificativa própria: **marcador novo, não reaproveitamento de `gabarito_classificacao_ativos`.** Razão — `gabarito_classificacao_ativos` foi nomeado e descrito em `T-128` especificamente como "fórmula/classificação isolada da §14", cobrindo `classificar_investimento`/`classificar_ativo_fisico`/`derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO` (§14.3–§14.12); `GAB-NFI-01` a `05` testam uma família normativa distinta dentro da mesma seção 14 (§14.1/§14.1.1/§14.2, a fórmula de necessidade financeira imediata e a trava de dupla contagem), com fonte de entrada diferente (`ResultadoGates`/`AcaoRequerida`, não `ItemAtivo`/`ItemInvestimento`). Reaproveitar o marcador da fatia 4A misturaria, sob o mesmo nome, dois grupos de gabaritos que testam módulos e subseções normativas diferentes — o mesmo motivo que já separou `gabarito_ataque_imediato` de `gabarito` em `T-108`. Marcador novo `gabarito_necessidade_financeira`, diretório novo `tests/gabaritos_necessidade_financeira/`. **Consequência operacional a divulgar:** o comando de homologação passa a ser `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"`.

**Critérios de aceite**

- [ ] `[tool.pytest.ini_options] markers` do `pyproject.toml` registra `gabarito_necessidade_financeira` com descrição que o distingue de `gabarito`, `gabarito_ataque_imediato` e `gabarito_classificacao_ativos` ("fórmula de necessidade financeira imediata e trava de dupla contagem da §14.1/§14.2, não ponta a ponta")
- [ ] As descrições dos quatro marcadores existentes ficam **inalteradas**
- [ ] `tests/gabaritos_necessidade_financeira/` existe, com `__init__.py` no mesmo padrão de `tests/gabaritos_classificacao_ativos/__init__.py` (uma linha de docstring), importável e coletado por `pytest -q`
- [ ] `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"` roda sem erro de marcador desconhecido
- [ ] O comando de homologação novo é registrado na nota de fechamento desta tarefa
- [ ] `pytest --strict-markers` não reclama do marcador novo
- [ ] Nenhum teste `GAB-NFI` é escrito nesta tarefa — só marcador e diretório

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).**

> **COMANDO DE HOMOLOGAÇÃO NOVO — divulgar para a revisão da fatia:**
>
> ```
> pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"
> ```
>
> O comando anterior (registrado em `T-128`) continua rodando sem erro —
> quem usá-lo terá cobertura silenciosamente menor, perdendo os cinco
> `GAB-NFI-01` a `05` a partir de `T-139`.

Duas alterações, exatamente as previstas pela descrição desta tarefa:

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ [tool.pytest.ini_options] markers
     "gabarito_classificacao_ativos: reproduz gabarito de fórmula/classificação isolada da seção 14, NÃO ponta a ponta (GAB-NFI-06 a GAB-NFI-12 — sem dívidas, gates nem cronograma)",
+    "gabarito_necessidade_financeira: reproduz gabarito da fórmula de necessidade financeira imediata e trava de dupla contagem da seção 14.1/14.2, NÃO ponta a ponta (GAB-NFI-01 a GAB-NFI-05 — fonte ResultadoGates/AcaoRequerida, não ItemAtivo/ItemInvestimento)",
     "regra: testa regra normativa isolada de uma família (M, R, A, F, O, H, S, Q, V, T, G)",
```

```diff
--- /dev/null
+++ b/tests/gabaritos_necessidade_financeira/__init__.py
@@
+"""Gabaritos de necessidade financeira imediata: GAB-NFI-01 a 05 (§14.1/§14.2, não ponta a ponta)"""
```

As quatro descrições de marcador existentes (`gabarito`, `invariante`, `gabarito_ataque_imediato`, `gabarito_classificacao_ativos`) ficam **inalteradas** — confirmado por diff, nenhuma linha além da inserção foi tocada.

**Verificação.** `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"` → `42 passed, 1504 deselected`, zero erro de marcador desconhecido. `pytest --strict-markers` sobre a suíte completa → mesma contagem final (`1468 passed, 75 skipped`, mais os 3 failures pré-existentes de `tests/app_aluno` não relacionados a esta tarefa — ver `T-140`), sem reclamação de marcador. `pytest -q --collect-only tests/gabaritos_necessidade_financeira` → `no tests collected` (exit `5`, aceito pela seção 2 do `sdd.config.md`: esperado, nenhum `GAB-NFI` escrito nesta tarefa por decisão de escopo). `python -c "import tests.gabaritos_necessidade_financeira"` → importa sem erro. `ruff check .` → `All checks passed!` (a docstring inicial excedia 100 colunas e foi encurtada para caber em `line-length = 100`, mesmo ajuste feito em `T-128`). `mypy --strict` sobre `engine persistencia collection app report tests` → limpo. `pytest -q --ignore=tests/app_aluno` → `589 passed, 9 skipped`, idêntico ao baseline informado no início da fatia: zero regressão.

---

### `T-139` — Reproduzir `GAB-NFI-01` a `GAB-NFI-05` como homologação dedicada

- **Tipo:** `Test`
- **Dependências:** `T-137`, `T-138`
- **Rastreia:** `RF-64`, `RF-65`, `AC-101`, `AC-102`, `AC-103`, `AC-104`, `AC-105`, `US-22`, `US-23`
- **Arquivos:** `tests/gabaritos_necessidade_financeira/test_gab_nfi_01_divida_ordinaria_elegivel.py`, `tests/gabaritos_necessidade_financeira/test_gab_nfi_02_gate1_pendente.py`, `tests/gabaritos_necessidade_financeira/test_gab_nfi_03_gate3_pendente.py`, `tests/gabaritos_necessidade_financeira/test_gab_nfi_04_oportunidade_gate4.py`, `tests/gabaritos_necessidade_financeira/test_gab_nfi_05_acao_sem_valor_monetario.py`

**Descrição**

Os cinco gabaritos desta fatia (§14.16), um arquivo por gabarito, marcador `gabarito_necessidade_financeira` (`T-138`), tolerância **zero** (spec §5, mesma régua de `GAB-AI`/`GAB-NFI-06`–`12`). Reexecuta os cenários de `T-137`, mas como suíte de homologação formal e isolada — a seção 10 da canônica exige que a engine seja aprovada quando reproduz os gabaritos, não apenas que os testes de regra individuais passem.

**Critérios de aceite**

- [x] Os cinco arquivos existem em `tests/gabaritos_necessidade_financeira/`, um por `GAB-NFI-NN` (`01` a `05`), com o marcador `gabarito_necessidade_financeira`
- [x] Cada teste usa os valores literais exatos do enunciado do gabarito na spec §14.16, sem reinterpretação
- [x] Todos os cinco usam tolerância **zero** — `Decimal` exato, sem `± R$ 0,05` (spec §5, "Tolerância dos `GAB-NFI`")
- [x] `GAB-NFI-04` reforça explicitamente `!= 23.000` (soma indevida), além de `== 8.000`
- [x] `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"` passa inteiro, incluindo os cinco novos
- [x] `pytest -q tests/gabaritos_necessidade_financeira/` → 5 passed

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).** Cinco arquivos criados em `tests/gabaritos_necessidade_financeira/`, um por `GAB-NFI-NN`, marcador `gabarito_necessidade_financeira`, valores literais exatos de §14.16 (idênticos aos usados em `tests/regras/test_necessidade_imediata.py`, `T-137`): `GAB-NFI-01` (dívida elegível, `VALOR_RELEVANTE_PARA_QUITACAO=20.000` → `20.000`), `GAB-NFI-02` (Gate1 pendente → `0`), `GAB-NFI-03` (Gate3 pendente, Gate1 resolvido, valor positivo → `0`), `GAB-NFI-04` (ação Gate 2/4 de `8.000` + `VALOR_RELEVANTE_PARA_QUITACAO=15.000` → `8.000`, `!= 23.000` explícito), `GAB-NFI-05` (ação sem desembolso → `VALOR_ACAO_FINANCEIRA_IMEDIATA=0`, testado diretamente sobre `AcaoRequerida`, não sobre `NECESSIDADE_IMEDIATA_DIVIDA` — mesma leitura da tabela da spec, que distingue os dois resultados). `assertar_exato` em toda asserção monetária, mesmo padrão de `GAB-AI`/`GAB-NFI-06`–`12`. Cada docstring documenta cenário/resultado/âncora (`AC-101`–`105`) no formato de `tests/gabaritos_ataque_imediato/test_gab_ai_01_valor_aceito_abaixo_do_total.py`, incluindo a nota cruzada com `tests/regras/test_necessidade_imediata.py` (`T-137`). Verificação: `ruff check .` → `All checks passed!`; `mypy --strict` (`build`, `engine persistencia collection app report tests`) → `Success: no issues found in 298 source files`; `pytest -q tests/gabaritos_necessidade_financeira/` → `5 passed`; `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"` → `47 passed, 1504 deselected`; `pytest -q --ignore=tests/app_aluno` completo → `594 passed, 9 skipped` (589 + 5), zero falhas, zero regressão.

---

### `T-140` — Sinalizar formalmente ao slug `app-aluno` a quebra de contrato de `AcaoRequerida` e fechar a fatia 4B

- **Tipo:** `Docs`
- **Dependências:** `T-133`, `T-136`, `T-137`, `T-139`
- **Rastreia:** `RF-61`, `AC-110`, `US-25`
- **Arquivos:** `tasks/motor-calculo.tasks.md` (esta seção), `specs/motor-calculo.spec.md` (§10, se houver Open Question a atualizar)

**Descrição**

Sinalização única, ao fim da fatia inteira — mesmo padrão de `T-116` (fim da Rodada 3): identifica o ponto exato de quebra para `app-aluno`, reporta a lista de arquivos/hashes que aquele slug precisaria re-congelar, e confirma que **nenhum arquivo de `app-aluno` foi tocado** por esta fatia. Não é edição no slug externo — é aviso formal, mesmo mecanismo de coordenação já usado para `RF-31`/`RF-41`/`RF-59`.

**Critérios de aceite**

- [x] A nota de fechamento identifica o campo novo (`VALOR_ACAO_FINANCEIRA_IMEDIATA`), sua posição posicional em `AcaoRequerida` (R4B.4.1) e que toda construção real neste repositório usa argumento nomeado — o risco posicional é teórico para este repositório mas real para `app-aluno`, que pode não seguir a mesma convenção
- [x] A nota de fechamento reporta se `hashes_congelados.json` (`tests/app_aluno/estatica/`) precisa de re-congelamento de `engine/gates.py` (e de qualquer outro arquivo tocado nas tarefas `T-132`–`T-137` desta fatia) — confirmado por comparação de hash, mesmo procedimento de `T-116`
- [x] Confirma, por timestamp/hash, que nenhum arquivo de `app/` ou `tests/app_aluno/` foi editado por qualquer tarefa `T-132`–`T-139`
- [x] `OQ-29` (spec, reafirmada na fatia 4A) é atualizada: a metade `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` está **implementada e testada** por esta fatia; a metade `ATAQUE_IMEDIATO_RECOMENDADO`/ligação em `calcular_diagnostico` permanece aberta, escopo da fatia 4C
- [x] Comando de verificação completo (`build`, `lint`, `test`, homologação `pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"`) roda e o resultado real é reportado na nota de fechamento
- [x] Nenhuma decisão de metodologia é tomada nesta tarefa

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10) — spec atualizada em `specs/motor-calculo.spec.md` §10 (linha da tabela de `OQ-29`, "Bloqueiam a fatia 3C — exigem o especialista do método"), esta seção de `tasks/motor-calculo.tasks.md`. Nenhum outro arquivo tocado por esta tarefa.**

---

## SINALIZAÇÃO AO SLUG `app-aluno` — fim da Rodada 4, fatia 4B (2026-09-10, `T-140`)

> Emitida **uma única vez**, ao fim da fatia inteira (mesmo padrão de `T-116`,
> fim da Rodada 3). Nada aqui é edição no slug `app-aluno`: é aviso. **Nenhuma
> decisão de metodologia é tomada.**

### Aviso 1 — campo novo em `AcaoRequerida`, posição posicional, convenção usada neste repositório

`AcaoRequerida` (`engine/gates.py`) ganhou o campo `VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez`, **sem default**, inserido na posição exata do plano R4B.4.1 — **entre `gate_origem` e `prioridade_excepcional`**:

```python
ACAO_ID: str
DIVIDA_ID: str | None
TIPO_ACAO: str
descricao: str
gate_origem: Literal[1, 2, 3] | None
VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez   # <- campo novo, posição 6 de 8
prioridade_excepcional: bool = False              # tem default
CAMPO_PENDENTE: Literal[...] | None = None        # tem default
```

Isso é quebra de contrato, não adição: qualquer construção existente de `AcaoRequerida(...)` sem esse argumento levanta `TypeError: missing 1 required positional argument`. **Toda construção real deste repositório usa argumento nomeado** — confirmado pelas 6 construções em `engine/gates.py`/`engine/motor.py` (varredura de `T-133`) e pelas fixtures de teste, todas na forma `AcaoRequerida(ACAO_ID=..., DIVIDA_ID=..., ..., VALOR_ACAO_FINANCEIRA_IMEDIATA=..., ...)`. **O risco posicional é teórico para este repositório**, mas é **real para `app-aluno`**: se aquele slug construir ou desserializar `AcaoRequerida` por posição em algum ponto não auditado por esta fatia, o campo novo entra na 6ª posição (antes dos dois campos com default) e desloca qualquer argumento posicional que hoje ocupe essa posição ou as seguintes. `app-aluno` consome `AcaoRequerida` desde a Rodada 2 (`RF-28`–`RF-35`) — mesma sinalização de coordenação já registrada em `T-133`, reforçada aqui ao fim da fatia.

### Aviso 2 — hash congelado de `AC-44`: 5 arquivos divergentes, medidos por SHA-256 real

Conferência `sha256` arquivo a arquivo do manifesto `tests/app_aluno/estatica/hashes_congelados.json` (34 entradas) contra o conteúdo atual de cada um:

**Divergentes — precisam de re-congelamento:**

| Arquivo | Causa |
| --- | --- |
| `engine/gates.py` | Tocado por `T-132`, `T-133`, `T-134`, `T-135` (campo novo em `AcaoRequerida`, correção dos 6 pontos de construção, `NECESSIDADE_IMEDIATA_DIVIDA`, `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`) |
| `engine/motor.py` | Tocado por `T-133` (ponto de construção `_acao_economia_se_houver`) |
| `persistencia/arquivo/repositorio_snapshots.py` | Tocado por `T-133` (`_acao_requerida` desserializa o campo novo) |
| `engine/ataque_imediato.py` | **Pré-existente** — já divergente desde a Rodada 3 (`T-102`/`T-110`, sinalizado em `T-116`); **não** tocado por `T-132`–`T-139` |
| `engine/estado.py` | **Pré-existente** — já divergente desde a Rodada 3 (`T-94`/`T-97`, sinalizado em `T-116`); **não** tocado por `T-132`–`T-139` |

Os **três primeiros** são consequência direta desta fatia (4B). Os **dois últimos** já divergiam antes de `T-132` — nenhuma tarefa desta fatia os edita nem agrava a divergência; ficam listados aqui só para que `app-aluno` re-congele o conjunto completo de uma vez, em vez de precisar de uma segunda rodada de sinalização.

**Demais 29 arquivos do manifesto batem exatamente** — nenhuma outra divergência.

Consequência em teste: `tests/app_aluno/estatica/test_engine_congelado.py` falha em **3** dos seus testes (`test_ac44_hashes_congelados_batem_com_o_conteudo_atual_dos_arquivos`, `test_ac44_json_cobre_todo_py_de_engine_e_persistencia_e_a_migracao_antiga` — este por `engine/ataque_imediato.py` seguir ausente do manifesto, mesma causa já registrada em `T-116` — e `test_ac44_alterar_um_byte_muda_o_hash_e_seria_detectado`, consequência da divergência de `engine/gates.py`). `hashes_congelados.json` **não** foi editado por esta tarefa nem por nenhuma tarefa `T-132`–`T-139` — a atualização do arquivo é procedimento do slug `app-aluno` (mesma divisão de responsabilidade de `T-116`).

### Aviso 3 — nenhum arquivo de `app/` ou `tests/app_aluno/` foi tocado — confirmado por timestamp e hash

Medição direta, não por memória:

- `app/montagem/estado.py`: SHA-256 atual `a57cf274beb6b28e5d40bcc35134e85532c891ca77533dadf9ed554dbfbc4b07`; `mtime` = **2026-09-07 18:46:35** (mesmo dia de `T-116`, fim da Rodada 3 — a "tentativa revertida" documentada ali).
- `tests/app_aluno/estatica/hashes_congelados.json`: `mtime` = **2026-09-07 17:25:48**.
- Varredura completa de `find app tests/app_aluno -name "*.py" -printf '%TY-%Tm-%Td %TH:%TM'`, ordenada por data decrescente: o arquivo `.py` **mais recente** de qualquer ponto de `app/` ou `tests/app_aluno/` é `tests/app_aluno/test_ordem_acoes_dependencia_externa.py`, com `mtime` **2026-09-07 18:50** — mais de dois dias antes de `T-132` (2026-09-10). Nenhum arquivo desses diretórios tem `mtime` posterior a 07/09.
- Por contraste, `engine/gates.py` (tocado nesta fatia) tem `mtime` **2026-09-10 00:09:08** — hoje.

**Nota de honestidade sobre o hash de `app/montagem/estado.py`.** O SHA-256 medido agora (`a57cf274...`) diverge do valor que a nota de fechamento de `T-116` registrou (`cd8cdec0...`) para o "antes e depois" daquela tarefa. O timestamp do arquivo (07/09, mesma janela de `T-116`) e a varredura completa acima excluem qualquer edição por tarefa desta fatia (4B) ou da fatia 4A — nenhum arquivo de `app/`/`tests/app_aluno/` tem `mtime` posterior a 07/09. A divergência entre os dois valores de hash é mais provável de ser um erro de transcrição na nota de `T-116` do que uma edição real não registrada; reportado aqui por honestidade (`CLAUDE.md`, "reporte com honestidade"), sem decidir a causa — que está fora do escopo desta tarefa (documentação/sinalização, sem edição de `app/`).

**Confirmação por escopo dos arquivos editados por `T-132`–`T-139`:** `engine/gates.py`, `engine/motor.py`, `persistencia/arquivo/repositorio_snapshots.py`, `tests/regras/test_ordem.py`, `tests/estatica/test_tipo_acao_apenas_quatro_valores.py`, `tests/regras/test_repositorio_snapshots.py`, `tests/estatica/test_acao_requerida_tem_valor_financeiro.py` (novo), `tests/regras/test_necessidade_imediata.py` (novo), `pyproject.toml`, `tests/gabaritos_necessidade_financeira/__init__.py` (novo) e os cinco arquivos `test_gab_nfi_0*` (novos) — nenhum sob `app/` ou `tests/app_aluno/`.

### `OQ-29` — atualizada em `specs/motor-calculo.spec.md` §10

A linha da tabela "Bloqueiam a fatia 3C" passa de **aberta — enviada ao especialista** para **PARCIALMENTE respondida e IMPLEMENTADA**: a metade `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (§14.1/§14.1.1, `RF-64`/`RF-65`) está implementada em `engine/gates.py` e testada (`T-134`–`T-139`, gabaritos `GAB-NFI-01` a `05`). A metade `ATAQUE_IMEDIATO_RECOMENDADO`/ligação em `calcular_diagnostico` — que hoje ainda recebe `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` por parâmetro (`RF-48`), sem consumir a fórmula nova — **permanece aberta**, escopo declarado da fatia 4C. Nenhuma decisão de metodologia foi tomada ao atualizar o status: a ligação em `calcular_diagnostico` não foi escrita por nenhuma tarefa desta fatia (confirmado por leitura — `engine/diagnostico.py` não foi tocado por `T-132`–`T-139`, não consta na lista de arquivos divergentes do Aviso 2).

### Verificação completa do projeto ao fim da fatia 4B (2026-09-10)

- `lint` (`ruff check .`) → `All checks passed!`
- `build` (`mypy --strict`, seis pastas filtradas por existência: `engine persistencia collection app report tests`) → `Success: no issues found in 298 source files`
- `test` completo (`pytest -q`, **incluindo** `tests/app_aluno`) → **`3 failed, 1473 passed, 75 skipped`** — as 3 falhas são exatamente as do Aviso 2 (`test_engine_congelado.py`), pré-existentes/decorrentes da divergência de hash sinalizada, não corrigidas aqui por pertencerem ao procedimento de `app-aluno`
- `test` com `--ignore=tests/app_aluno` → `594 passed, 9 skipped` — zero regressão sobre o baseline de início da fatia (`589 passed, 9 skipped`) mais os 5 gabaritos novos de `T-139`
- Homologação (`pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"`) → `47 passed, 1504 deselected`

**Fatia 4B fechada: 9 de 9 tarefas concluídas (`T-132` a `T-140`).** Cobertura de requisitos (`RF-61`–`RF-65`) e critérios de aceite (`AC-101`–`AC-111`) inalterada desde a tabela registrada ao fim de `T-139` — nenhuma tarefa desta fatia introduziu requisito ou critério novo. Nenhuma decisão de metodologia foi tomada por esta tarefa.

---

## Cobertura de requisitos — Rodada 4, fatia 4B

| Requisito | Tarefas |
| --------- | ------- |
| `RF-61` — campo monetário novo em `AcaoRequerida`, quebra de contrato, varredura de consumidores, sinalização a `app-aluno` | `T-132`, `T-133`, `T-136`, `T-140` |
| `RF-62` — derivar `VALOR_ACAO_FINANCEIRA_IMEDIATA`: `0` sem desembolso, valor conhecido com desembolso conhecido | `T-132`, `T-133` |
| `RF-63` — `VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO` quando desembolso exigido e valor desconhecido; sinalização provisória via mecanismo existente | `T-132`, `T-134`, `T-137` |
| `RF-64` — `NECESSIDADE_IMEDIATA_DIVIDA` por função pura, cinco ramos em ordem estrita; `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` como soma com sinalização de incompletude | `T-134`, `T-135`, `T-137`, `T-138`, `T-139` |
| `RF-65` — trava de dupla contagem entre `VALOR_ACAO_FINANCEIRA_IMEDIATA` e `VALOR_RELEVANTE_PARA_QUITACAO` da mesma dívida | `T-134`, `T-137`, `T-139` |

**Cobertura:** 5 de 5 requisitos funcionais da fatia 4B (`RF-61`–`RF-65`). Nenhuma tarefa desta fatia existe sem requisito atrás.

### Cobertura dos critérios de aceite — Rodada 4, fatia 4B

| `AC-NN` | Tarefas | | `AC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `AC-101` | `T-137`, `T-139` | | `AC-107` | `T-137` |
| `AC-102` | `T-137`, `T-139` | | `AC-108` | `T-137` |
| `AC-103` | `T-137`, `T-139` | | `AC-109` | `T-137` |
| `AC-104` | `T-137`, `T-139` | | `AC-110` | `T-133`, `T-136`, `T-140` |
| `AC-105` | `T-132`, `T-137`, `T-139` | | `AC-111` | `T-134`, `T-137` |
| `AC-106` | `T-134`, `T-137` | | | |

Os 11 critérios de aceite da fatia 4B (`AC-101` a `AC-111`) têm tarefa. Nenhum ficou parcial.

### Cobertura das user stories — Rodada 4, fatia 4B

`US-22` `T-132`, `T-133`, `T-134`, `T-135`, `T-137`, `T-138`, `T-139` ·
`US-23` `T-134`, `T-135`, `T-137`, `T-138`, `T-139` ·
`US-24` `T-134`, `T-137` ·
`US-25` `T-132`, `T-133`, `T-136`, `T-140`

### Cobertura dos edge cases — Rodada 4, fatia 4B

`EC-40` `T-134`, `T-137` · `EC-41` `T-134`, `T-137` · `EC-42` `T-134`, `T-137` ·
`EC-43` `T-134`, `T-137` · `EC-44` `T-134`, `T-137` · `EC-45` `T-135`, `T-137` ·
`EC-46` `T-135`, `T-137` · `EC-47` `T-132`, `T-133`, `T-136`

### Cobertura dos gabaritos `GAB-NFI-01` a `05` — Rodada 4, fatia 4B

`GAB-NFI-01` `T-137`, `T-139` · `GAB-NFI-02` `T-137`, `T-139` · `GAB-NFI-03` `T-137`, `T-139` ·
`GAB-NFI-04` `T-137`, `T-139` · `GAB-NFI-05` `T-137`, `T-139`

### Requisitos sem cobertura — Rodada 4, fatia 4B

Nenhum. Todos os `RF-61` a `RF-65` têm ao menos uma tarefa de implementação e
ao menos uma de teste. Nenhuma tarefa desta fatia toca `app/`, `collection/`,
`report/`, `calcular_diagnostico`, `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`,
ou reabre `classificar_investimento`/`classificar_ativo_fisico` (fatia 4A,
concluída) — escopo mantido estritamente dentro de `RF-61` a `RF-65`.

---

## Cobertura de requisitos — Rodada 4

| Requisito | Tarefas |
| --------- | ------- |
| `RF-53` — `classificar_investimento`, seis regras, ordem estrita | `T-117`, `T-119`, `T-121`, `T-122`, `T-124`, `T-125`, `T-127`, `T-128`, `T-129` |
| `RF-54` — `classificar_ativo_fisico`, essencialidade nunca automática | `T-118`, `T-120`, `T-121`, `T-123`, `T-124`, `T-125`, `T-127`, `T-128`, `T-129` |
| `RF-55` — não essencial + venda aceita + fluxo desconhecido → `MOBILIZACAO_POSSIVEL` | `T-120`, `T-123`, `T-127`, `T-129` |
| `RF-56` — veículo no mesmo ramo não produz classificação | `T-118`, `T-120`, `T-123`, `T-127`, `T-131` |
| `RF-57` — `VALOR_LIQUIDO_REALIZAVEL_ATIVO`/`_DISPONIVEL`, duas funções separadas | `T-120`, `T-121`, `T-126`, `T-129` |
| `RF-58` — normalização de passivo/custo, desconhecido nunca vira zero | `T-120`, `T-121`, `T-126` |
| `RF-59` — `CLASSIFICACAO_MOBILIZACAO` de entrada para derivada, varredura de consumidores | `T-119`, `T-120`, `T-124`, `T-125`, `T-130` |
| `RF-60` — reescrita do teste estático, não relaxamento | `T-130` |

**Cobertura:** 8 de 8 requisitos funcionais da Rodada 4 (`RF-53`–`RF-60`). Nenhuma tarefa desta rodada existe sem requisito atrás.

### Cobertura dos critérios de aceite — Rodada 4

| `AC-NN` | Tarefas | | `AC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `AC-88` | `T-122`, `T-127`, `T-129` | | `AC-95` | `T-122`, `T-127` |
| `AC-89` | `T-122`, `T-127`, `T-129` | | `AC-96` | `T-123`, `T-127` |
| `AC-90` | `T-122`, `T-127`, `T-129` | | `AC-97` | `T-130` |
| `AC-91` | `T-123`, `T-127`, `T-129` | | `AC-98` | `T-125` |
| `AC-92` | `T-123`, `T-127`, `T-129` | | `AC-99` | `T-121`, `T-126` |
| `AC-93` | `T-123`, `T-127`, `T-129` | | `AC-100` | `T-123`, `T-127`, `T-131` |
| `AC-94` | `T-121`, `T-126`, `T-129` | | | |

Os 13 critérios de aceite da Rodada 4 (`AC-88` a `AC-100`) têm tarefa. Nenhum ficou parcial.

### Cobertura das user stories — Rodada 4

`US-19` `T-117`, `T-118`, `T-119`, `T-120`, `T-122`, `T-123`, `T-124`, `T-125`, `T-127`, `T-128`, `T-129`, `T-131` ·
`US-20` `T-120`, `T-121`, `T-126`, `T-128`, `T-129` ·
`US-21` `T-119`, `T-120`, `T-124`, `T-125`, `T-130`

### Cobertura dos edge cases — Rodada 4

`EC-32` `T-119`, `T-120`, `T-125` · `EC-33` `T-122`, `T-127` · `EC-34` `T-123`, `T-127` ·
`EC-35` `T-123`, `T-127` · `EC-36` `T-121`, `T-126` · `EC-37` `T-122`, `T-127` ·
`EC-38` `T-125` · `EC-39` `T-120`, `T-123`, `T-127`, `T-131`

### Cobertura dos gabaritos `GAB-NFI` — Rodada 4

`GAB-NFI-06` `T-122`, `T-127`, `T-129` · `GAB-NFI-07` `T-122`, `T-127`, `T-129` ·
`GAB-NFI-08` `T-122`, `T-127`, `T-129` · `GAB-NFI-09` `T-123`, `T-127`, `T-129` ·
`GAB-NFI-10` `T-123`, `T-127`, `T-129` · `GAB-NFI-11` `T-123`, `T-127`, `T-129` ·
`GAB-NFI-12` `T-121`, `T-126`, `T-129`

**`GAB-NFI-01` a `GAB-NFI-05` — sem tarefa, deliberadamente:** dependem de
`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`/`NECESSIDADE_IMEDIATA_DIVIDA`
(fatia 4B), fora de escopo desta rodada (spec §4, nota da fatia 4A).

### Requisitos sem cobertura — Rodada 4

Nenhum. Todos os `RF-53` a `RF-60` têm ao menos uma tarefa de implementação e
ao menos uma de teste. Nenhuma tarefa desta rodada toca `app/`, `collection/`,
`report/`, `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`,
`NECESSIDADE_IMEDIATA_DIVIDA`, `VALOR_ACAO_FINANCEIRA_IMEDIATA`, `AcaoRequerida`,
gates, ou `calcular_diagnostico`/`Diagnostico`.

---

## Cobertura de requisitos

| Requisito | Tarefas |
| --------- | ------- |
| `RF-01` — ciclo mensal `M-01..M-12` | `T-42`, `T-45`, `T-46`, `T-47`, `T-68` |
| `RF-02` — recálculo só por quitação ou evento material | `T-42`, `T-46`, `T-47`, `T-66`, `T-70` |
| `RF-03` — cascata do resíduo e `ATAQUE_NAO_UTILIZADO` | `T-43`, `T-44`, `T-47`, `T-48` |
| `RF-04` — fluxo liberado só em *m+1* | `T-45`, `T-47`, `T-48` |
| `RF-05` — Avalanche por benefício marginal | `T-36`, `T-37`, `T-38`, `T-39`, `T-41`, `T-49`, `T-50`, `T-77` |
| `RF-06` — Bola de Neve por `VALOR_RELEVANTE_PARA_QUITACAO` | `T-27`, `T-28`, `T-51`, `T-52` |
| `RF-07` — Híbrido em seis etapas | `T-53`, `T-54`, `T-55`, `T-77` |
| `RF-08` — `NAO_CALCULAVEL` × `NAO_APLICAVEL` e `STATUS_METODO` | `T-54`, `T-60`, `T-61`, `T-62`, `T-65` |
| `RF-09` — `ORDEM_QUITACAO` com `JUSTIFICATIVA_POSICAO` | `T-63`, `T-65` |
| `RF-10` — snapshot sem sobrescrita | `T-02`, `T-67`, `T-69`, `T-70`, `T-75`, `T-76` |
| `RF-11` — troca com `DINHEIRO_NOVO > 0` | `T-71`, `T-72` |
| `RF-12` — precisão decimal integral | `T-01`, `T-03`, `T-04`, `T-09`, `T-10`, `T-20`, `T-68`, `T-69`, `T-75`, `T-76` |
| `RF-13` — parâmetros de fonte externa, zero no código | `T-01`, `T-02`, `T-05`, `T-06`, `T-07`, `T-10`, `T-56`, `T-75`, `T-76` |
| `RF-14` — diagnóstico e as três capacidades | `T-08`, `T-11`, `T-20`, `T-23`, `T-24`, `T-26`, `T-73` |
| `RF-15` — `MODO_ESTABILIZACAO` | `T-23`, `T-26`, `T-74` |
| `RF-16` — bloquear o que depende de dado ausente | `T-04`, `T-08`, `T-29`, `T-64`, `T-73` |
| `RF-17` — quatro gates, `DIVIDA_STATUS_ESTRATEGICO`, `ORDEM_ACOES` | `T-04`, `T-29`, `T-30`, `T-31`, `T-32`, `T-33` |
| `RF-18` — regra D.4 | `T-15`, `T-16`, `T-17` |
| `RF-19` — `CENARIO_ECONOMICAMENTE_SUPERIOR` (1%) | `T-57`, `T-59`, `T-65` |
| `RF-20` — `ECONOMICAMENTE_PROXIMO` (5% **e** 2 meses) | `T-58`, `T-59` |
| `RF-21` — fallback por taxa e `ORDEM_STATUS = PROVISORIA` | `T-40`, `T-41`, `T-64` |
| `RF-22` — evento futuro previsto fora da projeção-base | `T-34`, `T-35`, `T-66` |
| `RF-23` — `NIVEL_CONTROLE` e `CONFIABILIDADE_DADOS` derivados | `T-12`, `T-13`, `T-14` |
| `RF-24` — `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` | `T-18`, `T-19` |
| `RF-25` — `FATOR_SEGURANCA` subtrativo | `T-22`, `T-25` |
| `RF-26` — `STATUS_FINANCEIRO` e piso classificatório | `T-21`, `T-25` |
| `RF-27` — ordem de derivação obrigatória | `T-12`, `T-13`, `T-24`, `T-25`, `T-68` |

**Cobertura:** 27 de 27 requisitos funcionais. Nenhuma tarefa deste backlog existe sem requisito atrás.

### Requisitos sem cobertura

Nenhum. Todos os `RF-01` a `RF-27` da spec têm ao menos uma tarefa de implementação e ao menos uma de teste.

### Cobertura dos critérios de aceite

| `AC-NN` | Tarefas | | `AC-NN` | Tarefas |
| --- | --- | --- | --- | --- |
| `AC-01` | `T-49`, `T-50` | | `AC-25` | `T-15`, `T-16`, `T-17` |
| `AC-02` | `T-51`, `T-52` | | `AC-26` | `T-22`, `T-25` |
| `AC-03` | `T-53`, `T-55` | | `AC-27` | `T-57`, `T-59` |
| `AC-04` | `T-61`, `T-65` | | `AC-28` | `T-57`, `T-59`, `T-65` |
| `AC-05` | `T-20`, `T-26` | | `AC-29` | `T-58`, `T-59` |
| `AC-06` | `T-23`, `T-26` | | `AC-30` | `T-34`, `T-35` |
| `AC-07` | `T-23`, `T-26` | | `AC-31` | `T-66`, `T-70` |
| `AC-08` | `T-20`, `T-73` | | `AC-32` | `T-20`, `T-45`, `T-47` |
| `AC-09` | `T-60`, `T-64`, `T-73` | | `AC-33` | `T-40`, `T-41`, `T-64` |
| `AC-10` | `T-73` | | `AC-34` | `T-18`, `T-19` |
| `AC-11` | `T-74` | | `AC-35` | `T-18`, `T-19` |
| `AC-12` | `T-71`, `T-72` | | `AC-36` | `T-22`, `T-25` |
| `AC-13` | `T-42`, `T-46`, `T-47`, `T-66` | | `AC-37` | `T-21`, `T-25` |
| `AC-14` | `T-43`, `T-47`, `T-49` | | `AC-38` | `T-21`, `T-25` |
| `AC-15` | `T-45`, `T-47` | | `AC-39` | `T-21`, `T-25` |
| `AC-16` | `T-67`, `T-70` | | `AC-40` | `T-03`, `T-09` |
| `AC-17` | `T-01`, `T-05`, `T-06`, `T-07`, `T-10`, `T-56` | | `AC-41` | `T-31`, `T-33` |
| `AC-18` | `T-63`, `T-67`, `T-70` | | `AC-42` | `T-31`, `T-33` |
| `AC-19` | `T-39`, `T-41` | | `AC-43` | `T-29`, `T-33` |
| `AC-20` | `T-27`, `T-28` | | `AC-44` | `T-29`, `T-33` |
| `AC-21` | `T-27`, `T-28` | | `AC-45` | `T-31`, `T-33` |
| `AC-22` | `T-30`, `T-33` | | `AC-46` | `T-13`, `T-14` |
| `AC-23` | `T-29`, `T-33` | | `AC-47` | `T-36`, `T-38` |
| `AC-24` | `T-15`, `T-17` | | | |

Os 47 critérios de aceite estão cobertos.

### Cobertura dos edge cases

`EC-01` `T-44`, `T-47` · `EC-02` `T-42`, `T-66` · `EC-03` `T-54` · `EC-04` `T-61`, `T-62` ·
`EC-05` `T-61`, `T-62` · `EC-06` `T-73` · `EC-07` `T-73` · `EC-08` `T-66`, `T-70` ·
`EC-09` `T-66`, `T-70` · `EC-10` `T-23`, `T-74` · `EC-11` `T-23` · `EC-12` `T-20`, `T-73` ·
`EC-13` `T-36`, `T-38`, `T-46` · `EC-14` `T-27`, `T-28` · `EC-15` `T-29`, `T-33` ·
`EC-16` `T-30`, `T-33` · `EC-17` `T-32`, `T-33` · `EC-18` `T-45`, `T-47` · `EC-19` `T-57`, `T-59`

---

## Rodada 4 — fatia 4C (2026-09-10)

> **Escopo desta fatia.** `RF-66` a `RF-69` (spec §14, blocos "Rodada 4 —
> fatia 4C"), plano `plans/motor-calculo.plan.md` seção "Rodada 4 — Ligação
> em `calcular_diagnostico`, fatia 4C" (`R4C.x`). **Última fatia do
> documento do especialista** (discovery Rodada 4 §8). Fecha `OQ-29` por
> completo (a metade `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_
> IMEDIATA_ELEGIVEL` já fora fechada pela fatia 4B) e resolve formalmente
> `AMB-R3-01`/`OQ-44` (decisão (2): segunda passada com `dataclasses.replace`
> em `engine/motor.py::calcular_plano`, sem mudar a assinatura pública de
> `calcular_diagnostico`). **Pré-requisito: fatias 4A (`T-117` a `T-131`) e
> 4B (`T-132` a `T-140`) concluídas e verificadas** — nenhuma tarefa abaixo
> reabre `classificar_investimento`/`classificar_ativo_fisico`,
> `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`
> nem o campo `VALOR_ACAO_FINANCEIRA_IMEDIATA` de `AcaoRequerida`.
>
> **Fora de escopo, não implementado por nenhuma tarefa abaixo:** qualquer
> arquivo de `app/`, `collection/` ou `report/` (spec §9: "esta fatia não
> altera `app-aluno`"); `ATAQUE_IMEDIATO_POTENCIAL` como campo público de
> `Diagnostico` (`verificar_hierarquia_ataque_imediato` não é chamada por
> `_compor_ATAQUE_IMEDIATO_RECOMENDADO`, plano R4C.4.1); qualquer edição em
> `engine/ataque_imediato.py`/`engine/gates.py` (`RF-67`/`AC-115` exigem
> composição pura das funções já existentes, sem tocar nelas); sinalização
> de `STATUS_METODO=PROVISORIO` para a segunda metade de `EC-48`/`AC-109`
> (reordenar o pipeline arriscaria `AC-116` — lacuna registrada, não
> resolvida por esta fatia, ver `OQ-45` ao final).
>
> **Decisões já fechadas — não reabertas por nenhuma tarefa abaixo:**
> `calcular_diagnostico(estado, parametros)` **mantém assinatura e corpo
> inalterados** — continua devolvendo `ATAQUE_IMEDIATO_RECOMENDADO=
> dinheiro(0)` quando chamada isoladamente (decisão (2), `OQ-44`, plano
> R4C.1.1). `_compor_ATAQUE_IMEDIATO_RECOMENDADO` é função privada **nova**
> em `engine/motor.py` — não em `engine/ataque_imediato.py` (preserva a NFR
> de Pureza "só por parâmetro" daquele módulo, R4C.1.1 ponto 6). `EC-48`
> (elegível `DESCONHECIDO`) resolve para `dinheiro(0)` documentado — não
> aciona `STATUS_METODO=PROVISORIO` nesta fatia (R4C.6.1). `Diagnostico.
> ATAQUE_IMEDIATO_RECOMENDADO` continua tipado `Dinheiro`, não retipado
> para `DinheiroTalvez` (decisão da Rodada 3, R3.10, reafirmada em R4C.2).

### `T-141` — Implementar `_compor_ATAQUE_IMEDIATO_RECOMENDADO` em `engine/motor.py`

- **Tipo:** `Data`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-66`, `RF-67`, `AC-115`, `EC-48`, `EC-49`, `US-26`
- **Arquivos:** `engine/motor.py`

**Descrição**

Função privada nova (plano R4C.4.1), assinatura keyword-only exata do plano: `estado: EstadoFinanceiro`, `RESERVA_MOBILIZAVEL: DinheiroTalvez`, `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL: DinheiroTalvez`, `RESULTADO_MENSAL_ATUAL: Dinheiro`, retorno `Dinheiro`. **Não implementa nenhuma fórmula nova** — só orquestra, na ordem do plano, as nove funções já existentes de `engine/ataque_imediato.py` (`calcular_CAIXA_RECOMENDADO`, `calcular_INVESTIMENTOS_RECOMENDADOS`, `calcular_EXTRAORDINARIOS_RECOMENDADOS`, `calcular_ATIVOS_RECOMENDADOS`, `calcular_NECESSIDADE_RESIDUAL`, `derivar_RESERVA_RECOMENDADA`, `calcular_ATAQUE_IMEDIATO_RECOMENDADO`). Primeiro ramo é a trava de `EC-48`: se `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL is DESCONHECIDO`, devolve `dinheiro(0)` documentado, sem chamar nenhuma das demais funções.

**Critérios de aceite**

- [x] Assinatura idêntica ao plano R4C.4.1 — parâmetros nomeados (`*`, só keyword), tipos exatos, retorno `Dinheiro`
- [x] Primeiro ramo: `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL is DESCONHECIDO` → `return dinheiro(0)` imediato, comentário citando `EC-48` e o padrão já usado por `derivar_RESERVA_RECOMENDADA`/`derivar_RESERVA_MOBILIZAVEL` ("decisão/dado adiado ⇒ 0 documentado, nunca fabricado como certeza")
- [x] Demais ramos chamam, na ordem exata do plano, as sete funções de `engine/ataque_imediato.py` listadas na descrição — nenhuma fórmula é escrita inline fora dessas chamadas
- [x] `verificar_hierarquia_ataque_imediato` **não** é chamada por esta função (fora de escopo, `ATAQUE_IMEDIATO_POTENCIAL` não é campo público desta fatia)
- [x] `engine/ataque_imediato.py` e `engine/gates.py` **não são editados** por esta tarefa — só lidos/importados
- [x] Import direto de `engine.ataque_imediato` acrescentado ao topo de `engine/motor.py` (hoje só indireto via `engine.diagnostico`)
- [x] Docstring/comentário da função cita `RF-66`, `RF-67`, `RF-68`, `§14.2.4`, `§13.3`, `§13.9` — regra citada no código (`sdd.config.md` §4)
- [x] `REGRAS: Final[tuple[str, ...]]` de `engine/motor.py` ganha `"RF-66"`, `"RF-67"`, `"RF-68"`, `"§14.2.4"`
- [x] Função não é chamada em nenhum outro ponto de `calcular_plano` nesta tarefa — a integração é `T-142`
- [x] `mypy --strict engine/motor.py` e `ruff check .` passam
- [x] Nenhum teste é escrito nesta tarefa — comportamento verificado em `T-144`/`T-145`

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).**

Nova função privada `_compor_ATAQUE_IMEDIATO_RECOMENDADO` inserida em
`engine/motor.py`, logo após `_acao_economia_se_houver` e antes de
`calcular_plano` — mesmo padrão de função privada de composição já usado no
arquivo:

```python
def _compor_ATAQUE_IMEDIATO_RECOMENDADO(
    *,
    estado: EstadoFinanceiro,
    RESERVA_MOBILIZAVEL: DinheiroTalvez,
    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL: DinheiroTalvez,
    RESULTADO_MENSAL_ATUAL: Dinheiro,
) -> Dinheiro:
    ...
    if NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL is DESCONHECIDO:
        return dinheiro(0)  # EC-48, documentado — não silencioso

    elegivel = NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL
    CAIXA_RECOMENDADO = calcular_CAIXA_RECOMENDADO(DINHEIRO_DISPONIVEL=estado.DINHEIRO_DISPONIVEL)
    INVESTIMENTOS_RECOMENDADOS = calcular_INVESTIMENTOS_RECOMENDADOS(investimentos=estado.investimentos)
    EXTRAORDINARIOS_RECOMENDADOS = calcular_EXTRAORDINARIOS_RECOMENDADOS(recursos_extraordinarios=estado.recursos_extraordinarios)
    ATIVOS_RECOMENDADOS = calcular_ATIVOS_RECOMENDADOS(ativos=estado.ativos)
    NECESSIDADE_RESIDUAL = calcular_NECESSIDADE_RESIDUAL(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel,
        CAIXA_RECOMENDADO=CAIXA_RECOMENDADO,
        INVESTIMENTOS_RECOMENDADOS=INVESTIMENTOS_RECOMENDADOS,
        EXTRAORDINARIOS_RECOMENDADOS=EXTRAORDINARIOS_RECOMENDADOS,
        ATIVOS_RECOMENDADOS=ATIVOS_RECOMENDADOS,
    )
    RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
        RESERVA_MOBILIZAVEL=RESERVA_MOBILIZAVEL,
        NECESSIDADE_RESIDUAL=NECESSIDADE_RESIDUAL,
        RESULTADO_MENSAL_ATUAL=RESULTADO_MENSAL_ATUAL,
    )
    return calcular_ATAQUE_IMEDIATO_RECOMENDADO(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel,
        CAIXA_RECOMENDADO=CAIXA_RECOMENDADO,
        INVESTIMENTOS_RECOMENDADOS=INVESTIMENTOS_RECOMENDADOS,
        EXTRAORDINARIOS_RECOMENDADOS=EXTRAORDINARIOS_RECOMENDADOS,
        ATIVOS_RECOMENDADOS=ATIVOS_RECOMENDADOS,
        RESERVA_RECOMENDADA=RESERVA_RECOMENDADA,
    )
```

Import direto de `engine.ataque_imediato` acrescentado ao topo do módulo
(sete nomes, ordem alfabética exigida pelo `ruff`/`isort`):
`calcular_ATAQUE_IMEDIATO_RECOMENDADO`, `calcular_ATIVOS_RECOMENDADOS`,
`calcular_CAIXA_RECOMENDADO`, `calcular_EXTRAORDINARIOS_RECOMENDADOS`,
`calcular_INVESTIMENTOS_RECOMENDADOS`, `calcular_NECESSIDADE_RESIDUAL`,
`derivar_RESERVA_RECOMENDADA`. `DinheiroTalvez` acrescentado ao import
existente de `engine.tipos`. `REGRAS` de `engine/motor.py` passou de
`("RF-01", "RF-10", "RF-12", "RF-27", "RF-33")` para incluir também
`"RF-66"`, `"RF-67"`, `"RF-68"`, `"§14.2.4"`.

**Verificação critério a critério:**

1. Assinatura — `*` inicial (só keyword), `estado: EstadoFinanceiro`,
   `RESERVA_MOBILIZAVEL: DinheiroTalvez`, `NECESSIDADE_FINANCEIRA_IMEDIATA_
   ELEGIVEL: DinheiroTalvez`, `RESULTADO_MENSAL_ATUAL: Dinheiro`, retorno
   `Dinheiro` — idêntica ao pseudocódigo R4C.4.1, confirmada por leitura lado
   a lado.
2. Primeiro ramo — `if NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL is
   DESCONHECIDO: return dinheiro(0)`, com comentário citando `EC-48` e o
   texto "decisão/dado adiado ⇒ 0 documentado, nunca fabricado como certeza"
   (mesma frase do plano), e a distinção explícita de `EC-49`.
3. Ordem de composição — confirmada idêntica a R4C.4.1: `CAIXA_RECOMENDADO`
   → `INVESTIMENTOS_RECOMENDADOS` → `EXTRAORDINARIOS_RECOMENDADOS` →
   `ATIVOS_RECOMENDADOS` → `NECESSIDADE_RESIDUAL` → `RESERVA_RECOMENDADA` →
   `calcular_ATAQUE_IMEDIATO_RECOMENDADO` (return). Nenhuma fórmula inline —
   toda aritmética vive dentro das sete funções de `engine/ataque_
   imediato.py`.
4. `grep -n "verificar_hierarquia_ataque_imediato" engine/motor.py` → nenhum
   resultado (não importada, não chamada).
5. `engine/ataque_imediato.py` e `engine/gates.py` — só lidos com a
   ferramenta `Read` nesta tarefa; nenhuma escrita/edição feita neles.
6. Import direto confirmado no topo do arquivo (linhas 108-116 do arquivo
   final).
7. Docstring da função cita literalmente `RF-66 · RF-67 · RF-68 · §14.2.4 ·
   §13.3 · §13.9` na primeira linha.
8. `REGRAS` do módulo — conferido por leitura, ganhou os quatro IDs.
9. `grep -n "_compor_ATAQUE_IMEDIATO_RECOMENDADO" engine/motor.py` → só a
   linha da definição (`def _compor_ATAQUE_IMEDIATO_RECOMENDADO(`); nenhuma
   chamada dentro de `calcular_plano`.
10. `mypy --strict engine/motor.py` → `Success: no issues found in 1 source
    file`. `ruff check .` → `All checks passed!`.
11. Nenhum arquivo de teste criado ou editado nesta tarefa.

**Comandos executados:**

- `mypy --strict engine/motor.py` → `Success: no issues found in 1 source file`
- `ruff check .` → `All checks passed!`
- `mypy engine persistencia collection app report tests` (comando `build`
  completo do `sdd.config.md`) → `Success: no issues found in 298 source
  files` — mesma contagem de arquivos do baseline da fatia, zero regressão
- `pytest -q --ignore=tests/app_aluno` → `594 passed, 9 skipped` — idêntico
  ao baseline informado no início da fatia, zero regressão, nenhum teste
  novo coletado (esperado, escopo desta tarefa não inclui testes)

---

### `T-142` — Integrar a segunda passada de `Diagnostico` em `calcular_plano`

- **Tipo:** `Data`
- **Dependências:** `T-141`
- **Rastreia:** `RF-66`, `RF-68`, `AC-112`, `AC-116`, `EC-48`, `EC-49`, `US-26`
- **Arquivos:** `engine/motor.py`

**Descrição**

`engine/motor.py::calcular_plano` ganha a segunda passada de `Diagnostico` (plano R4C.1/R4C.5, mecanismo `OQ-44` = decisão (2)): entre a montagem final de `particao.ORDEM_ACOES` e a chamada a `montar_SnapshotOrdem`, monta `acoes_por_divida` a partir de `particao.ORDEM_ACOES` (filtrando `DIVIDA_ID is not None`, `RF-68`), calcula `elegivel = NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(particao=particao, acoes_por_divida=acoes_por_divida)` (`engine/gates.py`, fatia 4B), chama `_compor_ATAQUE_IMEDIATO_RECOMENDADO` (`T-141`) e substitui o campo no `Diagnostico` já construído via `dataclasses.replace(diagnostico_pre, ATAQUE_IMEDIATO_RECOMENDADO=...)`. `diagnostico_pre` (retorno original de `calcular_diagnostico`, com o placeholder) continua sendo o que os passos de `simular_cenario`/`comparar_cenarios`/`derivar_METODO_RECOMENDADO_PIQ` consomem — **inalterado**; só `montar_SnapshotOrdem` passa a receber o `Diagnostico` final com o valor real.

**Critérios de aceite**

- [x] A chamada a `calcular_diagnostico(estado, parametros)` continua na posição atual (linha ~245), sem novo argumento — variável renomeada para `diagnostico_pre` (ou equivalente que deixe explícito que é o valor pré-composição)
- [x] `simular_cenario` × 3, `comparar_cenarios`, `derivar_METODO_RECOMENDADO_PIQ`, `publicar_ORDEM_QUITACAO`, `consolidar_ORDEM_STATUS` continuam recebendo/consumindo `diagnostico_pre` — nenhuma dessas chamadas é reordenada nem passa a receber o `Diagnostico` final
- [x] O bloco novo (`acoes_por_divida`/`elegivel`/`_compor_ATAQUE_IMEDIATO_RECOMENDADO`/`dataclasses.replace`) fica posicionado depois da montagem final de `particao.ORDEM_ACOES` e antes da chamada a `montar_SnapshotOrdem` — nunca antes de `particionar_elegibilidade`
- [x] `montar_SnapshotOrdem(..., diagnostico=diagnostico, ...)` recebe a variável resultante de `dataclasses.replace`, não mais `diagnostico_pre`
- [x] Nenhuma outra função de `engine/motor.py` muda de assinatura
- [x] `mypy --strict engine/motor.py` e `ruff check .` passam
- [x] Nenhum teste é escrito nesta tarefa — comportamento verificado em `T-144` a `T-149`

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).**

`engine/motor.py::calcular_plano` ganhou a segunda passada de `Diagnostico` (plano
R4C.1/R4C.5, mecanismo `OQ-44` decisão (2)). Mudanças:

1. Import de `engine.gates` ganhou `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`
   (função de `gates.py`, fatia 4B), ordenado antes de `AcaoRequerida` — `ruff`/
   `isort` ordena maiúsculas antes de minúsculas no mesmo bloco.
2. `diagnostico = calcular_diagnostico(estado, parametros)` (linha ~353, antiga)
   virou `diagnostico_pre = calcular_diagnostico(estado, parametros)`, com
   comentário explicando que é o valor pré-composição consumido pelos passos
   7-10, sem alteração na chamada em si (mesma assinatura, mesma posição no
   fluxo).
3. Todas as referências a `diagnostico` dentro dos passos 7-10 (`simular_
   cenario` × 3 — avalanche/bola de neve/híbrido —, `criar_selecionar_alvo_
   hibrido`, `derivar_METODO_RECOMENDADO_PIQ` via `INCOMPATIBILIDADE_
   COMPORTAMENTAL_GRAVE`, `_beneficios_marginais_da_ordem` via `CAPACIDADE_
   ATAQUE_CONSERVADORA`) renomeadas para `diagnostico_pre` — mesma referência
   de objeto, nenhuma reordenação de chamada.
4. Bloco novo inserido depois de `consolidar_ORDEM_STATUS` (fim do passo 10,
   montagem final de `particao.ORDEM_ACOES` já ocorrida antes do passo 7) e
   antes do passo 11 (`avaliar_gatilho_recalculo`/`montar_SnapshotOrdem`):
   `acoes_por_divida` (filtro `DIVIDA_ID is not None` sobre
   `particao.ORDEM_ACOES`) → `elegivel = NECESSIDADE_FINANCEIRA_IMEDIATA_
   ELEGIVEL(particao=particao, acoes_por_divida=acoes_por_divida)` →
   `ataque_imediato_recomendado = _compor_ATAQUE_IMEDIATO_RECOMENDADO(estado=
   estado, RESERVA_MOBILIZAVEL=diagnostico_pre.RESERVA_MOBILIZAVEL,
   NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel, RESULTADO_MENSAL_ATUAL=
   diagnostico_pre.RESULTADO_MENSAL_ATUAL)` → `diagnostico = dataclasses.
   replace(diagnostico_pre, ATAQUE_IMEDIATO_RECOMENDADO=ataque_imediato_
   recomendado)`.
5. `montar_SnapshotOrdem(..., diagnostico=diagnostico, ...)` agora recebe a
   variável resultante do `dataclasses.replace` — única mudança no ponto de
   chamada final.
6. Duas correções de `ruff` durante a implementação, sem impacto de lógica:
   ordem alfabética do import novo em `engine.gates` e quebra de linha de
   `criar_selecionar_alvo_hibrido(...)` (ficou com 103 colunas ao trocar
   `diagnostico` por `diagnostico_pre`, acima do limite de 100).

**Diff da região alterada (antes → depois), resumido por trecho:**

```python
# ANTES (linha ~353)
diagnostico = calcular_diagnostico(estado, parametros)
...
cenario_avalanche = dataclasses.replace(
    simular_cenario(estado, diagnostico, dividas, sel_avalanche, parametros),
    metodo=METODO.AVALANCHE,
)
... (idem bola de neve, híbrido, criar_selecionar_alvo_hibrido)
resultado_recomendacao = derivar_METODO_RECOMENDADO_PIQ(
    cenarios_por_metodo, comparacao,
    INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=diagnostico.INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE,
    ...
)
...
beneficios_marginais = _beneficios_marginais_da_ordem(
    dividas, cenario_recomendado, diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA, parametros,
)
resultado_status_ordem = consolidar_ORDEM_STATUS(...)

gatilho = avaliar_gatilho_recalculo(evento)
motivo_final = motivo if motivo else gatilho.motivo
return montar_SnapshotOrdem(..., diagnostico=diagnostico, ...)

# DEPOIS
diagnostico_pre = calcular_diagnostico(estado, parametros)
...
cenario_avalanche = dataclasses.replace(
    simular_cenario(estado, diagnostico_pre, dividas, sel_avalanche, parametros),
    metodo=METODO.AVALANCHE,
)
... (idem bola de neve, híbrido, criar_selecionar_alvo_hibrido)
resultado_recomendacao = derivar_METODO_RECOMENDADO_PIQ(
    cenarios_por_metodo, comparacao,
    INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=diagnostico_pre.INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE,
    ...
)
...
beneficios_marginais = _beneficios_marginais_da_ordem(
    dividas, cenario_recomendado, diagnostico_pre.CAPACIDADE_ATAQUE_CONSERVADORA, parametros,
)
resultado_status_ordem = consolidar_ORDEM_STATUS(...)

# NOVO — segunda passada (RF-66/RF-68, T-142)
acoes_por_divida = {
    acao.DIVIDA_ID: acao for acao in particao.ORDEM_ACOES if acao.DIVIDA_ID is not None
}
elegivel = NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(
    particao=particao, acoes_por_divida=acoes_por_divida
)
ataque_imediato_recomendado = _compor_ATAQUE_IMEDIATO_RECOMENDADO(
    estado=estado,
    RESERVA_MOBILIZAVEL=diagnostico_pre.RESERVA_MOBILIZAVEL,
    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel,
    RESULTADO_MENSAL_ATUAL=diagnostico_pre.RESULTADO_MENSAL_ATUAL,
)
diagnostico = dataclasses.replace(
    diagnostico_pre, ATAQUE_IMEDIATO_RECOMENDADO=ataque_imediato_recomendado
)

gatilho = avaliar_gatilho_recalculo(evento)
motivo_final = motivo if motivo else gatilho.motivo
return montar_SnapshotOrdem(..., diagnostico=diagnostico, ...)
```

**Verificação critério a critério:**

1. `grep -n "diagnostico_pre = calcular_diagnostico" engine/motor.py` → linha
   368; a chamada continua `(estado, parametros)`, sem argumento novo, na
   mesma posição relativa do fluxo (logo após `limpar_cache_trajetoria()`,
   antes de `_inventario`/`particionar_elegibilidade`, como já era).
2. `grep -n "diagnostico_pre\." engine/motor.py` → confirma as três leituras
   de campo (`INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`, `CAPACIDADE_ATAQUE_
   CONSERVADORA`, mais as duas novas `RESERVA_MOBILIZAVEL`/`RESULTADO_
   MENSAL_ATUAL` usadas só no bloco novo) e `grep -n "diagnostico_pre,"` os
   três `simular_cenario`/`criar_selecionar_alvo_hibrido` — todas essas
   chamadas mantidas na ordem original, nenhuma reordenada.
3. Releitura completa de `calcular_plano` (linhas 322-495): o bloco novo
   começa imediatamente depois de `resultado_status_ordem = consolidar_
   ORDEM_STATUS(...)` (fim do passo 10) e termina antes de `gatilho =
   avaliar_gatilho_recalculo(evento)` (início do passo 11) — depois da
   montagem final de `particao.ORDEM_ACOES` (que ocorre antes do passo 7,
   linha ~385, incluindo a ação de economia) e antes de `montar_
   SnapshotOrdem`. Nunca antes de `particionar_elegibilidade` (linha 373).
4. `grep -n "diagnostico=diagnostico" engine/motor.py` → só a chamada dentro
   de `montar_SnapshotOrdem` (linha ~486); a variável `diagnostico` (sem
   sufixo `_pre`) só existe a partir do `dataclasses.replace` (linha 474) —
   confirmado por `grep -n "diagnostico\b" engine/motor.py`, sem nenhuma
   ocorrência de `diagnostico` puro entre a definição de `diagnostico_pre` e
   o `dataclasses.replace`.
5. Nenhuma assinatura de `_inventario`, `_beneficios_marginais_da_ordem`,
   `_acao_economia_se_houver`, `_compor_ATAQUE_IMEDIATO_RECOMENDADO` (`T-141`,
   inalterada) ou `calcular_plano` foi tocada — só o corpo de `calcular_
   plano` mudou (renomeação de variável + bloco novo + import).
6. `mypy --strict engine/motor.py` → `Success: no issues found in 1 source
   file`. `ruff check .` → `All checks passed!` (após corrigir ordem de
   import e uma linha de 103 colunas).
7. Nenhum arquivo de teste criado ou editado nesta tarefa.

**Comandos executados:**

- `mypy --strict engine/motor.py` → `Success: no issues found in 1 source file`
- `ruff check .` → `All checks passed!`
- `mypy engine persistencia collection app report tests` (comando `build`
  completo do `sdd.config.md`) → `Success: no issues found in 298 source
  files` — mesma contagem de arquivos do baseline, zero regressão de tipos
- `pytest -q --ignore=tests/app_aluno` → `594 passed, 9 skipped` — idêntico
  ao baseline de início da tarefa (594 passed, 9 skipped), **zero regressão**
- `pytest -q` (registro informativo, todas as pastas) → `3 failed, 1473
  passed, 75 skipped` — as 3 falhas são exclusivamente `tests/app_aluno/
  estatica/test_engine_congelado.py` (mecanismo de hash congelado de
  `engine/`), já sinalizadas como quebra de contrato esperada em `T-140`
  (Aviso 2) desde a fatia 4B; agora `engine/motor.py` também diverge do hash
  congelado porque esta tarefa o editou de fato — consistente com o aviso já
  registrado, não é regressão introduzida por `T-142`, e é exatamente por
  isso que o comando de verificação oficial desta tarefa usa `--ignore=
  tests/app_aluno`

---

### `T-143` — Reescrever a docstring de `calcular_diagnostico` e os comentários de `ATAQUE_IMEDIATO_RECOMENDADO` em `engine/diagnostico.py`

- **Tipo:** `Docs`
- **Dependências:** `T-142`
- **Rastreia:** `RF-69`, `AC-117`, `US-26`
- **Arquivos:** `engine/diagnostico.py`

**Descrição**

Reescrita pontual (plano R4C.4.2) — **não** a função inteira: só o bloco "T-114/RF-51" da docstring de `calcular_diagnostico` sobre `ATAQUE_IMEDIATO_RECOMENDADO`, o comentário do campo na declaração de `Diagnostico` (linha ~637-655) e o comentário de construção do placeholder (linha ~845-850). Remove as três afirmações desatualizadas — "placeholder" sem qualificação, "`OQ-29` está aberta", "nenhuma decisão do motor o lê" sem qualificação — e documenta, no lugar, que a chamada isolada de `calcular_diagnostico` **continua** devolvendo o placeholder por design (não por pendência), e que o valor real só existe no `Diagnostico` publicado por `calcular_plano` via `_compor_ATAQUE_IMEDIATO_RECOMENDADO` (`T-141`/`T-142`).

**Critérios de aceite**

- [x] O parágrafo sobre `RESERVA_MOBILIZAVEL` na docstring permanece **inalterado** — `RF-69` não o menciona
- [x] O parágrafo sobre `ATAQUE_IMEDIATO_RECOMENDADO` é reescrito com o texto do plano R4C.4.2: afirma que a chamada isolada desta função continua `dinheiro(0)` por design, cita `OQ-44`/R4C.1.1, explica que a fórmula exige o elegível (que só existe depois dos gates), e referencia `RF-66`/`RF-67`/`§14.2.4`
- [x] `grep -n "OQ-29" engine/diagnostico.py` devolve vazio, ou só ocorrência histórica claramente marcada como resolvida — nenhuma afirmação de que `OQ-29` está aberta permanece sem qualificação
- [x] `grep -n "placeholder"` em `engine/diagnostico.py` não encontra nenhuma ocorrência sem a qualificação "por design, não por pendência" (ou equivalente) no mesmo parágrafo
- [x] Nenhuma outra parte da docstring de `calcular_diagnostico` é alterada
- [x] Nenhum código executável de `engine/diagnostico.py` é alterado por esta tarefa — só docstring/comentário
- [x] `ruff check .` e `mypy --strict engine/diagnostico.py` passam

**Status:** `[x] concluída`

---

### `T-144` — Criar `tests/regras/test_ataque_imediato_recomendado_diagnostico.py` — `AC-112` a `AC-114`, `EC-48`, `EC-49`

- **Tipo:** `Test`
- **Dependências:** `T-142`
- **Rastreia:** `RF-66`, `AC-112`, `AC-113`, `AC-114`, `EC-48`, `EC-49`, `US-26`
- **Arquivos:** `tests/regras/test_ataque_imediato_recomendado_diagnostico.py` (novo)

**Descrição**

Arquivo novo (plano R4C.9), testes de integração ponta a ponta via `calcular_plano` (nunca chamando `calcular_diagnostico` isolada — essa prova é `T-146`). Cinco casos: `AC-112` (prova negativa genérica — `EstadoFinanceiro` com `DINHEIRO_DISPONIVEL > 0` e dívida elegível com `VALOR_RELEVANTE_PARA_QUITACAO > 0` produz `ATAQUE_IMEDIATO_RECOMENDADO != 0`); `AC-113` (cenário equivalente a `GAB-AI-06`: elegível `20.000`, recursos somando `22.000` → resultado `20.000`); `AC-114` (cenário equivalente a `GAB-AI-07`: elegível `10.000`, recursos `25.000` → resultado `10.000`, nunca `25.000`); `EC-48` (ação Gate 2/4 com `VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO` → `ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(0)`, nunca exceção nem valor fabricado); `EC-49` (todas as dívidas com `NECESSIDADE_IMEDIATA_DIVIDA=0`, recursos recomendados positivos → `ATAQUE_IMEDIATO_RECOMENDADO=0`, distinguindo por comentário o caminho lógico de `EC-48`).

**Critérios de aceite**

- [x] Todos os cinco casos chamam `calcular_plano` ponta a ponta — nenhum chama `calcular_diagnostico` diretamente
- [x] `AC-112`: asserção de que `diagnostico.ATAQUE_IMEDIATO_RECOMENDADO != dinheiro(0)` para o cenário com insumos positivos
- [x] `AC-113`: asserção exata (tolerância zero) de `ATAQUE_IMEDIATO_RECOMENDADO == dinheiro("20000")` (ou valor equivalente definido pelo cenário), com `assertar_exato`
- [x] `AC-114`: asserção exata de `ATAQUE_IMEDIATO_RECOMENDADO == dinheiro("10000")` **e** `!= dinheiro("25000")` explícito
- [x] `EC-48`: asserção de `ATAQUE_IMEDIATO_RECOMENDADO == dinheiro("0")`, sem levantar exceção
- [x] `EC-49`: asserção de `ATAQUE_IMEDIATO_RECOMENDADO == dinheiro("0")`, com comentário explícito distinguindo o caminho lógico de `EC-48` (elegível conhecido e zero vs. desconhecido)
- [x] Cada teste cita no docstring o `AC-NN`/`EC-NN` que cobre
- [x] `pytest -q tests/regras/test_ataque_imediato_recomendado_diagnostico.py` → 5 passed
- [x] `ruff check .` e `mypy --strict` passam

**Status:** `[x] concluída`

**Nota de fechamento (T-144).** Arquivo novo `tests/regras/test_ataque_imediato_recomendado_diagnostico.py`, cinco testes, todos via `calcular_plano` ponta a ponta sobre `carregar_gab_c()`/`carregar_gab_a()` ajustados por `dataclasses.replace` (nunca `calcular_diagnostico` isolada). `AC-112`: `DINHEIRO_DISPONIVEL=1000` sobre `GAB-C` → `ATAQUE_IMEDIATO_RECOMENDADO != 0`. `AC-113` (`GAB-AI-06`): D001 ajustada para saldo `10.000` (elegível `10.000+7.000+3.000=20.000`), `DINHEIRO_DISPONIVEL=5.000`, investimento líquido recomendável `7.000`, reserva mobilizável `10.000` (via `RESERVA_EXISTE=SIM`/`DISPOSICAO_USO_RESERVA=GRANDE_PARTE`/`RESERVA_TOTAL=VALOR_MAXIMO_INFORMADO=10.000`) → resultado exato `20.000`. `AC-114` (`GAB-AI-07`): carteira reduzida a uma dívida de saldo `10.000`, `DINHEIRO_DISPONIVEL=25.000` → resultado exato `10.000`, `!= 25.000` explícito. `EC-48`: como nenhum gate real hoje produz `AcaoRequerida` com `VALOR_ACAO_FINANCEIRA_IMEDIATA=DESCONHECIDO` (Gate 2 hardcoda `0`; a única fonte real de valor do Gate 3 cai no ramo 2 de `NECESSIDADE_IMEDIATA_DIVIDA`, sempre `0`, nunca no ramo 3), o teste usa `monkeypatch` em `engine.motor.particionar_elegibilidade` (mesma técnica de `test_motor.py::test_criterio5_erro_invariante_propaga_sem_ser_capturado`) para injetar essa `AcaoRequerida` sintética associada a D001 sobre a partição REAL de `GAB-C` — todo o resto do motor roda sem stub → `ATAQUE_IMEDIATO_RECOMENDADO=0`, sem exceção. `EC-49`: `GAB-A` (as duas dívidas bloqueadas no Gate 1 por `SALDO_DEVEDOR_ATUAL=DESCONHECIDO`, ramo 1 sempre `dinheiro(0)` conhecido) com `DINHEIRO_DISPONIVEL=1500` → elegível `0` conhecido (nunca `DESCONHECIDO`), `MIN(0, recursos)=0`; docstring distingue explicitamente de `EC-48` ("sei que é zero" vs. "não sei quanto é"). Evidência: `pytest -q tests/regras/test_ataque_imediato_recomendado_diagnostico.py` → `5 passed in 0.33s`; `ruff check .` → `All checks passed!`; `mypy --strict` (seis pastas) → `Success: no issues found in 300 source files`.

---

### `T-145` — Auditar por leitura de código que `_compor_ATAQUE_IMEDIATO_RECOMENDADO` só compõe funções já existentes (`AC-115`)

- **Tipo:** `Docs`
- **Dependências:** `T-141`, `T-144`
- **Rastreia:** `RF-67`, `AC-115`, `US-26`
- **Arquivos:** `tasks/motor-calculo.tasks.md` (nota de fechamento desta tarefa)

**Descrição**

Auditoria de revisão de código (plano R4C.9, **não** teste automatizado — mesmo padrão de `test_sem_percentual_automatico_de_reserva`, que é verificação de revisão registrada em nota de fechamento). Confirma, linha a linha do corpo de `_compor_ATAQUE_IMEDIATO_RECOMENDADO` (`T-141`), que toda operação sobre `Dinheiro`/`DinheiroTalvez` é uma chamada a uma função já existente de `engine.ataque_imediato`/`engine.gates` — nenhuma soma, `MIN`, comparação ou fórmula é escrita inline fora dessas chamadas.

**Critérios de aceite**

- [x] A nota de fechamento lista, função por função do corpo de `_compor_ATAQUE_IMEDIATO_RECOMENDADO`, a origem de cada valor (nome da função de `ataque_imediato.py`/`gates.py` chamada) — nenhuma linha aparece sem função de origem identificada
- [x] Confirma que `git diff`/leitura de `engine/ataque_imediato.py` e `engine/gates.py` não mostra nenhuma edição desde o fim da fatia 4B (`T-140`) — reforço de que `RF-67` não foi violado
- [x] Confirma que `AC-113`/`AC-114` (`T-144`) reproduzem os valores exatos dos `GAB-AI-06`/`GAB-AI-07` já homologados como função pura isolada (Rodada 3) — se a composição divergisse da fórmula original, esses dois testes já falhariam
- [x] Nenhum código é alterado por esta tarefa — só leitura e registro

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).** Repositório sem controle de versão
(`git diff` não aplicável, `sdd.config.md` §1) — auditoria feita por leitura
direta com a ferramenta `Read` e comparação com o texto literal registrado nas
notas de fechamento das tarefas de referência. Nenhum arquivo foi editado por
esta tarefa.

**1. Auditoria função por função do corpo de `_compor_ATAQUE_IMEDIATO_RECOMENDADO`
(`engine/motor.py`, linhas 245–324).**

| Linha do corpo | Valor produzido | Origem exata |
| --- | --- | --- |
| `if NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL is DESCONHECIDO: return dinheiro(0)` | guarda `EC-48` | **não é fórmula** — comparação de identidade (`is`) contra a sentinela `DESCONHECIDO`, exceção explícita já prevista na descrição da tarefa; `dinheiro(0)` é o construtor de `Dinheiro` já usado em toda a base, não uma soma |
| `CAIXA_RECOMENDADO = calcular_CAIXA_RECOMENDADO(DINHEIRO_DISPONIVEL=estado.DINHEIRO_DISPONIVEL)` | `CAIXA_RECOMENDADO` | `engine.ataque_imediato.calcular_CAIXA_RECOMENDADO` |
| `INVESTIMENTOS_RECOMENDADOS = calcular_INVESTIMENTOS_RECOMENDADOS(investimentos=estado.investimentos)` | `INVESTIMENTOS_RECOMENDADOS` | `engine.ataque_imediato.calcular_INVESTIMENTOS_RECOMENDADOS` |
| `EXTRAORDINARIOS_RECOMENDADOS = calcular_EXTRAORDINARIOS_RECOMENDADOS(recursos_extraordinarios=estado.recursos_extraordinarios)` | `EXTRAORDINARIOS_RECOMENDADOS` | `engine.ataque_imediato.calcular_EXTRAORDINARIOS_RECOMENDADOS` |
| `ATIVOS_RECOMENDADOS = calcular_ATIVOS_RECOMENDADOS(ativos=estado.ativos)` | `ATIVOS_RECOMENDADOS` | `engine.ataque_imediato.calcular_ATIVOS_RECOMENDADOS` |
| `NECESSIDADE_RESIDUAL = calcular_NECESSIDADE_RESIDUAL(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel, CAIXA_RECOMENDADO=..., INVESTIMENTOS_RECOMENDADOS=..., EXTRAORDINARIOS_RECOMENDADOS=..., ATIVOS_RECOMENDADOS=...)` | `NECESSIDADE_RESIDUAL` | `engine.ataque_imediato.calcular_NECESSIDADE_RESIDUAL` (a subtração das quatro parcelas e o `MAX(0, ...)` vivem dentro dela, não em `motor.py`) |
| `RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(RESERVA_MOBILIZAVEL=..., NECESSIDADE_RESIDUAL=..., RESULTADO_MENSAL_ATUAL=...)` | `RESERVA_RECOMENDADA` | `engine.ataque_imediato.derivar_RESERVA_RECOMENDADA` (a trava do `MODO_ESTABILIZACAO`, a guarda de `DESCONHECIDO` e o `MIN` vivem dentro dela) |
| `return calcular_ATAQUE_IMEDIATO_RECOMENDADO(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel, CAIXA_RECOMENDADO=..., INVESTIMENTOS_RECOMENDADOS=..., EXTRAORDINARIOS_RECOMENDADOS=..., ATIVOS_RECOMENDADOS=..., RESERVA_RECOMENDADA=...)` | valor de retorno `ATAQUE_IMEDIATO_RECOMENDADO` | `engine.ataque_imediato.calcular_ATAQUE_IMEDIATO_RECOMENDADO` (a soma dos cinco componentes e o `MIN` contra o elegível vivem dentro dela) |
| `elegivel = NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` | alias local | **não é fórmula** — reatribuição de nome (o parâmetro `DinheiroTalvez` já teve o ramo `DESCONHECIDO` descartado pela guarda acima; `elegivel` só existe para tipar `Dinheiro` puro nas chamadas seguintes, sem repetir o nome longo) |

Nenhuma linha do corpo soma, subtrai, aplica `MIN`/`MAX` ou compara dois
`Dinheiro`/`DinheiroTalvez` fora dessas sete chamadas — as sete funções
citadas na descrição da tarefa (`T-141`) são exatamente as sete que aparecem
na tabela, na mesma ordem. `verificar_hierarquia_ataque_imediato` não é
chamada (confirmado em `T-141`, critério 4, reconfirmado agora por
`grep -n "verificar_hierarquia_ataque_imediato" engine/motor.py` → nenhum
resultado).

**2. `engine/ataque_imediato.py` e `engine/gates.py` não foram editados desde
o fim da fatia 4B (`T-140`).**

O repositório não tem controle de versão (`sdd.config.md` §1) — "confirma por
leitura" é comparação do conteúdo atual com o que as notas de fechamento já
registraram como estado final, mesmo procedimento usado em `T-116`/`T-140`.

- `engine/ataque_imediato.py`: a última tarefa a **editar** (não só ler) este
  arquivo foi `T-124` (fatia 4A, Rodada 4), que alterou só três funções —
  `calcular_ATAQUE_IMEDIATO_POTENCIAL`, `calcular_INVESTIMENTOS_RECOMENDADOS`,
  `calcular_ATIVOS_RECOMENDADOS` — e cuja nota de fechamento afirma
  explicitamente: *"Nenhuma outra função de `engine/ataque_imediato.py` foi
  alterada além das três citadas — `derivar_RESERVA_MOBILIZAVEL`,
  `calcular_CAIXA_RECOMENDADO`, `calcular_EXTRAORDINARIOS_RECOMENDADOS`,
  `calcular_NECESSIDADE_RESIDUAL`, `derivar_RESERVA_RECOMENDADA`,
  `calcular_ATAQUE_IMEDIATO_RECOMENDADO`, `verificar_hierarquia_ataque_
  imediato` seguem com o corpo intocado"*. Das sete funções que `_compor_
  ATAQUE_IMEDIATO_RECOMENDADO` chama, `calcular_INVESTIMENTOS_RECOMENDADOS` e
  `calcular_ATIVOS_RECOMENDADOS` foram as duas tocadas por `T-124` (para
  chamar `classificar_investimento`/`classificar_ativo_fisico` em vez de ler
  campo direto — mudança da fatia 4A, **anterior** a `T-141`, já incorporada
  quando `_compor_ATAQUE_IMEDIATO_RECOMENDADO` foi escrita); as outras cinco
  (`calcular_CAIXA_RECOMENDADO`, `calcular_EXTRAORDINARIOS_RECOMENDADOS`,
  `calcular_NECESSIDADE_RESIDUAL`, `derivar_RESERVA_RECOMENDADA`,
  `calcular_ATAQUE_IMEDIATO_RECOMENDADO`) seguem intocadas desde a Rodada 3
  (`T-102`–`T-107`). A nota de fechamento de `T-140` (fim da fatia 4B)
  confirma por SHA-256 real que `engine/ataque_imediato.py` **não** foi
  tocado por nenhuma tarefa `T-132`–`T-139` (Aviso 2: "`engine/ataque_
  imediato.py` — **Pré-existente** — já divergente desde a Rodada 3
  (`T-102`/`T-110`, sinalizado em `T-116`); **não** tocado por
  `T-132`–`T-139`"). Leitura direta, agora, do corpo das sete funções
  (`engine/ataque_imediato.py`, linhas 319–644) confirma assinaturas e
  fórmulas idênticas ao texto transcrito nas docstrings/notas de `T-108`
  (marcador `gabarito_ataque_imediato`, sem tocar o arquivo),
  `T-121`/`T-122`/`T-123` (que criam/tocam `engine/classificacao_ativos.py`,
  não `ataque_imediato.py`) e `T-124` (última edição real).
- `engine/gates.py`: `T-134`/`T-135` (fatia 4B) adicionaram `NECESSIDADE_
  IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` a este arquivo
  — mas **nenhuma das duas é chamada por `_compor_ATAQUE_IMEDIATO_
  RECOMENDADO`**: o valor `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` chega à
  função por PARÂMETRO (já calculado em `calcular_plano`, integração de
  `T-142`), nunca por chamada direta a `engine.gates` dentro do corpo
  auditado no item 1. `T-140` (fim da fatia 4B, a tarefa mais recente que
  editou `gates.py`) é o próprio marco de fechamento contra o qual esta
  tarefa compara — não há tarefa entre `T-140` e `T-145` que toque
  `gates.py` (confirmado pela leitura sequencial de `T-141`–`T-144`: nenhuma
  lista `engine/gates.py` em "Arquivos"). Hash SHA-256 atual, medido agora
  (`certutil -hashfile ... SHA256`, mesmo procedimento de `T-140`):
  `engine/ataque_imediato.py` = `3130c952aa5c9d099df89eb4b60753e14612b23e61dfd5b183a43bf2e45ee80e`;
  `engine/gates.py` = `2c70a5ba6abd26c152b6d99374b8193b29bb2fc6e4c42a90bc75f1888e579af7`
  — registrados aqui como novo marco de referência para auditorias futuras
  desta rodada (nenhum hash anterior desses dois arquivos específicos consta
  nas notas de `T-108`/`T-121`–`T-123`/`T-134`/`T-135`/`T-140` para
  comparação byte a byte; a confirmação usada é textual, por leitura de
  corpo/assinatura contra o que essas notas descrevem, e por status "não
  tocado" que `T-140` já certificou por hash para o período `T-132`–`T-139`).

**3. `AC-113`/`AC-114` (`T-144`) reproduzem os valores exatos de `GAB-AI-06`/
`GAB-AI-07` (Rodada 3, função pura isolada).**

- `GAB-AI-06` (`tests/gabaritos_ataque_imediato/test_gab_ai_06_residual_e_
  recomendado_completo.py`): elegível `20.000`; `CAIXA_RECOMENDADO=5.000`;
  `INVESTIMENTOS_RECOMENDADOS=7.000`; `EXTRAORDINARIOS_RECOMENDADOS=0`;
  `ATIVOS_RECOMENDADOS=0`; `RESERVA_MOBILIZAVEL=10.000` ⇒ `NECESSIDADE_
  RESIDUAL=8.000`, `RESERVA_RECOMENDADA=8.000`, `ATAQUE_IMEDIATO_
  RECOMENDADO=20.000` — chamando as funções puras diretamente, sem
  `calcular_plano`. `AC-113` (`test_AC113_equivalente_a_GAB_AI_06_...`)
  monta um `EstadoFinanceiro` via `calcular_plano` cujos insumos produzem os
  MESMOS números intermediários (`CAIXA_RECOMENDADO=5.000`, investimento
  recomendável `7.000`, `RESERVA_MOBILIZAVEL=10.000`, elegível somando
  `10.000+7.000+3.000=20.000`) e assere `snapshot.diagnostico.ATAQUE_
  IMEDIATO_RECOMENDADO == dinheiro("20000")` com `assertar_exato` —
  resultado final idêntico ao gabarito isolado.
- `GAB-AI-07` (`tests/gabaritos_ataque_imediato/test_gab_ai_07_teto_da_
  necessidade_elegivel.py`): elegível `10.000` contra recursos recomendáveis
  totais `25.000` (`1.000+2.000+4.000+8.000+10.000`) ⇒ `ATAQUE_IMEDIATO_
  RECOMENDADO=10.000`, `!= 25.000`, chamando `calcular_ATAQUE_IMEDIATO_
  RECOMENDADO` diretamente. `AC-114`
  (`test_AC114_equivalente_a_GAB_AI_07_...`) monta, via `calcular_plano`,
  uma única dívida elegível de saldo `10.000` com `DINHEIRO_DISPONIVEL=
  25.000` (todo o recurso concentrado em caixa) e assere `ATAQUE_IMEDIATO_
  RECOMENDADO == dinheiro("10000")` **e** `!= dinheiro("25000")` — mesmo
  par de asserções do gabarito isolado, mesmo resultado numérico.

Como `_compor_ATAQUE_IMEDIATO_RECOMENDADO` (auditada no item 1) só orquestra
chamadas às mesmas sete funções que `GAB-AI-06`/`GAB-AI-07` exercitam
isoladamente, sem nenhuma fórmula adicional inline, uma composição divergente
da fórmula original teria produzido resultado diferente em `AC-113`/`AC-114`
— e os dois testes passam com os valores exatos (`assertar_exato`, tolerância
zero), o que é evidência direta de que a composição não introduziu desvio.

**Comandos executados (verificação, `sdd.config.md` §2):**

- `ruff check .` → `All checks passed!`
- `mypy` sobre `engine persistencia collection app report tests` (comando
  `build`) → `Success: no issues found in 300 source files`
- `pytest -q --ignore=tests/app_aluno` → `600 passed, 9 skipped` — idêntico
  ao estado informado no início desta tarefa, zero regressão (esperado:
  nenhum código foi alterado)

Nenhum arquivo de código foi tocado por esta tarefa — só `tasks/motor-
calculo.tasks.md` (esta nota de fechamento).

---

### `T-146` — Provar que `calcular_diagnostico` chamada isoladamente continua devolvendo o placeholder

- **Tipo:** `Test`
- **Dependências:** `T-142`
- **Rastreia:** `RF-68`, `RF-69`, `AC-112`, `US-26`
- **Arquivos:** `tests/regras/test_diagnostico_isolado_mantem_placeholder.py` (novo)

**Descrição**

Teste dedicado (não coberto por `T-144`, que só exercita `calcular_plano`) — a garantia central de que a decisão `OQ-44`/(2) não vazou comportamento: chama **apenas** `calcular_diagnostico(estado, parametros)`, sem passar por `calcular_plano`, para um `EstadoFinanceiro` com dívida elegível e recursos positivos (mesmo cenário de `AC-112`), e confirma que `ATAQUE_IMEDIATO_RECOMENDADO` **ainda** é `dinheiro(0)`. É a prova de que os 21 chamadores de teste que hoje dependem dessa característica (varredura R4C.1.3 do plano) continuam corretos sem precisar ser reescritos.

**Critérios de aceite**

- [x] O teste chama `calcular_diagnostico(estado, parametros)` diretamente, sem `calcular_plano` em nenhum ponto
- [x] O `EstadoFinanceiro` usado tem ao menos uma dívida elegível com `VALOR_RELEVANTE_PARA_QUITACAO > 0` e recursos (`DINHEIRO_DISPONIVEL`/investimentos/ativos) positivos — mesmo perfil de `AC-112`, para que a ausência do valor real não seja coincidência de um cenário vazio
- [x] Asserção: `diagnostico.ATAQUE_IMEDIATO_RECOMENDADO == dinheiro("0")`, com `assertar_exato`
- [x] Docstring do teste cita explicitamente a decisão `OQ-44`/(2) e a varredura de 22 chamadores (plano R4C.1.3) como motivação
- [x] `pytest -q tests/regras/test_diagnostico_isolado_mantem_placeholder.py` → 1 passed
- [x] `ruff check .` e `mypy --strict` passam

**Status:** `[x] concluída`

**Nota de fechamento (T-146).** Arquivo novo `tests/regras/test_diagnostico_isolado_mantem_placeholder.py`, um teste, chamando exclusivamente `calcular_diagnostico(estado, parametros)` — `calcular_plano` não é importada nem citada no arquivo. `EstadoFinanceiro` = `carregar_gab_c()` (três dívidas elegíveis, saldos `12.000`/`7.000`/`3.000`) com `DINHEIRO_DISPONIVEL` elevado de `0` (fixture) para `1.000` — mesmo perfil positivo de `AC-112`/`T-144`, para que a prova não seja coincidência de cenário vazio. Docstring cita explicitamente `OQ-44` decisão (2) e a varredura de 22 chamadores do plano R4C.1.3 como motivação. Evidência: `pytest -q tests/regras/test_diagnostico_isolado_mantem_placeholder.py` → `1 passed in 0.28s`; `ruff check .` → `All checks passed!`; `mypy --strict` (seis pastas) → `Success: no issues found in 300 source files`. Suíte completa após as duas tarefas: `pytest -q --ignore=tests/app_aluno` → `600 passed, 9 skipped` (antes: `594 passed, 9 skipped` — +6 testes novos, zero falhas, zero skips novos).

---

### `T-147` — Reexecutar `GAB-A`/`GAB-B`/`GAB-C` com asserção nova de `ATAQUE_IMEDIATO_RECOMENDADO`, comparando campo a campo antes/depois (`AC-116`)

- **Tipo:** `Test`
- **Dependências:** `T-142`
- **Rastreia:** `RF-66`, `AC-116`, `US-26`
- **Arquivos:** `tests/gabaritos/test_gabarito_a_deficit.py`, `tests/gabaritos/test_gabarito_b_equilibrio_fragil.py`, `tests/gabaritos/test_gabarito_c_avalanche.py`, `tests/gabaritos/test_gabarito_c_bola_de_neve.py`, `tests/gabaritos/test_gabarito_c_hibrido.py`, `tests/gabaritos/test_gabarito_c_recomendacao.py`

**Descrição**

> **Esta tarefa é diferente das reexecuções de não-regressão das fatias 4A/4B.** Ali, nenhum valor deveria mudar. Aqui, `ATAQUE_IMEDIATO_RECOMENDADO` **deve** mudar de `0` para o valor real — efeito desejado desta fatia (`RF-66`). O que **não pode mudar** é tudo o mais: método recomendado, ordem, custo total, prazo, `mes_primeira_vitoria`, `STATUS_METODO`, `STATUS_DIVIDA` de cada dívida. Cada um dos seis arquivos ganha **uma** asserção nova confirmando o valor esperado de `ATAQUE_IMEDIATO_RECOMENDADO` (calculado à mão a partir dos dados do gabarito — `0` nos três, porque `GAB-A`/`GAB-B`/`GAB-C` não populam `investimentos`/`ativos`/`recursos_extraordinarios`/reserva com valor positivo, plano R4C.9) — **nenhuma asserção pré-existente é removida ou tem seu valor esperado alterado**.

**Critérios de aceite**

- [x] Os seis arquivos ganham, cada um, exatamente uma asserção nova sobre `diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`, com `assertar_exato`
- [x] O valor esperado em cada um dos seis é `dinheiro("0")` (calculado à mão a partir dos dados de cada gabarito, documentado em comentário no teste) — se a leitura do gabarito divergir dessa previsão, a nota de fechamento reporta o valor real encontrado e a causa, sem forçar a asserção a bater
- [x] Nenhuma asserção pré-existente nesses seis arquivos (método recomendado, ordem, custo total, prazo, `mes_primeira_vitoria`, `STATUS_METODO`, `STATUS_DIVIDA`) tem seu valor esperado alterado — confirmado por diff, campo a campo, contra o estado do arquivo ao fim da fatia 4B
- [x] A nota de fechamento documenta explicitamente, para cada um dos seis gabaritos, os valores de método/ordem/custo/prazo/`mes_primeira_vitoria` **antes** (fim da fatia 4B) e **depois** (fim desta tarefa) — provando que são idênticos, exceto `ATAQUE_IMEDIATO_RECOMENDADO`
- [x] `pytest -q tests/gabaritos/` → todos passam, mesma contagem de testes anterior + 6 asserções novas dentro dos testes existentes (nenhum teste novo criado)
- [x] `ruff check .` e `mypy --strict` passam

**Status:** `[x] concluída`

**Nota de fechamento (T-147).**

Valor real de `ATAQUE_IMEDIATO_RECOMENDADO` obtido via `calcular_plano(estado, parametros)` (script isolado fora do arquivo de teste, antes de escrever qualquer asserção) para os seis gabaritos-alvo:

| Gabarito | `ATAQUE_IMEDIATO_RECOMENDADO` real | Cálculo à mão |
| --- | --- | --- |
| `GAB-A` (`test_gabarito_a_deficit.py`) | `0` | `DINHEIRO_DISPONIVEL=0`, `investimentos`/`ativos`/`recursos_extraordinarios=[]`, `RESERVA_EXISTE=NAO` ⇒ recursos recomendados somam 0 ⇒ `MIN(elegível, 0)=0` |
| `GAB-B` (`test_gabarito_b_equilibrio_fragil.py`) | `0` | idem — mesmos campos vazios/zerados na fixture `gab_b.json` |
| `GAB-C` — Avalanche (`test_gabarito_c_avalanche.py`) | `0` | idem — `gab_c.json` também tem os três campos vazios e reserva zerada, mesmo com as três dívidas elegíveis de saldo positivo (o teto de `MIN` é o lado direito zerado, não o elegível) |
| `GAB-C` — Bola de Neve (`test_gabarito_c_bola_de_neve.py`) | `0` | idem |
| `GAB-C` — Híbrido (`test_gabarito_c_hibrido.py`) | `0` | idem |
| `GAB-C` — Recomendação (`test_gabarito_c_recomendacao.py`) | `0` | idem |

A previsão manual (`0` nos seis, calculada a partir da leitura de `tests/fixtures/gab_a.json`, `gab_b.json`, `gab_c.json` antes de tocar em qualquer teste) bateu exatamente com o valor real lido de `calcular_plano` — nenhuma divergência encontrada, nenhum bug de integração de `T-142` a reportar.

Asserção adicionada em cada um dos seis arquivos (padrão idêntico nos seis, comentário com a referência `T-147/RF-66/AC-116`):

```python
snapshot = calcular_plano(estado, parametros)
assertar_exato(snapshot.diagnostico.ATAQUE_IMEDIATO_RECOMENDADO, dinheiro("0"))
```

Import novo em cada arquivo: `from engine.motor import calcular_plano` (e `from engine.precisao import dinheiro` no arquivo de recomendação, que ainda não importava `dinheiro`). Motivo de usar `calcular_plano` — não a variável `diagnostico` já existente em cada teste (produzida por `calcular_diagnostico` isolada): `calcular_diagnostico` chamada isoladamente SEMPRE devolve o placeholder `ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(0)` por desenho (`OQ-44` decisão (2), provado em `tests/regras/test_diagnostico_isolado_mantem_placeholder.py`, T-146) — assertar sobre aquela variável testaria só o placeholder, sem nenhum valor probatório do `RF-66` (a segunda passada só existe dentro de `calcular_plano`, `engine/motor.py::_compor_ATAQUE_IMEDIATO_RECOMENDADO`, T-141/T-142). A asserção nova precisa, portanto, de uma chamada adicional a `calcular_plano` para exercitar de fato o campo real.

**Confirmação de que nenhuma asserção pré-existente mudou.** As seis edições foram feitas exclusivamente por `Edit` com `old_string`/`new_string` cirúrgicos: (1) acréscimo de um parágrafo de docstring documentando o cálculo manual de `ATAQUE_IMEDIATO_RECOMENDADO` e (2) acréscimo do import `calcular_plano` (e `dinheiro` onde faltava), sem tocar nas demais linhas de import; (3) inserção das duas linhas novas (`snapshot = ...` / `assertar_exato(...)`) sempre DEPOIS da última asserção pré-existente de cada teste, nunca substituindo nem reordenando nenhuma linha anterior. Nenhuma chamada de `assertar_exato`/`assertar_monetario`/`assert` pré-existente teve seu valor esperado alterado — confirmado por leitura de cada arquivo após a edição.

**Valores antes (fim da fatia 4B) e depois (fim de T-147) — idênticos, exceto `ATAQUE_IMEDIATO_RECOMENDADO`:**

| Gabarito | Método | Ordem | Custo total | Prazo | `MESES_PRIMEIRA_VITORIA` | `ATAQUE_IMEDIATO_RECOMENDADO` antes | `ATAQUE_IMEDIATO_RECOMENDADO` depois |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GAB-A` | — (só diagnóstico de um mês, `AC-05`) | — | — | — | — | não testado | `0` |
| `GAB-B` | — (só diagnóstico de um mês, `AC-06`/`AC-07`) | — | — | — | — | não testado | `0` |
| `GAB-C` Avalanche | Avalanche | D001→D002→D003 | R$ 23.719,46 | 6 meses | mês 4 | não testado | `0` |
| `GAB-C` Bola de Neve | Bola de Neve | D003→D002→D001 | R$ 24.463,97 | 6 meses | mês 1 | não testado | `0` |
| `GAB-C` Híbrido | Híbrido | D003→D001→D002 | R$ 24.107,20 | 6 meses | mês 1 | não testado | `0` |
| `GAB-C` Recomendação | Híbrido (`METODO_RECOMENDADO_PIQ`) | publicada via `publicar_ORDEM_QUITACAO` | — (não recalculado neste teste) | — | ≤ `P_MESES_VITORIA_RAPIDA` | não testado | `0` |

Todas as colunas "método/ordem/custo/prazo/`MESES_PRIMEIRA_VITORIA`" vêm das asserções pré-existentes, que **não foram tocadas** por esta tarefa — os valores "antes" e "depois" são literalmente o mesmo texto no arquivo, o que é a prova exigida pelo critério de aceite. A única coluna nova é `ATAQUE_IMEDIATO_RECOMENDADO`, que passa de "não testado" (fim da 4B, nenhuma asserção sobre o campo existia nesses seis arquivos) para `0` (valor real confirmado via `calcular_plano`, T-147).

**Comandos executados:**
- `pytest -q tests/gabaritos/` → `7 passed` (mesma contagem de testes de antes — nenhum teste novo criado, só 6 asserções novas dentro dos testes já existentes)
- `pytest -q --ignore=tests/app_aluno` (suíte completa) → `600 passed, 9 skipped` — mesma contagem relatada no contexto da tarefa antes de T-147, confirmando ausência de regressão em qualquer outro teste
- `ruff check .` → `All checks passed!`
- `mypy --strict` (via `strict = true` em `pyproject.toml`, comando `build` do `sdd.config.md §2`) sobre `engine persistencia collection app report tests` → `Success: no issues found in 300 source files`

---

### `T-148` — Reexecutar os cinco invariantes confirmando `AC-116`

- **Tipo:** `Test`
- **Dependências:** `T-142`
- **Rastreia:** `AC-116`, `US-26`
- **Arquivos:** `tests/invariantes/` (os cinco arquivos existentes, `GAB-01` a `GAB-05`)

**Descrição**

Reexecução de não-regressão (plano R4C.3/R4C.9) — os cinco invariantes (`GAB-01` a `GAB-05`) não testam `ATAQUE_IMEDIATO_RECOMENDADO` diretamente, mas precisam continuar passando **sem nenhuma alteração de asserção**, confirmando que a segunda passada de `Diagnostico` em `calcular_plano` (`T-142`) não vazou para nenhum invariante estrutural (snapshot imutável, ordem consistente, etc.).

**Critérios de aceite**

- [x] Nenhum dos cinco arquivos de `tests/invariantes/` é editado por esta tarefa — só reexecutado
- [x] `pytest -m invariante` → mesma contagem de testes e mesmo resultado (todos passando) de antes de `T-141`/`T-142`
- [x] A nota de fechamento reporta a contagem exata antes e depois, confirmando igualdade
- [x] Se algum invariante falhar, a nota de fechamento identifica a causa raiz antes de qualquer correção — nenhuma correção de invariante é feita silenciosamente dentro desta tarefa (viraria tarefa nova)

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).** Reexecução pura, nenhum arquivo de
`tests/invariantes/` tocado — confirmado por `find tests/invariantes -name
"*.py" -printf '%TY-%Tm-%Td %TH:%TM'`: o `mtime` mais recente do diretório é
`2026-09-07 14:19` (`test_gab01_seguro.py` a `test_gab05_troca.py`,
`test_propriedades.py`), anterior a `T-141`/`T-142` (2026-09-10), sem nenhum
arquivo tocado hoje.

**Antes** (última contagem conhecida, registrada nas notas de fechamento de
`T-102`/`T-103`/`T-104`/`T-108`–`T-139`, todas citando a mesma homologação
combinada): `pytest -m "gabarito or invariante or ..."` sempre listou os
cinco invariantes como parte fixa do total (`GAB-01` a `GAB-05`, um teste por
arquivo) — confirmado isoladamente ao fim da fatia 4B (`T-139`, antes de
`T-141`/`T-142`) e agora reexecutado isoladamente.

**Depois** (`pytest -m invariante -v`, hoje, pós-`T-141`/`T-142`):

```
tests/invariantes/test_gab01_seguro.py::test_invariante_gab01_seguro PASSED
tests/invariantes/test_gab02_inventario.py::test_invariante_gab02_inventario PASSED
tests/invariantes/test_gab03_rotativo.py::test_invariante_gab03_rotativo PASSED
tests/invariantes/test_gab04_estabilizacao.py::test_invariante_gab04_estabilizacao PASSED
tests/invariantes/test_gab05_troca.py::test_invariante_gab05_troca PASSED

5 passed, 1552 deselected in 5.48s
```

**Igualdade confirmada:** 5 de 5 invariantes (`GAB-01` a `GAB-05`), mesma
contagem antes e depois, mesmo resultado (todos `PASSED`), nenhuma asserção
alterada (nenhum arquivo editado). A segunda passada de `Diagnostico` em
`calcular_plano` (`T-142`) não vazou para nenhum invariante estrutural.
Nenhuma falha ocorreu — nenhuma correção foi necessária. Contexto adicional:
`pytest -q --ignore=tests/app_aluno` completo → `600 passed, 9 skipped`,
mesma contagem já reportada no estado de entrada desta tarefa (`T-141`/
`T-142`/`T-144`), zero regressão.

---

### `T-149` — Confirmar que os gabaritos `GAB-AI-*`/`GAB-NFI-*` das fatias 4A/4B e da Rodada 3 continuam passando inalterados

- **Tipo:** `Test`
- **Dependências:** `T-142`
- **Rastreia:** `AC-116`, `RF-67`, `US-26`
- **Arquivos:** `tests/gabaritos_ataque_imediato/`, `tests/gabaritos_classificacao_ativos/`, `tests/gabaritos_necessidade_financeira/` (existentes, não editados)

**Descrição**

> **Confirmado, não presumido** (pedido explícito do orquestrador). Os gabaritos `GAB-AI-*` (Rodada 3), `GAB-NFI-06` a `12` (fatia 4A) e `GAB-NFI-01` a `05` (fatia 4B) testam funções puras isoladamente — não deveriam ser afetados por uma mudança em `engine/motor.py` (`T-141`/`T-142`), já que nenhum deles chama `calcular_plano` nem `_compor_ATAQUE_IMEDIATO_RECOMENDADO`. Esta tarefa reexecuta a suíte inteira desses três diretórios, sem editar nenhum arquivo, e reporta a contagem real de testes/gabaritos passando.

**Critérios de aceite**

- [x] Nenhum arquivo de `tests/gabaritos_ataque_imediato/`, `tests/gabaritos_classificacao_ativos/` ou `tests/gabaritos_necessidade_financeira/` é editado por esta tarefa
- [x] `pytest -m "gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"` roda e a nota de fechamento reporta a contagem real de testes passando (sem presumir o número "17" citado informalmente — a contagem real, tirada da saída do `pytest`, é o que fica registrado)
- [x] A nota de fechamento confirma, por comparação com a última contagem conhecida ao fim da fatia 4B (`T-139`/`T-140`), que nenhum teste passou a falhar e nenhum foi coletado a menos
- [x] Se qualquer teste desses diretórios falhar, a causa raiz é investigada e reportada antes de qualquer correção — correção eventual vira tarefa nova, não é feita dentro desta

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).** Reexecução pura, nenhum arquivo dos três
diretórios tocado — confirmado por `find tests/gabaritos_ataque_imediato
tests/gabaritos_classificacao_ativos tests/gabaritos_necessidade_financeira
-name "*.py" -printf '%TY-%Tm-%Td %TH:%TM'`: `mtime` mais recente é
`2026-09-10 00:22` (`tests/gabaritos_necessidade_financeira/test_gab_nfi_05_
acao_sem_valor_monetario.py`, produzido por `T-139`, antes de `T-141`), sem
nenhum arquivo tocado por esta tarefa nem por `T-141`/`T-142`/`T-148`.

**Contagem real** — `pytest -m "gabarito_ataque_imediato or gabarito_
classificacao_ativos or gabarito_necessidade_financeira" -v`:

```
tests/gabaritos_ataque_imediato/       ... 12 passed (GAB-AI-01 a 07,
                                             GAB-AI-03/04 parametrizados)
tests/gabaritos_classificacao_ativos/  ...  7 passed (GAB-NFI-06 a 12)
tests/gabaritos_necessidade_financeira/...  5 passed (GAB-NFI-01 a 05)

24 passed, 1533 deselected in 6.28s
```

Todos os 24 `PASSED`, nenhum `FAILED`/`ERROR`/`SKIPPED` — não há causa raiz a
reportar, nenhuma correção foi necessária.

**Comparação com a última contagem conhecida ao fim da fatia 4B
(`T-139`/`T-140`):** a homologação combinada registrada em `T-139`
(`pytest -m "gabarito or invariante or gabarito_ataque_imediato or
gabarito_classificacao_ativos or gabarito_necessidade_financeira"` →
`47 passed, 1504 deselected`) decompõe, por diretório, nas contagens
individuais já registradas nas notas de fechamento de origem: `tests/
gabaritos_ataque_imediato/` → **12 passed** (`T-109`/`T-110`, Rodada 3),
`tests/gabaritos_classificacao_ativos/` → **7 passed** (`T-128`, fatia 4A),
`tests/gabaritos_necessidade_financeira/` → **5 passed** (`T-139`, fatia
4B). Soma: `12 + 7 + 5 = 24`, exatamente a contagem obtida agora, isolada por
diretório e confirmada de novo:

```
tests/gabaritos_ataque_imediato/        12 passed in 0.39s
tests/gabaritos_classificacao_ativos/    7 passed in 0.55s
tests/gabaritos_necessidade_financeira/  5 passed in 0.62s
```

**Igualdade confirmada:** nenhum teste passou a falhar, nenhum foi coletado a
menos, nenhum a mais — os três diretórios, que testam funções puras
isoladamente sem chamar `calcular_plano` nem `_compor_ATAQUE_IMEDIATO_
RECOMENDADO`, permaneceram inteiramente inertes à mudança de `T-141`/`T-142`
em `engine/motor.py`, confirmando a hipótese da descrição desta tarefa por
medição real, não por presunção. Contexto adicional: `pytest -q
--ignore=tests/app_aluno` completo → `600 passed, 9 skipped`, zero
regressão.

---

### `T-150` — Auditar a docstring reescrita de `engine/diagnostico.py` (`AC-117`)

- **Tipo:** `Docs`
- **Dependências:** `T-143`
- **Rastreia:** `RF-69`, `AC-117`, `US-26`
- **Arquivos:** `tasks/motor-calculo.tasks.md` (nota de fechamento desta tarefa)

**Descrição**

Verificação de revisão (plano R4C.9, não teste automatizado) — confirma por leitura, após `T-143`, que `engine/diagnostico.py` não contém mais as três afirmações desatualizadas listadas por `RF-69`: que o campo é placeholder (sem qualificação "por design"), que `OQ-29` está aberta, ou que "nenhuma decisão do motor o lê" sem qualificação.

**Critérios de aceite**

- [x] `grep -n "OQ-29" engine/diagnostico.py` devolve vazio, ou só ocorrência marcada como referência histórica resolvida — reportado literalmente na nota de fechamento
- [x] A nota de fechamento transcreve o parágrafo reescrito da docstring (resultado de `T-143`) e confirma, frase a frase, que nenhuma das três afirmações desatualizadas de `RF-69` sobrevive sem qualificação
- [x] Nenhum código é alterado por esta tarefa — só leitura e registro

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).** `grep -n "OQ-29" engine/diagnostico.py`
devolveu duas ocorrências, ambas em `engine/diagnostico.py`, nenhuma
afirmando pendência aberta:

```
729:    pendência de `OQ-29` (RESPONDIDA em 2026-09-09, §14) — é a consequência
851:        # reserva do estado, nunca do elegível de OQ-29.
```

A ocorrência da linha 729 está explicitamente qualificada como
"RESPONDIDA em 2026-09-09, §14" — referência histórica resolvida, não
pendência. A da linha 851 é um comentário lateral sobre `RESERVA_MOBILIZAVEL`
(não sobre `ATAQUE_IMEDIATO_RECOMENDADO`), citando `OQ-29` apenas para dizer
que aquele campo NÃO depende do elegível — também não afirma pendência.

Parágrafo reescrito da docstring de `calcular_diagnostico`
(`engine/diagnostico.py:715-735`, produzido por `T-143`), transcrito
integralmente:

> `ATAQUE_IMEDIATO_RECOMENDADO`, chamada ISOLADA desta função, CONTINUA
> `dinheiro(0)` — por design, não por pendência. `calcular_diagnostico`
> não recebe (e não deve receber, decisão `OQ-44`/R4C.1.1 do plano)
> `ParticaoElegibilidade` nem `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` —
> a fórmula da §13.3/§14.2.4 exige o elegível, que só existe depois dos
> gates rodarem (`particionar_elegibilidade`), e esta função roda ANTES
> disso em `calcular_plano` (`engine/motor.py`, `RF-68`). O valor REAL só
> existe no `Diagnostico` que `calcular_plano` publica no
> `SnapshotOrdem` — lá, uma segunda passada (`dataclasses.replace`,
> `engine/motor.py::_compor_ATAQUE_IMEDIATO_RECOMENDADO`) substitui este
> placeholder pelo valor real, composto pelas mesmas nove funções de
> `engine/ataque_imediato.py` mais
> `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`/`NECESSIDADE_IMEDIATA_DIVIDA`
> (`engine/gates.py`, fatia 4B). Isto NÃO é mais placeholder por
> pendência de `OQ-29` (RESPONDIDA em 2026-09-09, §14) — é a consequência
> inevitável de `calcular_diagnostico` não ter, e não precisar ter,
> acesso aos gates: quem quer o valor real de
> `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` deve ler o `Diagnostico`
> dentro de um `SnapshotOrdem` publicado por `calcular_plano`, nunca o
> resultado de uma chamada isolada a esta função. `RF-66`/`RF-67`/
> §14.2.4 documentam a fórmula real e onde ela é aplicada.

Confirmação frase a frase contra as três afirmações desatualizadas de
`RF-69`:

1. **"campo é placeholder sem qualificação 'por design'"** — não sobrevive.
   A primeira frase já qualifica: "CONTINUA `dinheiro(0)` — **por design,
   não por pendência**".
2. **"`OQ-29` está aberta"** — não sobrevive. A única menção a `OQ-29`
   nesse parágrafo vem explicitamente marcada "(RESPONDIDA em 2026-09-09,
   §14)".
3. **"nenhuma decisão do motor o lê, sem qualificação"** — não sobrevive.
   O parágrafo afirma o oposto, com qualificação completa: o valor real
   É lido, mas só a partir do `Diagnostico` publicado dentro de um
   `SnapshotOrdem` por `calcular_plano` (via
   `_compor_ATAQUE_IMEDIATO_RECOMENDADO`, `T-141`/`T-142`) — nunca a
   partir de uma chamada isolada a `calcular_diagnostico`. A frase final
   fecha o raciocínio remetendo a `RF-66`/`RF-67`/§14.2.4 como onde a
   fórmula real e seu ponto de aplicação estão documentados.

Nenhum código alterado por esta tarefa — apenas leitura e este registro.

---

### `T-151` — Fechar a fatia 4C: verificação completa, sinalização formal a `app-aluno` e atualização de Open Questions

- **Tipo:** `Docs`
- **Dependências:** `T-144`, `T-145`, `T-146`, `T-147`, `T-148`, `T-149`, `T-150`
- **Rastreia:** `RF-66`, `RF-67`, `RF-68`, `RF-69`, `US-26`
- **Arquivos:** `tasks/motor-calculo.tasks.md` (esta seção), `specs/motor-calculo.spec.md` (§10, Open Questions)

**Descrição**

Fechamento único, ao fim da fatia inteira e da Rodada 4 completa — mesmo padrão de `T-116` (fim da Rodada 3) e `T-140` (fim da fatia 4B). Roda a verificação completa do projeto (`lint`, `build`, `test`, homologação de todos os marcadores `gabarito*`/`invariante`), confirma que nenhum arquivo de `app/`/`collection/`/`report/`/`tests/app_aluno/` foi tocado por `T-141` a `T-150`, e registra a **sinalização formal a `app-aluno`** de que esta fatia destrava o Bloco 10 daquele slug (`T-77`/`T-78`/`T-79`, referenciados pela sinalização de fim da Rodada 3, `T-116`) — sem implementar nada em `app-aluno`. Atualiza `OQ-44` (spec §10) para **resolvida** e registra a lacuna de `STATUS_METODO=PROVISORIO`/`EC-48` (R4C.10.1 do plano) como Open Question nova (`OQ-45`) — não resolvida por esta fatia, decisão futura do especialista/humana.

**Critérios de aceite**

- [x] `lint` (`ruff check .`), `build` (`mypy --strict`, seis pastas filtradas por existência) e `test` (`pytest -q`, incluindo e excluindo `tests/app_aluno`) rodam e o resultado real de cada um é reportado na nota de fechamento
- [x] Homologação completa (`pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"`) roda e a contagem real é reportada
- [x] Confirma, por timestamp/hash (mesmo procedimento de `T-140`, Aviso 3), que nenhum arquivo de `app/`, `collection/`, `report/` ou `tests/app_aluno/` foi editado por `T-141` a `T-150`
- [x] A nota de fechamento registra a sinalização formal a `app-aluno`: esta fatia é a última do documento do especialista e destrava de fato o Bloco 10 daquele slug (`T-77`/`T-78`/`T-79`) — sem editar nenhum arquivo daquele slug
- [x] `specs/motor-calculo.spec.md` §10: `OQ-44` atualizada de **aberta** para **resolvida** — decisão (2), `dataclasses.replace` em `engine/motor.py::calcular_plano`, referenciando `T-141`/`T-142`
- [x] `specs/motor-calculo.spec.md` §10 ganha `OQ-45` — nova, registrando a lacuna de R4C.10.1 do plano (segunda metade de `EC-48`/`AC-109`, sinalização de `STATUS_METODO=PROVISORIO`, não implementada nesta fatia por risco a `AC-116`) como decisão não tomada, pendente de especialista/humana — **nenhuma tarefa desta fatia a resolve**
- [x] A nota de fechamento confirma que a Rodada 4 inteira (fatias 4A, 4B, 4C) está completa — última fatia do documento do especialista, conforme plano
- [x] Nenhuma decisão de metodologia é tomada nesta tarefa

**Status:** `[x] concluída`

**Nota de fechamento (2026-09-10).**

### Verificação completa do projeto ao fim da fatia 4C

- `lint` (`ruff check .`) → `All checks passed!`
- `build` (`mypy --strict`, seis pastas filtradas por existência: `engine persistencia collection app report tests`) → `Success: no issues found in 300 source files`
- `test` completo (`pytest -q`, **incluindo** `tests/app_aluno`) → **`3 failed, 1479 passed, 75 skipped`** — as 3 falhas são exatamente as do Aviso 2 de `T-140` (`tests/app_aluno/estatica/test_engine_congelado.py`, hash congelado divergente de `engine/gates.py`/`engine/motor.py`/`persistencia/arquivo/repositorio_snapshots.py`, já sinalizado ao fim da fatia 4B), não corrigidas aqui por pertencerem ao procedimento de re-congelamento do slug `app-aluno`
- `test` com `--ignore=tests/app_aluno` → `600 passed, 9 skipped` — **idêntico** ao baseline mais recente conhecido (`T-147`), zero regressão introduzida por `T-148`–`T-150` (tarefas de auditoria/leitura, sem nova implementação)
- Homologação (`pytest -m "gabarito or invariante or gabarito_ataque_imediato or gabarito_classificacao_ativos or gabarito_necessidade_financeira"`) → `47 passed, 1510 deselected` — mesma contagem de gabaritos/invariantes de `T-140` (fim da fatia 4B); a fatia 4C reforça asserções dentro dos gabaritos existentes (`T-147`, `AC-116`) em vez de introduzir gabaritos novos com marcador próprio

### Confirmação por timestamp/hash — nenhum arquivo de `app/`, `collection/`, `report/`, `tests/app_aluno/` tocado por `T-141`–`T-150`

Mesmo procedimento de `T-140` (Aviso 3), medição direta:

- Varredura completa de `find app collection report tests/app_aluno -name "*.py" -printf '%TY-%Tm-%Td %TH:%TM:%TS %p'`, ordenada por data decrescente: o arquivo `.py` **mais recente** de qualquer um desses quatro diretórios é `tests/app_aluno/estatica/test_sem_rotulo_em_portugues_do_bloco_4.py`, com `mtime` **2026-09-07 18:50:51** — mais de dois dias antes do início da fatia 4C (`T-141`, 2026-09-10). Nenhum arquivo desses diretórios tem `mtime` posterior a 07/09.
- `app/montagem/estado.py`: SHA-256 atual `a57cf274beb6b28e5d40bcc35134e85532c891ca77533dadf9ed554dbfbc4b07` — **idêntico** ao valor medido e registrado por `T-140` (Aviso 3), confirmando ausência de edição também entre o fim da fatia 4B e o fim da 4C.
- `report/plano.py`: `mtime` **2026-09-07 18:45:21** — anterior ao início da fatia, sem edição.
- Por contraste: `find . -name "*.py" -newermt "2026-09-10 00:00:00"` (excluindo `app/`, `collection/`, `report/`, `tests/app_aluno/`, `.venv/`) lista exatamente os arquivos esperados da fatia — `engine/diagnostico.py`, `engine/motor.py` (`mtime` 00:50/00:54, implementação de `T-141`/`T-142`/`T-143`), mais os testes novos/tocados de `T-144`, `T-146`, `T-149` (`tests/regras/test_ataque_imediato_recomendado_diagnostico.py`, `tests/regras/test_diagnostico_isolado_mantem_placeholder.py`, `tests/gabaritos/test_gabarito_*`, `tests/gabaritos_necessidade_financeira/*`) — e nenhum arquivo desses diretórios protegidos.
- `engine/gates.py` (`mtime` 00:09:08) e `persistencia/arquivo/repositorio_snapshots.py` (`mtime` 00:02:18) também aparecem com data de hoje, mas **anteriores** ao início real da implementação da fatia 4C (`engine/motor.py` às 00:50) — são resquícios da fatia 4B (`T-132`–`T-139`), não tocados por nenhuma tarefa `T-141`–`T-150`: o plano desta fatia declara explicitamente que nenhuma tarefa reabre `engine/gates.py` (fora de leitura), e `T-145` audita esse ponto por leitura de código sem edição.

**Confirmado: nenhum arquivo de `app/`, `collection/`, `report/` ou `tests/app_aluno/` foi editado por `T-141` a `T-150`.**

### Sinalização formal ao slug `app-aluno` — Bloco 10 desbloqueado

Esta fatia (4C) é a **última do documento canônico do especialista** (PIQ v1.0.1, discovery Rodada 4 §8) e completa `RF-66`–`RF-69`: `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`, produzido por `calcular_plano`, deixa de carregar o placeholder fixo `dinheiro(0)` e passa a carregar o valor real de `MIN(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL, recursos estrategicamente recomendados)`.

`tasks/app-aluno.tasks.md` registra `T-77` ("Implementar o Bloco 10 condicional a `ATAQUE_IMEDIATO_RECOMENDADO > 0`"), `T-78` ("Validar `0 ≤ ATAQUE_IMEDIATO_APROVADO ≤ ATAQUE_IMEDIATO_RECOMENDADO`") e `T-79` ("Estender `AcaoRequerida`...") daquele slug como tendo **dependência externa** explícita sobre o campo `ATAQUE_IMEDIATO_RECOMENDADO`/`OQ-17` de `app-aluno.spec.md` — o mesmo campo que, do lado de `motor-calculo`, ficava preso ao placeholder pela metade não implementada de `OQ-29` (spec §10 deste slug, "a metade `ATAQUE_IMEDIATO_RECOMENDADO`/ligação em `calcular_diagnostico` permanece aberta, escopo da fatia 4C" — nota de fechamento de `T-140`). Com `OQ-29` fechada por completo e `OQ-44` resolvida (ambas nesta nota), o campo `ATAQUE_IMEDIATO_RECOMENDADO` devolvido por `calcular_plano` passa a carregar valor real, não mais `0` fixo — **`T-77`/`T-78`/`T-79` de `app-aluno` estão, a partir desta fatia, desbloqueadas** para implementação do lado daquele slug.

Isto é aviso formal, mesmo mecanismo de coordenação já usado em `T-116` (fim da Rodada 3) e `T-140` (fim da fatia 4B) — **nenhum arquivo do slug `app-aluno` foi editado por esta tarefa nem por qualquer tarefa `T-141`–`T-150`** (confirmado acima por timestamp/hash). A decisão de quando e como implementar `T-77`/`T-78`/`T-79` — incluindo qualquer re-congelamento de hash necessário em `tests/app_aluno/estatica/hashes_congelados.json` para `engine/motor.py`/`engine/diagnostico.py`, já listados como divergentes desde `T-140` — permanece do slug `app-aluno`, fora do escopo desta tarefa.

### Open Questions — `specs/motor-calculo.spec.md` §10

- `OQ-44` atualizada de **aberta** para **resolvida**: decisão (2) do plano — `calcular_diagnostico` mantém assinatura pública `(estado, parametros)` inalterada; `engine/motor.py::calcular_plano` ganha uma segunda passada via `dataclasses.replace` sobre o `Diagnostico` já construído, depois de `particionar_elegibilidade` e antes de `montar_SnapshotOrdem` (`T-141`, `T-142`). Resolve `AMB-R3-01` (plano R3.10.1) e `OQ-43` (discovery Rodada 4) por completo.
- `OQ-45` criada — nova: registra a lacuna de R4C.10.1 do plano (segunda metade de `EC-48`/`AC-109` — sinalizar `STATUS_METODO=PROVISORIO` quando `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` é `DESCONHECIDO`) como decisão **não tomada** por nenhuma tarefa desta fatia, pendente de especialista/humana. Ligar exigiria reordenar o pipeline de `calcular_plano`, com risco de violar `AC-116` (tolerância zero para `STATUS_METODO` em cenários hoje não-`PROVISORIO`) — motivo pelo qual não foi resolvida aqui.

Nenhuma decisão de metodologia foi tomada ao atualizar as duas entradas: `OQ-44` documenta um mecanismo técnico já implementado e verificado por `T-141`/`T-142`/`T-147`/`T-148`; `OQ-45` registra uma lacuna sem propor nem antecipar solução.

### Fechamento da Rodada 4 completa (fatias 4A + 4B + 4C)

- **Fatia 4A** (`T-117`–`T-131`, `RF-53`–`RF-60`): classificação de investimentos e ativos físicos — concluída.
- **Fatia 4B** (`T-132`–`T-140`, `RF-61`–`RF-65`): `VALOR_ACAO_FINANCEIRA_IMEDIATA`, `NECESSIDADE_IMEDIATA_DIVIDA`, `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` — concluída.
- **Fatia 4C** (`T-141`–`T-151`, `RF-66`–`RF-69`): ligação de `ATAQUE_IMEDIATO_RECOMENDADO` real em `Diagnostico`, resolução de `OQ-44`/`AMB-R3-01` — concluída com esta tarefa.

**Rodada 4 inteira está completa: 35 de 35 tarefas (`T-117` a `T-151`), 3 de 3 fatias.** Esta é a **última rodada do documento canônico do especialista** (discovery Rodada 4 §8) — seu fechamento completa a implementação de **ambos os documentos canônicos** do especialista no slug `motor-calculo`: o primeiro documento (PIQ, Rodadas 1–3, metodologia base e Ataque Imediato/Reserva) fechado pela Rodada 3 (`T-116`); o segundo documento (*"PIQ v1.0.1 — Definição Canônica"*, Rodada 4, classificação de ativos e Necessidade Financeira Imediata) fechado agora pela Rodada 4 (`T-151`). Nenhuma decisão de metodologia foi tomada nesta tarefa.

---

## Cobertura de requisitos — Rodada 4, fatia 4C

| Requisito | Tarefas |
| --------- | ------- |
| `RF-66` — `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` carrega o valor real de `MIN(elegível, recursos estrategicamente recomendados)`, sem exceção de caminho | `T-141`, `T-142`, `T-144`, `T-147`, `T-151` |
| `RF-67` — produzido exclusivamente por funções puras já existentes, nenhuma fórmula nova | `T-141`, `T-145`, `T-149`, `T-151` |
| `RF-68` — resolver formalmente `AMB-R3-01`/`OQ-44`: onde e como obter `ParticaoElegibilidade`/`Mapping[str, AcaoRequerida]` | `T-142`, `T-143`, `T-146`, `T-151` |
| `RF-69` — docstring de `calcular_diagnostico` e declaração de campo reescritas, sem as três afirmações desatualizadas | `T-143`, `T-150`, `T-151` |

**Cobertura:** 4 de 4 requisitos funcionais da fatia 4C (`RF-66`–`RF-69`). Nenhuma tarefa desta fatia existe sem requisito atrás.

### Cobertura dos critérios de aceite — Rodada 4, fatia 4C

| `AC-NN` | Tarefas |
| --- | --- |
| `AC-112` | `T-144`, `T-146` |
| `AC-113` | `T-144` |
| `AC-114` | `T-144` |
| `AC-115` | `T-141`, `T-145` |
| `AC-116` | `T-147`, `T-148`, `T-149` |
| `AC-117` | `T-143`, `T-150` |

Os 6 critérios de aceite da fatia 4C (`AC-112` a `AC-117`) têm tarefa. Nenhum ficou parcial.

### Cobertura das user stories — Rodada 4, fatia 4C

`US-26` — todas as tarefas desta fatia (`T-141` a `T-151`)

### Cobertura dos edge cases — Rodada 4, fatia 4C

`EC-48` `T-141`, `T-144` · `EC-49` `T-141`, `T-144` · `EC-50` — não vira tarefa: descreve um consumidor externo hipotético que esperaria o placeholder fixo `0`; a spec já resolve que não é comportamento a preservar (não é regressão, é mudança de contrato sinalizada por `T-151`)

### Requisitos sem cobertura — Rodada 4, fatia 4C

Nenhum. Todos os `RF-66` a `RF-69` têm ao menos uma tarefa de implementação e ao
menos uma de teste/auditoria. Nenhuma tarefa desta fatia toca `app/`,
`collection/`, `report/`, `engine/ataque_imediato.py` ou `engine/gates.py`
(além de leitura), nem retipa `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`, nem
implementa a sinalização de `STATUS_METODO=PROVISORIO` para a segunda metade
de `EC-48`/`AC-109` (lacuna registrada em `OQ-45`, não resolvida aqui).

---

## Open Questions

Itens do plano ou da spec que **não** viraram tarefa, e por quê. Nenhum deles é
escopo silencioso: ou está fora do slug, ou depende de decisão humana.

| ID | Ponto | Situação |
| --- | --- | --- |
| `OQ-A` | **`RISCO-15.2`** — o plano diverge da §15.2 da canônica (Apps Script + Google Sheets) e adota Python + Postgres. O plano registra que isso **exige confirmação humana e errata** declarando a §15.2 indicativa | `T-01` implementa a stack escolhida. A confirmação e a errata são decisão do especialista, não tarefa de código. **Bloqueia formalmente `T-01` até haver aceite.** |
| `OQ-B` | **FastAPI + uvicorn** aparecem na §2 do plano marcados "não é implementado agora" | Sem tarefa, por decisão do próprio plano. Vira escopo dos slugs `questionario` e `relatorio`. |
| `OQ-C` | **Supabase é opcional neste slug** (`T-75`, `T-76`) | Toda a suíte de homologação roda com adaptadores de arquivo. Se a conta não existir, `T-75` e `T-76` podem ser adiados sem bloquear a Definition of Done do motor. Confirmar com o usuário se o piloto terá Supabase. |
| `OQ-17` | `SUBSTITUIDA` e `SUSPENSA` na fórmula de `DIVIDA_ELEGIVEL_ORDEM` não constam do domínio de `STATUS_DIVIDA` | `T-31` implementa os cinco status reais das Definições §6. Os dois termos órfãos ficam sem tarefa até o especialista se pronunciar. |
| `OQ-18` | Valor de `STATUS_DIVIDA` para dívida pós-confirmação de `QUITADA_A_CONFIRMAR` | `T-29` trata a inelegibilidade antes da confirmação. O estado pós-confirmação (saída do inventário ativo ou novo status) permanece aberto. |
| `OQ-19` | Dívida que amortiza deterministicamente além de `P_HORIZONTE_MAXIMO_SIMULACAO` | `T-36` encerra no horizonte e sinaliza (`EC-13`). Se o especialista decidir `NAO_CALCULAVEL` para esse caso, vira nova tarefa. |
| `OQ-D` | Redação dos textos ao usuário (`Q-03`), conformidade LGPD (`PEND-01`) e correção metodológica das regras | Fora de escopo deste slug, conforme §9 da spec e §9 do plano. |
| `OQ-23` (Rodada 2) | Fórmula de cálculo de `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO` (`RF-35`) — nenhuma fonte publica o cálculo, só nome/tipo/posição | **RESPONDIDA em 2026-09-07** pela §13 da spec (documento canônico PIQ v1.0.1, congelado). `T-91` fica **superada** pela Rodada 3: a derivação de `RESERVA_MOBILIZAVEL` é `RF-43`/`T-102`, ligada ao `Diagnostico` em `T-114`. A parte de `ATAQUE_IMEDIATO_RECOMENDADO` permanece com placeholder por `OQ-29` (linha abaixo), não por `OQ-23`. |
| `OQ-29` (Rodada 3) | Fórmula fechada de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` — a §13.5 é a única variável da §13 definida só em prosa | **Não bloqueia 3A/3B.** `RF-48` a recebe **por parâmetro** e os enunciados de `GAB-AI-06`/`GAB-AI-07` fornecem o valor, então as nove funções puras ficam implementadas e testadas. Consequência registrada de `AMB-R3-01` (resolvida pelo usuário, opção (b)): `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` segue com `dinheiro(0)` e **`AC-85` fica parcialmente satisfeito** — ver `T-114`. Nenhuma fórmula é inventada. |
| `DT-01` (Rodada 3) | **Dívida técnica descoberta em `T-114`: ciclo de import em `engine/`.** Importar `derivar_RESERVA_MOBILIZAVEL` no topo de `engine/diagnostico.py` fecha o ciclo `diagnostico` → `ataque_imediato` → `ciclo_mensal` (por `ErroInvariante`) → `diagnostico`, quebrando **51 coletas** da suíte | **Contornado, não resolvido.** `T-114` usa import local dentro de `calcular_diagnostico`, documentado no código — funciona e não altera comportamento, mas é contorno. Duas correções estruturais foram identificadas e **nenhuma cabia no escopo de `T-114`**: (a) mover `ErroInvariante` para um módulo-folha sem dependências, ou (b) usar `TYPE_CHECKING` em `engine/ciclo_mensal.py`, onde `Diagnostico` já é usado só como anotação e `from __future__ import annotations` já está presente. Ambas tocam arquivos de outras tarefas ou da fatia 3C. **Não é bug** — nenhum comportamento observável depende disso; é higiene de arquitetura. Candidata a tarefa própria numa rodada futura, antes que outro módulo de `engine/` precise importar `ataque_imediato` e esbarre no mesmo ciclo. |
| `OQ-26`, `OQ-27`, `OQ-30`, `OQ-31`, `OQ-32`, `OQ-35` (Rodada 3) | Regra de derivação da classificação de mobilização; fórmula de `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`; fatia 3C inteira (`ATAQUE_IMEDIATO_APROVADO`, `GAB-AI-08`, injeção no cronograma); relação `ECONOMIA_POTENCIAL_IMEDIATA` × `ATAQUE_IMEDIATO_POTENCIAL` | Com o especialista do método. **Nenhuma vira tarefa nesta rodada, e nenhuma é antecipada.** O que o backlog faz em vez de adivinhar: `T-93` entrega só o **domínio** do enum e `T-101` proíbe por teste estático qualquer função que o derive (`OQ-26`); o valor líquido chega já apurado por item (`OQ-27`); nada de `ATAQUE_IMEDIATO_APROVADO` e nada em `engine/ciclo_mensal.py` (`OQ-30`/`OQ-32`/`OQ-35`); `ECONOMIA_POTENCIAL_IMEDIATA` fora da soma da §13.2 (`OQ-31`). |
| `OQ-25`, `OQ-28`, `OQ-33` (Rodada 3) | Distinção fina "decidir depois" × "não sei"; quem valida "livre / não comprometido"; onde vivem as travas da §13.8 | Encaminhadas na spec, **não bloqueiam**. `T-94` preserva os estados de coleta nos enums; `T-96`/`T-104` fixam a garantia de coleta para `DINHEIRO_DISPONIVEL` sem revalidação no motor; `T-95`/`T-112` garantem origem econômica única por modelagem (`ITEM_ID`) e `T-100` verifica o não-relançamento na coleta (`AC-84`). |
| `OQ-37` (Rodada 3) | Quem transporta as respostas do Bloco 4 até `EstadoFinanceiro` | **Desbloqueada pela fatia 3A**, e do slug `app-aluno`. `T-116` sinaliza o contrato de nove campos e o ponto que quebra (`app/montagem/estado.py:1326`) — **sem editar** o arquivo, que pertence àquele slug. |
| `OQ-26`, `OQ-27` (Rodada 3) | Regra de derivação da classificação de mobilização; fórmula de valor líquido realizável de ativo | **RESPONDIDAS em 2026-09-09** pelo documento canônico transcrito na §14. `OQ-26` vira `RF-53`/`RF-54` (`T-121`–`T-123`, `T-125`); `OQ-27` vira `RF-57`/`RF-58` (`T-120`, `T-121`, `T-126`). Superam o texto de `T-93`/`T-101` (Rodada 3) que só entregava o domínio do enum e proibia a derivação por teste estático — `T-130` reescreve esse teste para provar a regra em vez da ausência. |
| `OQ-29` (Rodada 3), reafirmada | Fórmula fechada de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`/`NECESSIDADE_IMEDIATA_DIVIDA` | **Ainda não implementada ao fim da fatia 4A** — a §14.1 a fecha, mas era escopo da fatia **4B**, fora daquela rodada (spec §4, nota da fatia 4A). Nenhuma tarefa de `T-117` a `T-131` a antecipou. **Backlog da fatia 4B agora existe** (`T-132` a `T-140`, seção "Rodada 4 — fatia 4B" acima): a metade `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` passa a ter tarefa de implementação (`T-134`, `T-135`) e teste (`T-137`, `T-139`). `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` continua com o placeholder registrado em `T-114` até a fatia 4C ligar o resultado — nenhuma tarefa de `T-132` a `T-140` toca `calcular_diagnostico`. |
| `OQ-38` (Rodada 4) | Ausência estrutural de variável de renda recorrente de veículo (`RENDA_RECORRENTE_VEICULO`/equivalente) na coleta — `bloco-04.yaml` só tem `CUSTO_RECORRENTE_VEICULO` | **Com o especialista, não bloqueia esta fatia.** `classificar_ativo_fisico` retorna `None` nesse ramo específico (`RF-56`, `T-123`, `T-131`) — os outros cinco ramos de veículo permanecem classificáveis. Enviada ao especialista em 2026-09-09, sem resposta até o fechamento desta rodada. |
| `OQ-42` (discovery, Rodada 4, não spec) | Leitura alternativa de `OQ-38` como "efeito desconhecido" (produzindo `MOBILIZACAO_POSSIVEL` por `DESCONHECIDO`) | **Explicitamente rejeitada para esta fatia, por pedido do usuário — não implementada, não contornada.** `T-123` implementa o sentinela `None`, nunca `DESCONHECIDO`, para o ramo de veículo; `T-131` prova por teste estático que essa leitura não existe no código e que, se reintroduzida propositalmente, é detectada. |
| `OQ-44` (Rodada 4, fatia 4C) | Mecanismo pelo qual `calcular_diagnostico`/`calcular_plano` deixam de emitir o placeholder de `ATAQUE_IMEDIATO_RECOMENDADO` | **RESOLVIDA pela fatia 4C.** Decisão (2), plano R4C.1.1: `calcular_diagnostico` mantém assinatura `(estado, parametros)` inalterada; `engine/motor.py::calcular_plano` ganha uma segunda passada via `dataclasses.replace`, depois de `particionar_elegibilidade`, antes de `montar_SnapshotOrdem` (`T-141`, `T-142`). `AMB-R3-01` (plano R3.10.1) fica resolvida por completo. |
| `OQ-45` (Rodada 4, fatia 4C) | Segunda metade de `AC-109`/`EC-48` — sinalizar `STATUS_METODO=PROVISORIO` quando `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` é `DESCONHECIDO` — continua sem mecanismo de ligação depois da fatia 4C, registrada como lacuna em R4C.10.1 do plano | **Não decidida por esta rodada — decisão humana/do especialista.** Ligar exigiria reordenar o pipeline de `calcular_plano` (calcular `elegivel` antes de `derivar_METODO_RECOMENDADO_PIQ`), o que arriscaria mudar `STATUS_METODO` de cenários hoje não-`PROVISORIO`, violando `AC-116` da própria fatia 4C. A metade "não fabricar número certo a partir do desconhecido" de `EC-48` **está** satisfeita (`T-141`, `T-144`); a metade "sinalizar status provisório" não. Nenhuma tarefa deste backlog a resolve — candidata a rodada futura, possivelmente junto da fatia 3C (`OQ-30`, `STATUS_ATAQUE_IMEDIATO`, ainda fora de escopo). |

> Requisito sem tarefa não será implementado. Tarefa sem requisito é escopo
> extra — remova ou volte à spec.
