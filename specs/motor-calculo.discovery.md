# Discovery — Extensão de `AcaoRequerida`/`Diagnostico` (pedido do slug `app-aluno`)

| Campo | Valor |
| ----- | ----- |
| Slug afetado | `motor-calculo` (backlog original `78/78` concluído — esta é uma rodada nova) |
| Origem do pedido | slug `app-aluno`, `specs/app-aluno.spec.md` §10 (Open Questions) |
| Motivo | `app-aluno` construiu toda a camada de aplicação sobre `engine/` **congelado**, e três tarefas do seu backlog (`T-77`, `T-78`, `T-79`) ficaram bloqueadas — a decisão de *o quê* mudar já foi tomada pelo especialista; falta o slug `motor-calculo` escrever o código |
| Decisões já fechadas por | especialista do método, registradas com justificativa técnica completa em `specs/app-aluno.spec.md` §10: `OQ-10`, `OQ-13`, `OQ-14`, `OQ-15`, `OQ-17`, `OQ-18` (todas `respondida`) |

## Por que isto não é uma decisão nova a tomar aqui

Este documento **não pede** que o slug `motor-calculo` decida nada de metodologia. Toda decisão de produto/domínio já foi tomada pelo especialista do lado de `app-aluno`, com evidência técnica registrada. O trabalho aqui é de **implementação**: transcrever essas decisões para `engine/gates.py` e `engine/diagnostico.py`, e revalidar os gabaritos e invariantes que essa mudança toca.

Se, ao implementar, surgir qualquer ambiguidade que os textos abaixo não resolvem, a resposta é a mesma regra de sempre (`sdd.config.md` §7 e §3, "ambiguidade não se adivinha"): registrar como Open Question nova em `specs/motor-calculo.spec.md`, não decidir por conta própria.

## Estado atual de `engine/gates.py::AcaoRequerida`

```python
@dataclass(frozen=True, slots=True)
class AcaoRequerida:
    DIVIDA_ID: str
    descricao: str
    gate_origem: Literal[2, 3]
    prioridade_excepcional: bool = False
```

O próprio docstring já previa a extensão: *"a estrutura completa de `ORDEM_ACOES` (...) é consolidada em `T-32`, que pode estender esta dataclass com novos campos sem quebrar o contrato aqui fixado"*.

## As mudanças pedidas, uma a uma

### 1 e 2 — `AcaoRequerida` ganha `ACAO_ID` e `TIPO_ACAO` (`OQ-10`, `OQ-13`)

```python
ACAO_ID: str
TIPO_ACAO: str  # domínio fechado, ver abaixo
```

- **`ACAO_ID`**: identidade estável da ação. Permanece idêntica entre snapshots enquanto a ação for a mesma — é o vínculo que o Bloco 11 do `app-aluno` usa para saber que uma pergunta de acompanhamento se refere à mesma ação vista antes, mesmo depois de recalcular.
- **`TIPO_ACAO`**: domínio fechado de exatamente quatro valores, ASCII, sem parênteses, nomeados pelo conceito específico (decisão do especialista, `OQ-13`):
  ```
  "INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"
  ```
  Motivo de não usar o termo genérico entre parênteses que a canônica usa em prosa (`INTERVENÇÃO (renegociação)`, `CORREÇÃO (economia)`): o termo específico já resolve por construção a pergunta "existe só uma intervenção?" — ver `OQ-13` na íntegra para a justificativa completa.

Nenhum dos dois tem hoje linha no dicionário de variáveis da canônica (§11) — não há domínio publicado a transcrever além do que `OQ-13` já fechou.

### 3 — Derivação de `TIPO_ACAO` (`OQ-14`)

Três dos quatro valores já são deriváveis do que o motor **já decide** hoje; o quarto passa a ser emitido (mudança 4, abaixo). O discriminador correto não é `gate_origem` (que é só `Literal[2, 3]`, insuficiente) — é `GATE_PENDENTE` (`engine/tipos.py:75-87`), cujo próprio docstring diz: *"Gates 2 e 3 compartilham `INTERVENCAO_PENDENTE` e só se distinguem aqui"*.

Mapeamento:

| `TIPO_ACAO` | Origem |
| --- | --- |
| `"INFORMACAO"` | Gate 1 (`GATE_PENDENTE.INFORMACAO`) |
| `"RENEGOCIACAO"` | Gate 3 + `divida.RENEGOCIACAO_PENDENTE` |
| `"TROCA"` | Gate 3 + `divida.TROCA_PENDENTE` |
| `"ECONOMIA"` | Fora do fluxo de gates (mudança 6, abaixo) |

O Gate 3 (`engine/gates.py:368-374`, conferir número de linha atual) já ramifica os três casos internamente, escrevendo a origem na `descricao` em prosa — a informação já existe, só precisa passar a ser campo tipado em vez de texto livre.

### 4 — `DIVIDA_ID` passa de `str` para `str | None` (`OQ-15`)

```python
DIVIDA_ID: str | None
```

Mudança de **invariante do contrato**, não acréscimo: hoje todo consumidor de `ORDEM_ACOES` pode presumir `DIVIDA_ID` presente. Com a ação de economia (mudança 6) emitida fora do fluxo de gates, ela não tem dívida associada — é identificada exclusivamente por `ACAO_ID`.

**Atenção ao implementar:** todo código dentro de `motor-calculo` que hoje lê `AcaoRequerida.DIVIDA_ID` presumindo `str` precisa passar a tratar `None`. (O lado `app-aluno` já está pronto para isso — construiu o vínculo do Bloco 11 inteiramente sobre `ACAO_ID`, nunca sobre `DIVIDA_ID`, precisamente para não quebrar quando esta mudança chegasse.)

### 5 — Gate 1 passa a emitir `AcaoRequerida` (`OQ-14`)

**Isto é a mudança de maior risco das cinco.** Hoje, `aplicar_gate_1_informacao` devolve `acao=None` nos dois ramos de bloqueio:

```python
# engine/gates.py — ramo 1 (linha ~191-205)
if divida.STATUS_DIVIDA == STATUS_DIVIDA.QUITADA_A_CONFIRMAR:
    return ResultadoGates(
        ...,
        acao=None,  # ← passa a construir uma AcaoRequerida de tipo INFORMACAO
    )

# engine/gates.py — ramo 2 (linha ~207-222)
if resultado_valor_relevante.VALOR_RELEVANTE_PARA_QUITACAO is DESCONHECIDO:
    return ResultadoGates(
        ...,
        acao=None,  # ← idem
    )
```

Os dois ramos passam a construir uma `AcaoRequerida` com `TIPO_ACAO = "INFORMACAO"` em vez de `None`.

**Consequência que precisa virar trabalho explícito, não efeito colateral:** os gabaritos e invariantes do slug já foram fechados contra a saída atual (`acao=None`). Pelo menos `GAB-03` (dívida rotativa sem saldo/pagamento, `INFORMACAO_PENDENTE`) e `EC-17` (todas as dívidas bloqueadas, `ORDEM_ACOES` primeiro) tocam exatamente dívidas travadas por informação — uma `ORDEM_ACOES` que hoje vem vazia nesses casos passa a vir preenchida. `specs/motor-calculo.spec.md` cita tolerância **zero** para gates e aplicação de resíduo (§10.3) — uma divergência aqui não é absorvível por arredondamento. Reexecutar `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes, e atualizar as expectativas de `ORDEM_ACOES` onde mudarem, faz parte desta mudança — não é um item separado a esquecer.

### 6 — Ação de economia emitida fora do fluxo de gates

Quando `ECONOMIA_POTENCIAL_IMEDIATA > 0` (deriva de `VALOR_GASTOS_FANTASMAS` com `B2.10A = SIM`), o motor emite uma `AcaoRequerida` com `TIPO_ACAO = "ECONOMIA"` e `DIVIDA_ID = None`, fora do fluxo normal de gates (gates avaliam dívidas; economia é sobre orçamento, não sobre uma dívida específica). Ver mudança 4 para a consequência de tipo.

### 7 — Novo campo `CAMPO_PENDENTE` em `AcaoRequerida` (`OQ-18`)

```python
CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"]
```

Os dois ramos de bloqueio de `aplicar_gate_1_informacao` (mudança 5, acima) reduzem a exatamente duas causas — nomeie qual delas gerou o bloqueio:

| Ramo | `CAMPO_PENDENTE` |
| --- | --- |
| `STATUS_DIVIDA == QUITADA_A_CONFIRMAR` | `"STATUS_DIVIDA"` |
| `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` (dentro de `compor_VALOR_RELEVANTE_PARA_QUITACAO`, `engine/valor_quitacao.py`) | `"SALDO_DEVEDOR_ATUAL"` |

O campo nomeia o **campo de `Divida` do próprio contrato do motor** — nunca um `RegistroPergunta.ID` de coleta (o motor não conhece pergunta, só variável de domínio; a mesma fronteira que já separa `engine/` de `collection/` no slug `app-aluno`). Quem traduz `CAMPO_PENDENTE` para a pergunta a reabrir é a aplicação, não o motor.

### 8 — `Diagnostico` ganha dois campos extras (`OQ-17`)

```python
# engine/diagnostico.py — mesmo bloco de "campos comportamentais adicionais"
# que já existe hoje para NIVEL_CONTROLE, CONFIABILIDADE_DADOS, etc.
RESERVA_MOBILIZAVEL: Dinheiro
ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro
```

Segue **exatamente** o padrão já usado em `engine/diagnostico.py` para os cinco campos comportamentais que já foram adicionados como extras ao bloco literal do plano original (`NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS`, `RISCO_RECAIDA`, `RISCO_COMPORTAMENTAL_GERAL`, `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`) — mesmo motivo: `SnapshotOrdem` declara um único campo `diagnostico: Diagnostico`, não uma tupla, então a extensão vem como campo novo em `Diagnostico`, nunca como objeto separado.

Hoje `ATAQUE_IMEDIATO_RECOMENDADO`/`RESERVA_MOBILIZAVEL` não existem em nenhum lugar de `engine/*.py` (confirmado por busca em todo o pacote) — só aparecem em condição de exibição e prosa de "uso pelo motor" na canônica, sem nunca terem sido implementados como campo real.

## Resumo executável (checklist)

- [ ] `AcaoRequerida.ACAO_ID: str` (novo campo)
- [ ] `AcaoRequerida.TIPO_ACAO: str`, domínio fechado `{"INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"}` (novo campo)
- [ ] `AcaoRequerida.DIVIDA_ID` muda de `str` para `str | None` (mudança de tipo — checar todo consumidor interno)
- [ ] `AcaoRequerida.CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"]` (novo campo)
- [ ] `aplicar_gate_1_informacao` passa a emitir `AcaoRequerida` (`TIPO_ACAO="INFORMACAO"`, `CAMPO_PENDENTE` conforme o ramo) nos dois ramos que hoje devolvem `acao=None`
- [ ] Gate 3 passa a preencher `TIPO_ACAO` (`RENEGOCIACAO`/`TROCA`) em vez de só escrever em `descricao`
- [ ] Ação de economia emitida fora do fluxo de gates quando `ECONOMIA_POTENCIAL_IMEDIATA > 0`, com `DIVIDA_ID=None`, `TIPO_ACAO="ECONOMIA"`
- [ ] `Diagnostico.RESERVA_MOBILIZAVEL: Dinheiro` e `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro` (novos campos, mesmo bloco de extras já existente)
- [ ] `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes reexecutados; expectativas de `ORDEM_ACOES` atualizadas onde a saída do Gate 1 mudar de vazia para preenchida
- [ ] Hash congelado de `engine/` em `tests/app_aluno/estatica/hashes_congelados.json` (slug `app-aluno`) precisa ser atualizado depois desta mudança — é o procedimento já documentado por `AC-44` naquele slug, não parte deste trabalho

## O que isto desbloqueia do lado de `app-aluno`

`tasks/app-aluno.tasks.md::T-77`, `T-78`, `T-79` — único trabalho executável restante daquele backlog, hoje bloqueado só por esta dependência. Nenhuma mudança de desenho é necessária do lado de `app-aluno` quando esta rodada terminar: `T-83`, `T-84`, `T-89`, `T-90` (Bloco 11) e a leitura de `Diagnostico` em `T-77`/`T-78` já foram escritos para consumir exatamente estes campos por nome, incluindo os `xfail(strict=True)` que provam manualmente (via monkeypatch) que passariam de verdade assim que estes campos existirem.

---
---

# Discovery — Rodada 3: Ataque Imediato e Reserva (resposta a `OQ-23`)

| Campo | Valor |
| ----- | ----- |
| Slug afetado | `motor-calculo` (Rodada 1 `78/78` · Rodada 2 `13/14`, `T-91` bloqueada — esta é a terceira rodada) |
| Origem do pedido | Documento canônico *"PIQ v1.0.1 — Definição Canônica de `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO` — Regras de composição, limites, precedência e entrada no cronograma"*, entregue pelo especialista do método em **2026-09-07** |
| Motivo | `OQ-23` (levantada na Rodada 2) foi respondida. A fórmula existe agora, mas **a resposta é maior que a pergunta**: define seis variáveis e consome ~16 entradas que não existem no motor |
| Fonte normativa | `specs/motor-calculo.spec.md` **§13** (11 subseções, transcrição integral), marcada **congelada**: *"Nenhuma dessas decisões fica a critério do desenvolvedor"* |
| Estado de `T-91` | Continua **bloqueada**, mas por motivo diferente — ver "A mudança de natureza do bloqueio" abaixo |

## Por que isto NÃO é a mesma situação da Rodada 2

A Rodada 2 foi um discovery de **transcrição**: toda decisão de domínio já estava
fechada, e o trabalho era mecânico — escrever em `engine/gates.py` e
`engine/diagnostico.py` aquilo que o especialista já havia decidido. O documento
daquela rodada podia se dar ao luxo de abrir com *"este documento não pede que o
slug decida nada de metodologia"*.

**A Rodada 3 não tem esse luxo.** A §13 é normativa e congelada para o que ela
trata — mas ela trata de **fórmulas**, não de **origens de dados**. Ela declara
que `ATAQUE_IMEDIATO_POTENCIAL = DINHEIRO_DISPONIVEL + RESERVA_MOBILIZAVEL + ...`
sem dizer como nenhuma dessas parcelas chega ao motor. O resultado é um documento
de discovery com uma proporção invertida em relação ao anterior: **o que já está
decidido é a aritmética; o que não está decidido é praticamente todo o resto** —
modelagem de estado, fronteira de módulo, produção da classificação de ativos,
ponto de confirmação do usuário e integração no cronograma.

Este documento, portanto, **levanta questões e não as resolve**. Onde a §13 é
explícita, ele transcreve e aponta. Onde a §13 é silenciosa, ele registra a
lacuna como questão aberta — conforme `sdd.config.md` §6 ("metodologia não se
decide implementando") e a regra de ambiguidade do `CLAUDE.md`.

## A mudança de natureza do bloqueio de `T-91`

`tasks/motor-calculo.tasks.md:2701` descreve `T-91` como *"BLOQUEADA por `OQ-23`"*,
e seu primeiro critério de aceite (`:2714`) é:

> `OQ-23` está respondida pelo especialista do método, com fórmula explícita
> registrada em `specs/motor-calculo.spec.md` (...) antes de qualquer linha de
> implementação desta tarefa

**Esse critério foi satisfeito em 2026-09-07.** A fórmula existe e está em §13.
Mesmo assim `T-91` não se torna executável, porque o bloqueio migrou:

| | Antes (Rodada 2) | Agora (Rodada 3) |
| --- | --- | --- |
| Natureza | "não existe fórmula" | "existe fórmula, não existe o estado que ela lê" |
| Quem resolve | especialista do método | parte modelagem técnica nossa, parte especialista |
| Arquivo afetado | `engine/diagnostico.py` (um) | `engine/estado.py`, `engine/diagnostico.py`, `engine/ciclo_mensal.py`, `engine/snapshot.py`, `collection/`, `app/` |

O estado atual do placeholder está em `engine/diagnostico.py:637-638` (campos) e
`engine/diagnostico.py:764-765` (valores), com a justificativa em
`engine/diagnostico.py:674-687` — cuja última frase (*"A derivação real é escopo
de `T-91`, bloqueada até `OQ-23` ser respondida"*) precisa ser reescrita nesta
rodada, porque a premissa que ela cita mudou.

## 1. Inventário de lacunas de modelagem

Varredura própria (`grep` em `engine/` por `RESERVA|ATIVO|INVESTIMENT|EXTRAORDIN|MOBILIZ|ATAQUE_IMEDIATO|DINHEIRO_DISPONIVEL|NECESSIDADE_FINANCEIRA`).
O levantamento do pedido confere; abaixo o resultado verificado, com linha.

### 1.1. O que já existe em `engine/`

| Identificador | Onde | Observação |
| --- | --- | --- |
| `RESULTADO_MENSAL_ATUAL` | `engine/diagnostico.py:150` | Entrada da trava de `MODO_ESTABILIZACAO` da §13.4 — **já disponível** |
| `MODO_ESTABILIZACAO` | `engine/diagnostico.py:486` | Derivado da mesma condição de déficit que a §13.4 exige — **já disponível** |
| `ECONOMIA_POTENCIAL_IMEDIATA` | `engine/estado.py:340` | Ver questão `OQ-31` (sobreposição conceitual) |
| `DESCONHECIDO` / `Desconhecido` | `engine/tipos.py:32`, `:40` | Alinhamento explícito pedido pela §13.1 |
| `DinheiroTalvez` | `engine/tipos.py:45` | `Dinheiro \| Desconhecido` — o tipo que `RESERVA_MOBILIZAVEL` precisa passar a ter |
| `Oportunidade` | `engine/estado.py:76-89` | Placeholder mínimo (`beneficio`, `recurso_disponivel`, `prazo`, `sustentavel`) — relevante para §13.5 |
| `Divida.OPORTUNIDADE_VIGENTE` | `engine/estado.py:294` | Gate 4 |
| `RESERVA_MOBILIZAVEL` / `ATAQUE_IMEDIATO_RECOMENDADO` | `engine/diagnostico.py:637-638` | **Contrato apenas**, `dinheiro(0)` em `:764-765` |

### 1.2. O que NÃO existe em `engine/` — confirmado

`EstadoFinanceiro` (`engine/estado.py:334-346`) tem exatamente 14 campos e
**nenhum** modela reserva, caixa, investimento, ativo ou recurso extraordinário.
Nenhum dos identificadores abaixo aparece em qualquer arquivo de `engine/`:

| Variável consumida pela §13 | Origem declarada (§13.11 / canônica) | O que falta criar |
| --- | --- | --- |
| `RESERVA_TOTAL` | Usuário (`B4.02A`) | Campo em `EstadoFinanceiro`, tipo `DinheiroTalvez` (a §13.1 Regra 3 exige o estado `DESCONHECIDA`) |
| `RESERVA_EXISTE` | Usuário (`B4.02`) | Campo; domínio ternário — ver `OQ-25` (o `INFORMAL` de coleta) |
| `DISPOSICAO_USO_RESERVA` | Usuário (`B4.03`) | Campo; domínio de 4 valores em coleta — ver `OQ-25` |
| `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` | Usuário (`B4.03A`) | Campo; **não existe com este nome em lugar nenhum do projeto** — ver `OQ-24` |
| `DINHEIRO_DISPONIVEL` | Usuário (`B4.01A`) | Campo `Dinheiro`; a §13.3 exige a qualificação "realmente livre / não comprometido" — ver `OQ-28` |
| `INVESTIMENTOS_LIQUIDOS_MOBILIZAVEIS` | Motor (derivada) | Estrutura de investimento por item + regra de derivação — a regra **não está publicada** |
| `RECURSOS_EXTRAORDINARIOS_POTENCIAIS` | Motor (derivada) | Estrutura por item + regra; entradas em `collection/registros/bloco-03.yaml:245-312` |
| `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` | Motor (derivada) | Estrutura de ativo + fórmula — **não publicada** (ver `OQ-27`) |
| `MOBILIZACAO_POSSIVEL` / `_RECOMENDAVEL` / `_COM_RESSALVAS` / `NAO_MOBILIZAR` | Motor (derivada, ver §4 abaixo) | Enum novo em `engine/tipos.py` + **regra de classificação não publicada** (`OQ-26`) |
| `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` | Motor | Sem fórmula fechada (`OQ-29`) |
| `ATAQUE_IMEDIATO_POTENCIAL` | Motor | Campo novo em `Diagnostico` |
| `ATAQUE_IMEDIATO_APROVADO` | Usuário (confirmação) | Campo + **ponto de interação inexistente** (`OQ-30`) |
| `RESERVA_RECOMENDADA` | Motor | Campo novo |
| `CAIXA_RECOMENDADO` / `INVESTIMENTOS_RECOMENDADOS` / `EXTRAORDINARIOS_RECOMENDADOS` / `ATIVOS_RECOMENDADOS` | Motor | Intermediárias da §13.3 |

**Ordem de grandeza.** A §13 consome 16 identificadores inexistentes e produz 7
novos. `EstadoFinanceiro` hoje tem 14 campos: acomodar isto significa
aproximadamente **dobrar a superfície do contrato de entrada do motor** — e
`EstadoFinanceiro` entra em `SnapshotOrdem.estado_inputs`
(`engine/snapshot.py:120`), que alimenta `hash_inputs` (`:119`) via
`_serializar_canonico` (`:136`). Toda adição de campo muda o hash de todo
snapshot existente. Isso é consequência estrutural, não detalhe.

### 1.3. Uma estrutura nova, não só campos escalares

Investimentos e ativos são **repetíveis por item** na coleta — as fichas
`B4.04A–B4.06B` (investimentos) e `B4.I02–B4.I09` (imóveis) são marcadas
`[COND, REP]` em `collection/registros/bloco-04.yaml:217`, `:236`, `:261`,
`:280`, `:300`, `:336`. A §13.3 soma "Σ `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`
dos ativos `MOBILIZACAO_RECOMENDAVEL`" — ou seja, o motor precisa de uma
**coleção de itens classificados individualmente**, no mesmo padrão de
`EstadoFinanceiro.dividas: tuple[Divida, ...]` (`engine/estado.py:342`), não de
um único total agregado. Provavelmente `tuple[Ativo, ...]` e
`tuple[Investimento, ...]` (nomes a decidir no plano).

## 2. A fronteira `engine/` × `collection/` — `B4.03A` no meio da fórmula

A §13.1 Regra 2 e a Regra 3 são escritas **em termos de uma pergunta**:

```
SE B4.03A possuir valor numérico conhecido            ← ID de pergunta
SE B4.03A = "Prefiro decidir somente depois de ver a análise"   ← rótulo de opção
OU B4.03A = "Não sei"
```

Isto colide frontalmente com a fronteira firmada na Rodada 2. O precedente é
explícito no discovery anterior (mudança 7, `OQ-18`):

> O campo nomeia o **campo de `Divida` do próprio contrato do motor** — nunca um
> `RegistroPergunta.ID` de coleta (o motor não conhece pergunta, só variável de
> domínio (...)). Quem traduz `CAMPO_PENDENTE` para a pergunta a reabrir é a
> aplicação, não o motor.

E é reforçado por `sdd.config.md` §3: *"nada em `engine/` ou `persistencia/`
importa de `app/`, `collection/` ou `report/`"*.

O motor, portanto, **não pode** ler `B4.03A` nem comparar contra rótulos em
português. Precisa de um contrato de domínio equivalente. A tradução natural dos
três estados textuais é um domínio fechado (`Dinheiro` | "decidir depois" | "não
sei"), possivelmente colapsando os dois últimos em `DESCONHECIDO` — a §13.1
Regra 3 os trata de forma idêntica, e o pseudocódigo da §13.9 já faz exatamente
esse colapso ao testar `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO`.

**Mas isso não está decidido**, e há um motivo concreto para não decidir sozinho:
"prefiro decidir depois" e "não sei" são estados **comportamentalmente
diferentes** (um é adiamento deliberado, o outro é falta de informação), e o
projeto já tem precedente de distinguir esses casos — `CAMPO_PENDENTE` da Rodada
2 existe justamente para nomear a causa de um bloqueio, e `app/` reabre pergunta
com base nisso. Colapsar os dois em `DESCONHECIDO` pode ser correto para a
aritmética e errado para a devolutiva ao usuário. Ver `OQ-25`.

### 2.1. Conflito direto de nomenclatura — o achado mais concreto desta varredura

`collection/registros/bloco-04.yaml:156`:

```yaml
  - ID: B4.03A
    (...)
    VARIAVEL_GRAVADA: RESERVA_MOBILIZAVEL
```

A coleta grava a resposta crua de `B4.03A` **na variável `RESERVA_MOBILIZAVEL`**.
A §13.1 diz o oposto: `RESERVA_MOBILIZAVEL` é o **resultado** de
`MIN(RESERVA_TOTAL, MAX(0, VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO))`, e a
resposta crua de `B4.03A` é o **insumo** `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`.

São dois valores diferentes com o mesmo nome: em `GAB-AI-02` (§13.10) a resposta
crua é `30.000` e `RESERVA_MOBILIZAVEL` é `20.000`. Sob a regra de idioma do
projeto (`sdd.config.md` §7 — "o nome no código deve ser o nome na especificação,
caractere por caractere"), esta colisão é exatamente o tipo de coisa que faz uma
regra se perder. Um dos dois lados precisa ser renomeado. Ver `OQ-24`.

## 3. O Bloco 4 existe — e é mais completo do que se supunha

`collection/registros/bloco-04.yaml` existe, tem 49 perguntas transcritas da §11
da canônica (cabeçalho, `:1-3`), e **todas as perguntas de reserva estão lá**:

| Pergunta | Linha | `VARIAVEL_GRAVADA` |
| --- | --- | --- |
| `B4.01` | `:19` | `DINHEIRO_DISPONIVEL_EXISTE` |
| `B4.01A` | `:35` | `DINHEIRO_DISPONIVEL` |
| `B4.02` | `:58` | `RESERVA_EXISTE` |
| `B4.02A` | `:77` | `RESERVA_TOTAL` |
| `B4.02B` | `:104` | `LOCAL_RESERVA` |
| `B4.03` | `:134` | `DISPOSICAO_USO_RESERVA` |
| `B4.03A` | `:156` | `RESERVA_MOBILIZAVEL` (ver `OQ-24`) |
| `B4.04` | `:178` | `INVESTIMENTOS_EXISTE` |
| `B4.04A` | `:205` | `TIPO_INVESTIMENTO` |
| `B4.04B` | `:222` | `VALOR_ESTIMADO_ATIVO (investimento)` |
| `B4.05` | `:246` | `LIQUIDEZ_INVESTIMENTOS` |
| `B4.06`/`B4.06A` | `:268`, `:286` | `CUSTO_DESMOBILIZACAO_INVESTIMENTOS*` |
| `B4.06B` | `:306` | `DISPOSICAO_USO_INVESTIMENTO` |
| `B4.I01`–`B4.I04A` | `:324`–`:400` | Ficha de imóvel |
| Recursos extraordinários | `bloco-03.yaml:245`–`:312` | `TIPO_/VALOR_/JANELA_/CERTEZA_RECURSO_EXTRAORDINARIO` |

**Conclusão: a coleta não é dependência externa bloqueante.** Este é o achado
mais favorável da rodada — a matéria-prima existe e está transcrita. O que não
existe é (a) o transporte dessas respostas até `engine/` e (b) as regras de
derivação que transformam resposta crua em variável de fórmula.

Note ainda `bloco-04.yaml:112-115`, que já implementa uma trava de dupla contagem
na origem:

> Valores aqui informados como reserva NÃO são relançados em B4.04
> (investimentos). B4.04 pergunta explicitamente "além dos valores já informados
> como reserva".

Isto é exatamente o primeiro caso vedado da §13.8 (reserva em CDB contada duas
vezes), já prevenido no questionário. Relevante para a §8 abaixo.

## 4. Classificação de ativos — a lacuna mais silenciosa

A §13 usa `MOBILIZACAO_POSSIVEL`, `MOBILIZACAO_RECOMENDAVEL`,
`MOBILIZACAO_COM_RESSALVAS` e `NAO_MOBILIZAR` em quatro pontos distintos (§13.2,
§13.3 duas vezes, §13.7) e **nunca diz como a classificação é produzida**.

Busca em todo o repositório: os quatro termos aparecem em exatamente **dois**
arquivos — `specs/motor-calculo.spec.md` (a própria §13) e
`specs/piq-app-spec.md`. Zero ocorrências em `engine/`, `collection/`, `app/`,
`tests/`. Não há enum, não há função, não há teste.

A canônica responde metade da pergunta, em `specs/piq-app-spec.md:2614`:

> **Derivadas pelo motor, nunca perguntadas:** Classificação dos ativos
> (`NAO_MOBILIZAR` · `MOBILIZACAO_COM_RESSALVAS` · `MOBILIZACAO_POSSIVEL` ·
> `MOBILIZACAO_RECOMENDAVEL`), `ATIVOS_TOTAIS`, `PASSIVOS_VINCULADOS_ATIVOS`,
> `PATRIMONIO_LIQUIDO`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO`,
> `PATRIMONIO_MOBILIZAVEL`, `PATRIMONIO_ESTRATEGICAMENTE_MOBILIZAVEL`,
> `ECONOMIA_RECORRENTE_POTENCIAL`, `ATAQUE_IMEDIATO_POTENCIAL / RECOMENDADO` são
> derivados pelo motor. **Nunca perguntar a classificação do ativo.**

Ou seja: está **fechado que é derivação do motor** (não entrada do usuário) e
está **proibido perguntar**. O que não existe em lugar nenhum é **a regra de
derivação** — quais entradas produzem qual das quatro classes, e com que corte.

Isto é uma lacuna metodológica de tamanho comparável à própria §13: sem ela,
`ATIVOS_RECOMENDADOS` e `INVESTIMENTOS_RECOMENDADOS` são incalculáveis, e
portanto `ATAQUE_IMEDIATO_RECOMENDADO` inteiro é incalculável. As entradas
plausíveis existem na coleta (`LIQUIDEZ_INVESTIMENTOS` com domínio
`D0/D1/D7/D30/MAIS_30/BLOQUEADO`, `bloco-04.yaml:239-245`;
`CUSTO_DESMOBILIZACAO_INVESTIMENTOS`, `:286`; `DISPOSICAO_USO_INVESTIMENTO`,
`:306`; `IMOVEL_POSSUI_PASSIVO`, `:383`) — mas mapear essas entradas nas quatro
classes é **decisão de metodologia, não de implementação**. Ver `OQ-26` e `OQ-27`.

## 5. `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` — definida em prosa, sem fórmula

Diferente de todas as outras variáveis da §13, esta não tem bloco de fórmula.
A §13.5 a define por quatro finalidades ("executar ações financeiras imediatas
elegíveis; aproveitar oportunidades executáveis; realizar quitações e
amortizações permitidas; aplicar ataque extraordinário sobre dívidas atualmente
elegíveis") e por duas desigualdades (`ATAQUE_IMEDIATO_RECOMENDADO <=` ela e
`<= ATAQUE_IMEDIATO_POTENCIAL`). A §13.11 a lista como "Origem: Motor".

Ela é o **teto** da fórmula inteira: em `GAB-AI-07` é ela, sozinha, que reduz
`25.000` de recursos disponíveis a um recomendado de `10.000`. Sem fórmula
fechada, `GAB-AI-06` e `GAB-AI-07` só são executáveis com o valor **injetado**
como dado de teste, nunca derivado.

Investiguei se dá para derivar do que o motor já tem. Os ingredientes das quatro
finalidades existem parcialmente:

| Finalidade da §13.5 | O que o motor já tem |
| --- | --- |
| "dívidas atualmente elegíveis" | `ParticaoElegibilidade` / `aplicar_gates` (`engine/gates.py`), consumida em `engine/ordem.py:113` |
| "quitações permitidas" | `compor_VALOR_RELEVANTE_PARA_QUITACAO` (`engine/valor_quitacao.py`), usada em `engine/ordem.py:115` |
| "oportunidades executáveis" | `Oportunidade` (`engine/estado.py:76-89`) — mas é **placeholder mínimo** por docstring própria (`:80-83`), com avaliação completa remetida a `T-29`/`T-30` |
| "ações financeiras imediatas elegíveis" | `ORDEM_ACOES: tuple[AcaoRequerida, ...]` (`engine/snapshot.py:131`) — mas `AcaoRequerida` **não tem campo de valor**; carrega `descricao`, `TIPO_ACAO`, `CAMPO_PENDENTE`, nunca um `Dinheiro` |

Ou seja: existem peças, mas **não uma soma óbvia e única**. A pergunta concreta
que ninguém respondeu é se `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` é
`Σ VALOR_RELEVANTE_PARA_QUITACAO` das dívidas elegíveis pós-gate, ou algo mais
restrito (só as estrategicamente vantajosas, conforme a REGRA CANÔNICA da §13.4
que exige "finalidade concreta e justificável"). As duas leituras dão números
muito diferentes, e a diferença cai direto no valor recomendado ao usuário.
Ver `OQ-29`. **Esta é a questão que mais bloqueia a rodada.**

## 6. `ATAQUE_IMEDIATO_APROVADO` — um passo de interação que não existe

A §13.6 define o aprovado como "parcela do recomendado que o usuário
**confirma** que utilizará", e a §13.11 lista sua origem como "Usuário".

O fluxo atual do motor não tem esse passo. `calcular_diagnostico(estado,
parametros)` (`engine/diagnostico.py:641`) é uma função pura de uma passada:
recebe estado, devolve diagnóstico. Não há ponto onde o motor pare, apresente um
número e espere confirmação — e não pode haver, porque `engine/` é puro por
regra (`sdd.config.md` §3: "a pureza do motor (função pura, sem I/O) depende
disso e é verificada em teste estático").

A consequência é estrutural: `ATAQUE_IMEDIATO_APROVADO` **não pode ser derivado
pelo motor**; tem que **entrar** nele como dado, num segundo cálculo. Isso
implica um ciclo de duas passadas:

```
1ª passada: estado (sem aprovado) → Diagnostico com ATAQUE_IMEDIATO_RECOMENDADO
2ª passada: estado + ATAQUE_IMEDIATO_APROVADO confirmado → cronograma-base
```

O que reforça essa leitura: `app/` já tem máquina de estados do caso
(`app/casos/maquina.py`), rotas de cálculo (`app/http/rotas_calculo.py`) e o
Bloco 11 de acompanhamento (`app/http/rotas_bloco11.py`) — a infraestrutura de
"perguntar algo ao usuário depois de um cálculo" existe naquele slug, não neste.
E `V-01` (`sdd.config.md` §4) já manda que "quitação confirmada ou evento
material cria um novo snapshot" — uma confirmação de ataque imediato parece
encaixar nesse mesmo padrão de novo snapshot.

Mas **nada disso está escrito em lugar nenhum**, e a fronteira entre os slugs
importa: se o passo de confirmação vive em `app-aluno`, esta rodada precisa
entregar apenas o **contrato de entrada** e coordenar com aquele backlog, como a
Rodada 2 coordenou na direção inversa. Ver `OQ-30`.

## 7. Impacto no cronograma-base — o maior risco da rodada

A §13.6 é categórica: *"Somente `ATAQUE_IMEDIATO_APROVADO` entra no
cronograma-base da engine."* Investiguei como o cronograma funciona hoje.

O cronograma é `simular_cenario` (`engine/ciclo_mensal.py:725`), que monta o
`EstadoSimulacao` de abertura em `:779-787` com:

```python
CAPACIDADE_ATAQUE_M=dg.CAPACIDADE_ATAQUE_CONSERVADORA,
```

E a docstring (`:748-750`) registra a regra vigente:

> `dg` carrega `CAPACIDADE_ATAQUE_CONSERVADORA` (RF-14/RF-15 — **"a única
> capacidade que alimenta o cronograma-base"**, `engine/diagnostico.py`), usada
> como `CAPACIDADE_ATAQUE_M` do mês de abertura.

**Aqui está o atrito.** Existem hoje duas afirmações normativas de exclusividade
sobre o mesmo objeto:

- `RF-14`/`RF-15`: `CAPACIDADE_ATAQUE_CONSERVADORA` é a **única** capacidade que
  alimenta o cronograma-base;
- §13.6: **somente** `ATAQUE_IMEDIATO_APROVADO` entra no cronograma-base.

As duas são conciliáveis se forem lidas como grandezas de naturezas distintas —
uma é fluxo mensal recorrente, a outra é injeção pontual no mês 0 — mas nenhuma
das duas redações diz isso, e a §13 não menciona `CAPACIDADE_ATAQUE_CONSERVADORA`
em nenhum ponto. Ver `OQ-32`.

### 7.1. A trava de conservação `A-04`/`F-02` não absorve um aporte externo

`engine/ciclo_mensal.py:590-602` verifica, com igualdade exata e `ErroInvariante`
ruidoso:

```python
ataque_aplicado = e.CAPACIDADE_ATAQUE_M - residuo_ataque + sum(...)
soma_conservacao = ataque_aplicado + ataque_nao_utilizado
if soma_conservacao != e.CAPACIDADE_ATAQUE_M:
    raise ErroInvariante(
        "conservação do ataque do mês não fechou (A-04/TRAVA): ..."
```

O comentário imediatamente acima (`:583-589`) explica que é *"nunca ± tolerância,
é subtração exata dentro do próprio mês"*, porque *"um motor que perde ou inventa
dinheiro é bug crítico"*.

Consequência direta: **qualquer dinheiro injetado no mês 0 que não passe por
`CAPACIDADE_ATAQUE_M` faz a trava estourar.** Há pelo menos três desenhos
possíveis (somar o aprovado à `CAPACIDADE_ATAQUE_M` do mês 0; abater direto dos
saldos iniciais em `saldos_iniciais`, `:769-777`, antes do mês 1; criar um "mês
zero" de aporte), e eles produzem **cronogramas diferentes** — abater do saldo
antes do primeiro ciclo de juros não dá o mesmo número que atacar dentro do mês
1 depois de `_saldo_apos_juros` (`:280`). A §13 não escolhe nenhum, e a escolha
muda o resultado de `GAB-AI-08` ("cronograma-base utiliza apenas 9.000").

Além disso, um aporte no mês 0 pode quitar dívida logo de saída, o que ativa a
cascata de resíduo (`M-06`/`A-01`, `:628-631`), altera `mes_primeira_vitoria`
(`:809-812`) e portanto pode mudar o **método recomendado** — a Bola de Neve e o
Híbrido dependem de primeira vitória. O alcance é bem maior que "somar um número".

**Este é o análogo da mudança 5 da Rodada 2** (Gate 1 passando a emitir ação), que
o discovery anterior marcou como "a mudança de maior risco das cinco" e que
obrigou a revisar gabaritos. Aqui o risco é maior, porque toca a trava de
conservação e os três métodos, sob tolerância zero (`sdd.config.md` §5: tolerância
zero para "método recomendado, ordem, gates, status, número de meses, primeira
vitória").

## 8. Travas de dupla contagem (§13.8) — onde elas vivem?

A §13.8 lista quatro casos vedados. Cada um cai numa camada diferente, e é isso
que torna a questão não trivial:

| Caso vedado (§13.8) | Camada onde é verificável | Observação |
| --- | --- | --- |
| Reserva em CDB contada como reserva **e** investimento | **Coleta** | Já prevenido: `bloco-04.yaml:112-115` instrui que valores de reserva não são relançados em `B4.04` |
| Dinheiro comprometido contado como `DINHEIRO_DISPONIVEL` | **Coleta** | `B4.01` já pergunta "que não esteja comprometido com as despesas normais" (`bloco-04.yaml:8-11`) |
| Venda de ativo contada como ativo **e** como dinheiro | **Motor** (invariante) | Verificável estruturalmente |
| Extraordinário como aprovado **e** como evento independente | **Motor/aplicação** | Toca `EVENTO_RECALCULO` (`engine/snapshot.py:118`) |

O motor tem precedente forte para tratar isso como **invariante de execução**, e
não como validação de entrada: a trava `A-04` (§7.1 acima) é exatamente uma
verificação de conservação de dinheiro com `ErroInvariante`. O análogo natural
seria `ATAQUE_IMEDIATO_POTENCIAL >= ATAQUE_IMEDIATO_RECOMENDADO >=
ATAQUE_IMEDIATO_APROVADO >= 0` (a hierarquia da §13.6) checada em tempo de
execução.

Mas a hierarquia é **consequência**, não causa: ela pode continuar válida com
dupla contagem em ambos os lados. Detectar a dupla contagem de fato exige
rastrear **origem econômica** de cada recurso (a §13.8 exige "origem econômica
única"), o que só é possível se cada item carregar sua categoria — o que remete
de novo à modelagem da §1.3. Ver `OQ-33`.

## 9. Sobreposição com as capacidades já existentes

`engine/diagnostico.py` já produz `BASE_CONSERVADORA` (`:477`),
`CAPACIDADE_ATAQUE_CONSERVADORA` (`:478`), `CAPACIDADE_ATAQUE_ATUAL` (`:257`),
`CAPACIDADE_ATAQUE_POTENCIAL` e `MODO_ESTABILIZACAO` (`:486`).

**A §13 não menciona nenhuma delas** — exceto `MODO_ESTABILIZACAO`, e apenas
como trava (§13.4). Isso é notável, porque a nomenclatura é quase idêntica:
`CAPACIDADE_ATAQUE_POTENCIAL` (existente) vs. `ATAQUE_IMEDIATO_POTENCIAL` (novo);
`CAPACIDADE_ATAQUE_CONSERVADORA` (existente, o que alimenta o cronograma) vs.
`ATAQUE_IMEDIATO_RECOMENDADO` (novo, o que o motor considera adequado).

A leitura mais provável é que sejam grandezas **ortogonais**: capacidade é
**fluxo mensal** derivado de `RESULTADO_MENSAL_ATUAL` (renda menos despesas, ver
`engine/diagnostico.py:271`: `CAPACIDADE_ATAQUE_ATUAL = MAX(0,
RESULTADO_MENSAL_ATUAL)`), enquanto ataque imediato é **estoque** derivado de
patrimônio (caixa, reserva, ativos). Fluxo e estoque não se sobrepõem por
natureza, e a §13.2 de fato só soma parcelas patrimoniais.

**Mas há um ponto de contato real e não resolvido.** `ECONOMIA_POTENCIAL_IMEDIATA`
(`engine/estado.py:340`) é anotada no próprio código como `# GAB-B/EC-11:
potencial ≠ base` e a docstring de `engine/diagnostico.py:23-30` registra que ela
entra numa soma com as capacidades:

```
(1) CAPACIDADE_ATAQUE_CONSERVADORA + ECONOMIA_POTENCIAL_IMEDIATA = 200 + 400 = 600
(2) BASE_CONSERVADORA + ECONOMIA_POTENCIAL_IMEDIATA              = 200 + 400 = 600
```

`ECONOMIA_POTENCIAL_IMEDIATA` tem "IMEDIATA" no nome, é dinheiro que o usuário
poderia liberar já, e na Rodada 2 passou a gerar uma `AcaoRequerida` de
`TIPO_ACAO="ECONOMIA"` (discovery Rodada 2, mudança 6). Ela é economia
**recorrente** (fluxo) ou **imediata** (estoque)? Se for lida como estoque
disponível agora, é candidata a compor `ATAQUE_IMEDIATO_POTENCIAL` — e aí há
dupla contagem com a soma acima. A canônica (`piq-app-spec.md:2614`) lista
`ECONOMIA_RECORRENTE_POTENCIAL` na mesma frase que `ATAQUE_IMEDIATO_POTENCIAL /
RECOMENDADO`, o que sugere que são vizinhas conceituais e que alguém já pensou
nas duas juntas — sem dizer como se relacionam. Ver `OQ-31`.

## 10. Precedência sobre a Matriz Canônica — há conflito com o já implementado?

A §13 declara prevalecer "para os temas especificamente tratados nesta seção".
Varri as Rodadas 1 e 2 procurando implementação conflitante.

**Resultado: nenhum conflito de cálculo.** O motivo é simples e verificável — os
temas da §13 **nunca foram implementados**. `RESERVA_MOBILIZAVEL` e
`ATAQUE_IMEDIATO_RECOMENDADO` são placeholders `dinheiro(0)`
(`engine/diagnostico.py:764-765`), explicitamente marcados como *"não usado por
nenhuma decisão do motor (nenhum gate, nenhuma ordenação, nenhum cronograma lê
estes dois campos ainda)"* (`:682-683`). As outras quatro variáveis da §13 não
existem. Não há fórmula anterior a ser revogada, nem teste a ser reescrito por
mudança de regra.

Ficam **três pontos de atrito de fronteira**, todos já registrados acima, e
nenhum deles é conflito de fórmula:

1. `RF-14`/`RF-15` "única capacidade que alimenta o cronograma-base" × §13.6
   "somente `ATAQUE_IMEDIATO_APROVADO` entra no cronograma-base" (§7, `OQ-32`);
2. `collection/registros/bloco-04.yaml:156` grava a resposta crua de `B4.03A` em
   `RESERVA_MOBILIZAVEL`, que a §13.1 define como valor derivado (§2.1, `OQ-24`);
3. A trava `A-04` de conservação exata (§7.1) não conflita com a §13, mas
   restringe severamente como ela pode ser integrada.

O item 1 é o único que pode exigir revisão de redação normativa anterior. Os
itens 2 e 3 são de implementação.

## 11. Os 8 testes de homologação (`GAB-AI-01` a `GAB-AI-08`)

Os gabaritos hoje vivem em dois lugares: `tests/gabaritos/` (numéricos ponta a
ponta — `test_gabarito_a_deficit.py`, `test_gabarito_b_equilibrio_fragil.py`,
`test_gabarito_c_*.py`) com fixtures JSON em `tests/fixtures/gab_a.json`,
`gab_b.json`, `gab_c.json`; e `tests/invariantes/` (`test_gab01_seguro.py` a
`test_gab05_troca.py`).

Os `GAB-AI-NN` **não se encaixam em nenhum dos dois moldes**, e isso é um achado,
não um detalhe de organização:

- `GAB-A`/`GAB-B`/`GAB-C` são **ponta a ponta**: carregam um `EstadoFinanceiro`
  completo de fixture e verificam a saída do motor inteiro. Sete dos oito
  `GAB-AI` não são assim — `GAB-AI-01` a `GAB-AI-07` verificam **uma fórmula
  isolada** com 3 a 6 entradas, sem dívidas, sem gates, sem cronograma.
- `GAB-01`..`GAB-05` são **invariantes** (propriedades que valem sempre). Os
  `GAB-AI` são casos numéricos pontuais, não propriedades.

Portanto: **é uma terceira família de gabarito**, provavelmente
`tests/gabaritos_ataque_imediato/` (nome a decidir no plano). Divisão por
natureza:

| ID | Natureza | O que exige para ser executável |
| --- | --- | --- |
| `GAB-AI-01`, `-02`, `-03` | Unitário de `RESERVA_MOBILIZAVEL` | Só os 4 campos de reserva modelados. **Executável assim que a §1.2 estiver modelada** |
| `GAB-AI-04` | Idem + estado `DESCONHECIDA` | Idem + resolução de `OQ-25` |
| `GAB-AI-05` | `RESERVA_RECOMENDADA` sob déficit | Reusa `MODO_ESTABILIZACAO` já existente |
| `GAB-AI-06`, `-07` | `ATAQUE_IMEDIATO_RECOMENDADO` completo | Exige `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` **injetável** — o enunciado a fornece como dado ("`= 20.000`"), então o teste passa mesmo sem `OQ-29` respondida, desde que a variável seja parâmetro e não derivada internamente |
| `GAB-AI-08` | Ponta a ponta com cronograma | Exige tudo: aprovado, integração no cronograma, `OQ-30` + `OQ-32`. **O único verdadeiramente ponta a ponta** |

Observação de método que vale registrar: sete dos oito gabaritos são testáveis
sem resolver as questões mais difíceis, **desde que as funções de derivação sejam
puras e recebam suas entradas por parâmetro** em vez de irem buscá-las no estado.
Isso é um argumento forte a favor do fatiamento proposto na §13 deste discovery.

Sobre tolerância: `sdd.config.md` §5 dá `± R$ 0,05` para valores monetários
acumulados. Os `GAB-AI` são valores redondos exatos (`5.000`, `20.000`, `8.000`)
resultantes de `MIN`/`MAX`/soma — não há acumulação de arredondamento, então
tolerância zero é defensável. Não decido: ver `OQ-34`.

## 12. Questões abertas desta rodada

Numeração continuando a série local do slug (a Rodada 2 encerrou em `OQ-23`).
**Nenhuma destas é decidida neste documento.**

### 12.1. Exigem o especialista do método

| ID | Questão | Por que bloqueia |
| --- | --- | --- |
| `OQ-26` | **Qual a regra de derivação da classificação de ativos** (`NAO_MOBILIZAR` · `MOBILIZACAO_COM_RESSALVAS` · `MOBILIZACAO_POSSIVEL` · `MOBILIZACAO_RECOMENDAVEL`)? A canônica (`piq-app-spec.md:2614`) fecha que é derivada pelo motor e proíbe perguntar, mas nenhuma fonte publica o mapeamento de entradas (`LIQUIDEZ_INVESTIMENTOS`, `CUSTO_DESMOBILIZACAO_*`, `DISPOSICAO_USO_INVESTIMENTO`, `IMOVEL_POSSUI_PASSIVO`, tipo de ativo) para as quatro classes | Sem ela, `ATIVOS_RECOMENDADOS` e `INVESTIMENTOS_RECOMENDADOS` são incalculáveis, logo `ATAQUE_IMEDIATO_RECOMENDADO` inteiro é incalculável. **Bloqueia `GAB-AI-06`/`-07` na derivação real** |
| `OQ-27` | **Qual a fórmula de `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`?** A canônica lista `VALOR_LIQUIDO_REALIZAVEL_ATIVO` como derivada; a §13.3 usa o sufixo `_DISPONIVEL`, que não aparece na canônica. São a mesma variável? Entram `CUSTOS_ESTIMADOS_DESMOBILIZACAO` (`bloco-04.yaml:516`, `:772`, `:960`) e `SALDO_PASSIVO_VINCULADO` (`:400`)? | Componente direto de `ATIVOS_RECOMENDADOS` |
| `OQ-29` | **Qual a fórmula fechada de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`?** A §13.5 é a única variável definida só em prosa. É `Σ VALOR_RELEVANTE_PARA_QUITACAO` das dívidas elegíveis pós-gate, ou um subconjunto "estrategicamente vantajoso" (§13.4)? Ações de `ORDEM_ACOES` entram — e com que valor, se `AcaoRequerida` não tem campo monetário? | É o **teto** de toda a fórmula (`GAB-AI-07` depende exclusivamente dele). **A questão mais bloqueante da rodada** |
| `OQ-31` | **`ECONOMIA_POTENCIAL_IMEDIATA` compõe `ATAQUE_IMEDIATO_POTENCIAL`?** Ela é fluxo (economia recorrente) ou estoque (dinheiro liberável já)? Hoje entra em soma com as capacidades (`engine/diagnostico.py:23-30`); a canônica cita `ECONOMIA_RECORRENTE_POTENCIAL` ao lado de `ATAQUE_IMEDIATO_POTENCIAL` (`piq-app-spec.md:2614`) sem relacioná-las | Risco de dupla contagem entre capacidade mensal e ataque imediato (§13.8) |
| `OQ-32` | **Como conciliar `RF-14`/`RF-15` ("`CAPACIDADE_ATAQUE_CONSERVADORA` é a única capacidade que alimenta o cronograma-base", `engine/ciclo_mensal.py:748-750`) com a §13.6 ("somente `ATAQUE_IMEDIATO_APROVADO` entra no cronograma-base")?** Fluxo mensal e injeção pontual coexistem, ou uma redação revoga a outra? | Define se há revisão de norma anterior. **Bloqueia `GAB-AI-08`** |
| `OQ-35` | **Em que momento do cronograma o `ATAQUE_IMEDIATO_APROVADO` é aplicado?** Antes do primeiro ciclo de juros (abatendo `saldos_iniciais`, `engine/ciclo_mensal.py:769-777`), ou dentro do mês 1 após `_saldo_apos_juros` (`:280`)? As duas produzem cronogramas diferentes, e o aporte pode quitar dívida de saída, alterando `mes_primeira_vitoria` (`:809-812`) e, por consequência, o **método recomendado** | Tolerância zero para "número de meses, primeira vitória, método recomendado" (`sdd.config.md` §5) |

### 12.2. Decisão técnica nossa (plano/spec, sem o especialista)

| ID | Questão | Encaminhamento provável |
| --- | --- | --- |
| `OQ-24` | **Colisão de nome:** `collection/registros/bloco-04.yaml:156` grava a resposta crua de `B4.03A` em `RESERVA_MOBILIZAVEL`; a §13.1 define `RESERVA_MOBILIZAVEL` como o valor **derivado** e chama a resposta crua de `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`. Em `GAB-AI-02` os dois valem `30.000` e `20.000` | **RESOLVIDA (usuário, 2026-09-07) — decisão técnica, não requer especialista.** Renomear o `VARIAVEL_GRAVADA` de `bloco-04.yaml:156` para `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`, alinhando com §13 (congelada, com precedência declarada sobre redação anterior). `RESERVA_MOBILIZAVEL` fica exclusivo do valor **derivado**. Escopo verificado: **uma única linha** — todos os outros 15 usos de `RESERVA_MOBILIZAVEL` no repositório (`engine/diagnostico.py`, `persistencia/`, 11 arquivos de teste) já usam o nome no sentido correto (campo derivado de `Diagnostico`), nenhum precisa mudar. O `ID` da pergunta (`B4.03A`) **não** muda — `sdd.config.md` §6 exige estabilidade do ID, não do `VARIAVEL_GRAVADA` |
| `OQ-25` | **Contrato de domínio para os três estados de `B4.03A`.** O motor não pode ler ID de pergunta nem rótulo em português (precedente `OQ-18`/`CAMPO_PENDENTE`, Rodada 2). "Prefiro decidir depois" e "Não sei" colapsam ambos em `DESCONHECIDO` (como faz o pseudocódigo §13.9), ou são estados distintos? Idem para `RESERVA_EXISTE = INFORMAL` (`bloco-04.yaml:56`) e os 4 valores de `DISPOSICAO_USO_RESERVA` (`:127-133`), que a §13.1 reduz a `NAO`/não-`NAO` | Colapso é correto para a aritmética; a distinção pode importar para a devolutiva e para reabrir pergunta. Provável: `DinheiroTalvez` no motor + preservação do estado fino em `app/` |
| `OQ-28` | **Como o motor sabe que `DINHEIRO_DISPONIVEL` está "realmente livre, não comprometido"** (§13.3)? `B4.01` já pergunta isso no enunciado (`bloco-04.yaml:8-11`), então é garantia de coleta — ou o motor deve validar? | Provável: garantia de coleta, documentada; o motor confia no contrato |
| `OQ-33` | **Onde vivem as travas de dupla contagem (§13.8)?** Invariante de execução com `ErroInvariante` (padrão `A-04`, `engine/ciclo_mensal.py:596-602`), validação na construção do estado, ou garantia de coleta? Detectar "origem econômica única" exige que cada item carregue categoria | Provável: híbrido — hierarquia da §13.6 como invariante no motor; não-relançamento como garantia de coleta (já em `bloco-04.yaml:112-115`) |
| `OQ-34` | **Tolerância dos `GAB-AI`:** `± R$ 0,05` (padrão de monetário acumulado, `sdd.config.md` §5) ou zero? Os oito são valores exatos de `MIN`/`MAX`/soma, sem acumulação | Provável: zero, por não haver acumulação de arredondamento |
| `OQ-36` | **`Diagnostico` cresce em 5 campos** (`ATAQUE_IMEDIATO_POTENCIAL`, `_APROVADO`, `RESERVA_RECOMENDADA`, `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`, e `RESERVA_MOBILIZAVEL` muda de `Dinheiro` para `DinheiroTalvez`). A mudança de tipo é **quebra de contrato**, não adição | Mesmo tratamento da mudança 4 da Rodada 2 (`DIVIDA_ID: str → str | None`): checar todo consumidor. Impacta `hash_inputs` (`engine/snapshot.py:119-120`) e o hash congelado de `app-aluno` (`AC-44`) |

### 12.3. Coordenação entre slugs

| ID | Questão | Slug |
| --- | --- | --- |
| `OQ-30` | **Onde vive o passo de confirmação de `ATAQUE_IMEDIATO_APROVADO`?** `engine/` é puro por regra (`sdd.config.md` §3) e `calcular_diagnostico` (`engine/diagnostico.py:641`) é uma passada só — o aprovado não pode ser derivado, tem que entrar como dado num segundo cálculo. `app/` já tem máquina de estados (`app/casos/maquina.py`), rotas de cálculo (`app/http/rotas_calculo.py`) e Bloco 11 (`app/http/rotas_bloco11.py`) | `app-aluno` provavelmente dono do passo; `motor-calculo` entrega o contrato de entrada. Coordenação inversa à da Rodada 2 |
| `OQ-37` | **Quem transporta as respostas do Bloco 4 até `EstadoFinanceiro`?** `app/montagem/estado.py` é o montador e hoje não tem nenhuma referência a reserva ou ataque imediato (grep: zero ocorrências) | `app-aluno`, dependente do contrato que esta rodada definir |

## 13. Tamanho da rodada e proposta de fatiamento

**Esta rodada é grande demais para uma leva só.** Comparação honesta com a Rodada
2: aquela foram 8 mudanças em 2 arquivos de `engine/`, 14 tarefas, com todas as
decisões de domínio já fechadas. Esta tem ~16 variáveis de entrada a modelar, 2
estruturas repetíveis novas, 7 variáveis derivadas, 6 questões que exigem o
especialista, alteração da trava de conservação do cronograma e coordenação com
dois outros slugs.

Além disso, ela **não é executável de ponta a ponta hoje**: `OQ-29` (fórmula de
`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`) e `OQ-26` (classificação de ativos)
são pré-requisitos da derivação real, e nenhuma das duas depende de nós.

Proposta de três rodadas, ordenadas por dependência e por quanto cada uma entrega
mesmo com as questões abertas:

### Rodada 3A — Modelagem de estado (executável já, sem depender do especialista)

Modelar em `engine/estado.py` os campos e estruturas da §1.2/§1.3: reserva
(4 campos), `DINHEIRO_DISPONIVEL`, coleções de investimentos, ativos e recursos
extraordinários, e o enum de classificação em `engine/tipos.py` (o **domínio** dos
quatro valores está fechado pela §13; só a **regra de derivação** falta, `OQ-26`).
Entrega o contrato que `app-aluno` precisa para `OQ-37`. Depende de resolver
`OQ-24`, `OQ-25`, `OQ-28`, `OQ-36` — todas decisão técnica nossa.

### Rodada 3B — Cálculo puro (parcialmente executável)

`RESERVA_MOBILIZAVEL` (§13.1), `RESERVA_RECOMENDADA` (§13.4),
`ATAQUE_IMEDIATO_POTENCIAL` (§13.2) e `ATAQUE_IMEDIATO_RECOMENDADO` (§13.3), como
funções puras recebendo entradas por parâmetro. **Fecha `GAB-AI-01` a `GAB-AI-07`
(sete dos oito)** — inclusive `-06` e `-07`, porque os enunciados fornecem
`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` como dado. Destrava efetivamente
`T-91`, que é sobre exatamente estes dois campos. Fica pendente a derivação real
de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (`OQ-29`) e da classificação
(`OQ-26`) — o mesmo padrão de placeholder honesto que `T-90` já usou, agora num
escopo bem menor.

### Rodada 3C — Integração no cronograma (bloqueada; maior risco)

`ATAQUE_IMEDIATO_APROVADO`, o passo de confirmação e a injeção no cronograma-base.
Fecha `GAB-AI-08`. Bloqueada por `OQ-30`, `OQ-32` e `OQ-35`. É onde mora o risco
de regressão em `GAB-A`/`GAB-B`/`GAB-C` e nos cinco invariantes, pela trava `A-04`
e pelo efeito sobre primeira vitória e método recomendado.

**Recomendação:** abrir 3A imediatamente (não depende de ninguém e desbloqueia
`app-aluno`), enviar `OQ-26`/`OQ-27`/`OQ-29`/`OQ-31`/`OQ-32`/`OQ-35` ao
especialista em paralelo, e não iniciar 3C antes das respostas.

## Resumo executável (checklist)

Pré-requisitos — nenhum é código:

- [ ] `OQ-24` decidida: renomear ou não `VARIAVEL_GRAVADA` de `B4.03A` (`collection/registros/bloco-04.yaml:156`)
- [ ] `OQ-25` decidida: contrato de domínio dos três estados de `B4.03A`, do `INFORMAL` de `RESERVA_EXISTE` e dos 4 valores de `DISPOSICAO_USO_RESERVA`
- [ ] `OQ-26`, `OQ-27`, `OQ-29`, `OQ-31`, `OQ-32`, `OQ-35` enviadas ao especialista do método
- [ ] `OQ-30`, `OQ-37` alinhadas com o slug `app-aluno`

Rodada 3A:

- [ ] Campos de reserva em `EstadoFinanceiro` (`engine/estado.py:334-346`): `RESERVA_EXISTE`, `RESERVA_TOTAL: DinheiroTalvez`, `DISPOSICAO_USO_RESERVA`, `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO: DinheiroTalvez`
- [ ] `DINHEIRO_DISPONIVEL: Dinheiro` em `EstadoFinanceiro`
- [ ] Estruturas repetíveis de investimento, ativo e recurso extraordinário (padrão `tuple[Divida, ...]`, `engine/estado.py:342`)
- [ ] Enum de classificação em `engine/tipos.py` com os 4 valores da §13 (domínio fechado; derivação em aberto por `OQ-26`)
- [ ] Impacto de `hash_inputs` (`engine/snapshot.py:119-120`) avaliado e o hash congelado de `app-aluno` (`AC-44`) sinalizado

Rodada 3B:

- [ ] `RESERVA_MOBILIZAVEL` derivada pela §13.1, tipo migrado para `DinheiroTalvez` (hoje `Dinheiro`, `engine/diagnostico.py:637`) — mudança de contrato, checar consumidores
- [ ] `RESERVA_RECOMENDADA` (§13.4) reusando `MODO_ESTABILIZACAO` (`engine/diagnostico.py:486`)
- [ ] `ATAQUE_IMEDIATO_POTENCIAL` (§13.2) e `ATAQUE_IMEDIATO_RECOMENDADO` (§13.3)
- [ ] Trava da §13.1 respeitada: **nenhum percentual automático** de `RESERVA_TOTAL` em lugar nenhum do código
- [ ] Nova família de gabaritos com `GAB-AI-01` a `GAB-AI-07` (terceira família, ao lado de `tests/gabaritos/` e `tests/invariantes/`)
- [ ] `engine/diagnostico.py:674-687` reescrito: a justificativa do placeholder cita `OQ-23` como aberta, e ela foi respondida em 2026-09-07
- [ ] `tasks/motor-calculo.tasks.md:2701-2720` (`T-91`) atualizada: primeiro critério de aceite satisfeito, bloqueio remanescente redefinido

Rodada 3C:

- [ ] `ATAQUE_IMEDIATO_APROVADO` entra no motor como **dado**, nunca derivado (`engine/` é puro)
- [ ] Invariante da hierarquia §13.6 (`POTENCIAL >= RECOMENDADO >= APROVADO >= 0`), padrão `ErroInvariante` de `engine/ciclo_mensal.py:596-602`
- [ ] Injeção no cronograma sem violar a trava `A-04`/`F-02` (`engine/ciclo_mensal.py:583-602`)
- [ ] `GAB-AI-08` ponta a ponta
- [ ] `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes reexecutados — atenção a `mes_primeira_vitoria` (`engine/ciclo_mensal.py:809-812`) e ao método recomendado, ambos sob tolerância zero

## O que isto desbloqueia

- **`T-91`** (`tasks/motor-calculo.tasks.md:2701`) — última tarefa aberta da Rodada 2; efetivamente destravada ao fim de 3B
- **`app-aluno`** — `OQ-37` (montagem do estado a partir do Bloco 4) depende do contrato de 3A; `OQ-30` (confirmação do aprovado) depende de 3C
- **`AC-61`** (`specs/motor-calculo.spec.md:268`) — hoje verificável só por tipo/posição; passa a ser verificável por valor

---
---

# Discovery — Rodada 4: Necessidade Financeira Imediata e Classificação de Ativos (fechamento de `OQ-29`/`OQ-26`/`OQ-27`)

| Campo | Valor |
| ----- | ----- |
| Slug afetado | `motor-calculo` (Rodada 1 `78/78` · Rodada 2 `13/14` · Rodada 3 `T-102`–`T-116` — esta é a quarta rodada) |
| Origem do pedido | Documento canônico *"PIQ v1.0.1 — Fechamento Canônico — Necessidade Financeira Imediata e Classificação de Ativos"*, entregue pelo especialista do método em **2026-09-09** |
| Motivo | `OQ-29`, `OQ-26` e `OQ-27` (levantadas na Rodada 3) foram respondidas. A fórmula de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`, a regra de derivação da classificação de ativos e a fórmula de `VALOR_LIQUIDO_REALIZAVEL_ATIVO(_DISPONIVEL)` agora existem |
| Fonte normativa | `specs/motor-calculo.spec.md` **§14** ("Definições incorporadas — Rodada 4"), transcrição integral, marcada **congelada**: *"Nenhuma dessas decisões fica a critério do desenvolvedor"* |
| Lacuna residual | `OQ-38` (renda recorrente de veículo) segue **aberta** — não é resolvida por este documento de fechamento, nem por este discovery |

## Por que isto NÃO fecha a Rodada 3 inteira

A Rodada 3 deixou dois placeholders explícitos em `engine/diagnostico.py:764-765`
(hoje `:849-850`, ver §5 abaixo): `RESERVA_MOBILIZAVEL` já é valor real desde
`T-114`; `ATAQUE_IMEDIATO_RECOMENDADO` continua `dinheiro(0)` porque sua fórmula
(§13.3) exige `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` por parâmetro, e essa
variável não tinha fórmula fechada. A §14 fecha exatamente essa fórmula — mas
fechar a fórmula não é o mesmo que ligá-la em `calcular_diagnostico`. Como a
Rodada 3 registrou em `AMB-R3-01`: a assinatura de `calcular_diagnostico(estado,
parametros)` foi mantida deliberadamente sem a "peça que falta", com a decisão
de que ela mudaria quando a peça existisse. Ela existe agora — então `AMB-R3-01`
deixa de valer, e o que a substitui **não está decidido em lugar nenhum**. Ver
§5.

Este documento segue o mesmo método das Rodadas 2 e 3: onde a §14 é explícita,
transcreve e aponta; onde a §14 é silenciosa ou colide com modelagem já feita,
registra a lacuna como questão aberta (`sdd.config.md` §3, "ambiguidade não se
adivinha"), continuando a numeração local a partir de `OQ-39` (`OQ-38` já
ocupada pela lacuna de renda de veículo, registrada pelo próprio Spec Agent em
`specs/motor-calculo.spec.md:1978-1987`).

## 1. Inventário de variáveis de entrada — o que existe e o que falta

Varredura própria em `engine/estado.py`, `engine/gates.py`, `engine/tipos.py`,
`collection/registros/bloco-04.yaml`, confrontada com a §14.

### 1.1. `DIVIDA_STATUS_ESTRATEGICO`, `Gate 1/Gate 3 = PENDENTE` — já existem, mas não em `Divida`

**Achado que corrige uma premissa do briefing.** `DIVIDA_STATUS_ESTRATEGICO`
e `GATE_PENDENTE` **não são campos de `Divida`** (`engine/estado.py:426-449`,
lido integralmente — a dataclass tem exatamente 17 campos e nenhum se chama
`DIVIDA_STATUS_ESTRATEGICO` nem `GATE_PENDENTE`). Eles são campos de **saída**
de `ResultadoGates` (`engine/gates.py:278-280`), produzidos por
`determinar_status_estrategico` (`:677-776`) — uma função por dívida — e
agregados para o inventário inteiro por `ParticaoElegibilidade`
(`engine/gates.py:779-815`, produzida por uma função de particionamento ainda
não lida neste discovery, mas cujo contrato de saída já está claro):

```python
@dataclass(frozen=True, slots=True)
class ParticaoElegibilidade:
    elegiveis: tuple[Divida, ...]
    ORDEM_ACOES: tuple[AcaoRequerida, ...]
    bloqueadas: tuple[ResultadoGates, ...]
```

Ou seja: "Gate 1 = PENDENTE" e "Gate 3 = PENDENTE" **não são testáveis sobre um
`Divida` isolado** — são testáveis sobre o `ResultadoGates` daquela dívida
(`GATE_PENDENTE.INFORMACAO` para Gate 1; `GATE_PENDENTE.TRANSFORMACAO` para
Gate 3, `engine/tipos.py:75-87`), que só existe depois que a dívida **já
atravessou os gates**. `NECESSIDADE_IMEDIATA_DIVIDA(divida)` (§14.1.1), tal
como a §14 a escreve, não é uma função pura de `Divida` — é uma função de
`Divida` **e** do `ResultadoGates` correspondente (ou, de forma equivalente,
do par `(divida, particao)` para localizar onde aquela dívida caiu). Isso
importa diretamente para §3 abaixo (onde a função deveria viver).

### 1.2. `VALOR_ACAO_FINANCEIRA_IMEDIATA` — não existe, e o candidato mais próximo não serve

Busca por `VALOR_ACAO_FINANCEIRA_IMEDIATA` em todo o repositório: zero
ocorrências fora da spec e deste discovery.

A §14.2.1 a define como "variável interna derivada... de valor monetário já
conhecido na operação, proposta, acordo, oportunidade, regularização ou
intervenção" — não uma nova pergunta. Investiguei os três candidatos que já
existem no motor:

| Candidato | Onde | Cobre o quê | Por que não serve sozinho |
| --- | --- | --- | --- |
| `Divida.VALOR_QUITACAO_HOJE: DinheiroTalvez` | `engine/estado.py:433` | Valor de quitação à vista, avaliado no Gate 1 (`resultado_valor_relevante`) | É insumo de `VALOR_RELEVANTE_PARA_QUITACAO`, que a §14.1.1 já usa como ramo **separado** ("SENÃO SE status estratégico..."). Não é o mesmo conceito de "valor de uma ação de Gate 2/4 executável agora" — reaproveitá-lo colidiria com a trava de dupla contagem da §14.2.3, que exige que a MESMA dívida não entre duas vezes por dois caminhos diferentes |
| `Oportunidade.beneficio: DinheiroTalvez` | `engine/estado.py:87` | Benefício da oportunidade do Gate 4 | Cobre só Gate 4 ("oportunidade" é uma das seis origens que a §14.2.1 lista); não cobre Gate 2 (risco/regularização/intervenção), que é a outra metade explícita da fórmula ("decorrente de Gate 2 ou Gate 4") |
| `AcaoRequerida` | `engine/gates.py:142-172` | Toda ação emitida por Gate 1/2/3/economia | **Não tem campo monetário** — confirmado por leitura integral da dataclass (`ACAO_ID`, `DIVIDA_ID`, `TIPO_ACAO`, `descricao`, `gate_origem`, `prioridade_excepcional`, `CAMPO_PENDENTE`). A Rodada 3 já havia registrado esta mesma lacuna, em `OQ-29` original: *"ações de `ORDEM_ACOES` entram — e com que valor, se `AcaoRequerida` não tem campo monetário?"* (linha `:670` deste arquivo, seção "12.1" da Rodada 3) |

**Conclusão verificada, não presumida do resumo do pedido:** não existe hoje,
em nenhuma dataclass do motor, um campo que sirva como
`VALOR_ACAO_FINANCEIRA_IMEDIATA` para o par (Gate 2, Gate 4) de forma unificada.
A pergunta concreta que fica é: esse valor precisa ser um **novo campo
monetário em `AcaoRequerida`** (mudança de contrato de uma dataclass que
`app-aluno` já consome — mesma classe de risco de `RF-31`/`RF-41`), ou um
**campo novo em `Divida`** (ex.: `VALOR_ACAO_FINANCEIRA_IMEDIATA:
DinheiroTalvez`, ao lado de `VALOR_QUITACAO_HOJE`), calculado antes dos gates
e consultado por eles? As duas leituras têm consequências de contrato bem
diferentes:

- **Se for campo de `AcaoRequerida`**: é adição de campo (aditiva por
  posição, como o padrão já usado nas Rodadas 2/3 para campos novos), mas
  força `AcaoRequerida` a existir **antes** de `NECESSIDADE_IMEDIATA_DIVIDA`
  poder lê-la — hoje `AcaoRequerida` só é produzida **depois** que um gate já
  decidiu bloquear (`ResultadoGates.acao`), então o valor circularia: a
  função de necessidade precisaria do resultado dos gates para achar a ação,
  e ao mesmo tempo a ação precisaria carregar um valor que a necessidade usa.
  Não é logicamente circular (a ordem é gates → ação com valor → necessidade
  lê a ação), mas é uma dependência que a modelagem atual não expressa em
  lugar nenhum.
- **Se for campo de `Divida`**: evita a dependência de ordem acima
  (`NECESSIDADE_IMEDIATA_DIVIDA` leria `Divida.VALOR_ACAO_FINANCEIRA_IMEDIATA`
  diretamente, sem esperar `AcaoRequerida` existir), mas é campo de
  **entrada** de algo que a §14.2.1 descreve como **derivado** ("valor
  monetário já conhecido na operação, proposta, acordo..." — soa a dado
  coletado, não calculado) — e duplicaria informação que talvez já exista
  em `VALOR_QUITACAO_HOJE` ou em `Oportunidade.beneficio` para os casos que
  eles já cobrem.

Nenhuma das duas é óbvia, e nenhuma está decidida por nenhuma fonte lida.
Ver `OQ-39`.

### 1.3. `ESSENCIALIDADE`, `POSSIBILIDADE_VENDA` — a notícia boa da rodada: já existem na coleta, quase no formato certo

Diferente do que o briefing hipotetiza, a coleta **já tem** os dois conceitos,
com nomes por tipo de ativo (não um nome único normalizado) e com domínio já
compatível:

| Variável da §14 | Coleta (por tipo de ativo) | Linha | Domínio coletado | Domínio da §14 |
| --- | --- | --- | --- | --- |
| `ESSENCIALIDADE` | `IMOVEL_ESSENCIAL` | `bloco-04.yaml:474` | `ESSENCIAL` / `IMPORTANTE` / `NAO_ESSENCIAL` | `ESSENCIAL` / `IMPORTANTE` / `PARCIAL` / `NAO_ESSENCIAL` |
| `ESSENCIALIDADE` | `VEICULO_ESSENCIAL` | `:645` | `ESSENCIAL` / `IMPORTANTE` / `NAO_ESSENCIAL` | idem |
| `ESSENCIALIDADE` | `OUTRO_ATIVO_ESSENCIAL` | `:920` | `ESSENCIAL` / `NAO_ESSENCIAL` (dois valores, sem `IMPORTANTE`) | idem |
| `POSSIBILIDADE_VENDA` | `POSSIBILIDADE_VENDA_IMOVEL` | `:496` | `NAO` / `EXTREMO` / `TALVEZ` / `SIM` / `JA_PRETENDE` | `NAO` / `EXTREMO` / `TALVEZ` / `SIM` / `JA_PRETENDE` — **idêntico** |
| `POSSIBILIDADE_VENDA` | `POSSIBILIDADE_VENDA_VEICULO` | `:667` | idem, cinco valores | idêntico |
| `POSSIBILIDADE_VENDA` | `POSSIBILIDADE_VENDA_OUTRO_ATIVO` | `:940` | idem, cinco valores (não lido linha a linha, mas o padrão se repete nas outras duas fichas) | idêntico |

`POSSIBILIDADE_VENDA` bate exatamente com a §14.4 — nenhuma decisão de
normalização necessária além de dar um nome único de domínio de motor
(mesmo padrão já usado por `RESERVA_EXISTE`/`DISPOSICAO_USO_RESERVA` na
Rodada 3, que traduziram domínios de coleta em enums de `engine/tipos.py`).

`ESSENCIALIDADE` tem uma divergência real: a §14.5/§14.6 distingue quatro
classes (`ESSENCIAL`, `IMPORTANTE`, `PARCIAL`, `NAO_ESSENCIAL`), com `§14.6`
tratando `IMPORTANTE` e `PARCIAL` com a **mesma regra**
("SE ESSENCIALIDADE em {IMPORTANTE, PARCIAL}"). A coleta hoje só produz três
valores para imóvel/veículo (sem `PARCIAL`) e dois para outro ativo (sem
`IMPORTANTE` nem `PARCIAL`). Como a §14.6 trata `IMPORTANTE` e `PARCIAL`
identicamente, a ausência de `PARCIAL` na coleta não é bloqueante para
calcular a classificação — um valor do domínio de motor que a coleta nunca
produz não quebra a função, só fica nunca exercitado por dado real. Não é
o mesmo caso de `OQ-38` (onde falta a variável inteira, não um valor do
domínio). Mas o **nome do campo** ainda precisa de decisão: `Divida`... não,
`ItemAtivo` tem hoje `ITEM_ID`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`,
`CLASSIFICACAO_MOBILIZACAO` — **nenhum campo de essencialidade ou de
possibilidade de venda** (`engine/estado.py:390-392`, lido integralmente).
Ver §2 abaixo — isto não é um acréscimo trivial, é inversão do contrato.

### 1.4. `SALDO_PASSIVO_VINCULADO`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO`, `CUSTO_DESMOBILIZACAO_INVESTIMENTOS` — não existem em `ItemAtivo`/`ItemInvestimento`

Confirmado por leitura integral de `ItemAtivo` (`engine/estado.py:376-395`) e
`ItemInvestimento` (`:349-372`): nenhum dos dois tem campo de passivo
vinculado nem de custo de desmobilização. Isto é esperado e coerente com a
decisão deliberada da Rodada 3 — `ItemAtivo.VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`
foi modelado como **já apurado** (`OQ-27` estava aberta), não com os
componentes brutos da fórmula. A coleta já os tem, com nomes por tipo de
ativo: `CUSTOS_ESTIMADOS_DESMOBILIZACAO (imóvel)` (`bloco-04.yaml:516`),
`(veículo)` (`:772`), `(outro)` (`:960`); `SALDO_FINANCIAMENTO_IMOVEL (=
SALDO_PASSIVO_VINCULADO)` (`:400`), `SALDO_FINANCIAMENTO_VEICULO (=
SALDO_PASSIVO_VINCULADO)` (`:605`), `SALDO_PASSIVO_VINCULADO (outro)`
(`:868`) — já achados e citados no discovery da Rodada 3 (`OQ-27`). A §14.12
agora fecha a fórmula que os consome.

### 1.5. `LIQUIDEZ_INVESTIMENTOS`, `DISPOSICAO_USO_INVESTIMENTO` — não existem em `ItemInvestimento`

`ItemInvestimento` hoje (`engine/estado.py:349-372`) tem `ITEM_ID`,
`VALOR_LIQUIDO_REALIZAVEL`, `POSSUI_LIQUIDEZ: bool`,
`CLASSIFICACAO_MOBILIZACAO` — um booleano de liquidez (sim/não), não o
domínio de seis valores que a §14.3.1 exige (`D0`, `D1`, `D7`, `D30`,
`MAIS_30`, `BLOQUEADO`, já citado no discovery da Rodada 3 a partir de
`bloco-04.yaml:239-245`). `POSSUI_LIQUIDEZ` é insuficiente para a Regra 1
(bloqueio por `LIQUIDEZ_INVESTIMENTOS = BLOQUEADO`) e para a Regra 4
(`D0`/`D1`/`D7` versus `D30` versus `MAIS_30`) — são cortes diferentes do
mesmo conceito de liquidez, e o `bool` atual não expressa nenhum dos dois
com precisão (`BLOQUEADO` não é obviamente "sem liquidez" no sentido que
`POSSUI_LIQUIDEZ=False` hoje comunica; e nada distingue D1 de D30). Não há
`DISPOSICAO_USO_INVESTIMENTO` em lugar nenhum de `engine/estado.py`.

### 1.6. `RENDA_RECORRENTE_ATIVO`/`CUSTO_RECORRENTE_ATIVO` — não existem; a lacuna de `OQ-38`

Confirmado: nenhuma ocorrência de `RENDA_RECORRENTE_ATIVO` ou
`CUSTO_RECORRENTE_ATIVO` em `engine/`. A §14.8 os define como par genérico
("`FLUXO_LIQUIDO_RECORRENTE_ATIVO = RENDA_RECORRENTE_ATIVO -
CUSTO_RECORRENTE_ATIVO`"), mas a coleta **não tem** essas duas variáveis com
esse nome — tem pares por tipo de ativo: `RENDA_IMOVEL`/`CUSTO_IMOVEL`
(`bloco-04.yaml:436`, `:456`), `RENDA_OUTRO_ATIVO`/`CUSTO_OUTRO_ATIVO`
(`:885`, `:902`), e para veículo **só** `CUSTO_RECORRENTE_VEICULO` (`:624`) —
sem `RENDA_VEICULO` nem equivalente. Confirmação de segunda fonte, coerente
com a nota do Spec Agent já registrada em `specs/motor-calculo.spec.md:1978-1987`
(transcrita na íntegra ali, incluindo a menção explícita de que a pergunta já
foi enviada ao especialista em 2026-09-09 e segue sem resposta). Ver §4.

## 2. Impacto na modelagem da Rodada 3 — `ItemAtivo`/`ItemInvestimento` mudam de natureza, não só de tamanho

A Rodada 3 modelou `CLASSIFICACAO_MOBILIZACAO` como **campo obrigatório de
entrada, sem default**, em `ItemAtivo` e `ItemInvestimento`
(`engine/estado.py:369`, `:392`), com justificativa explícita na docstring de
cada um ("a classificação chega JÁ FEITA... o motor recebe, nunca deriva") e
com um teste estático dedicado —
`tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` — que
varre toda função de `engine/**/*.py` por AST e **reprova qualquer função cuja
anotação de retorno mencione `CLASSIFICACAO_MOBILIZACAO`**, em qualquer forma
(direta, união, coleção, string adiada). A própria docstring do teste já
previa este momento: *"Quando `OQ-26` for respondida, este teste não deve ser
apagado em silêncio: ele documenta a data e a fonte em que a derivação passou
a ser permitida"* (`tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py:57-58`).

`OQ-26` foi respondida (§14.3–§14.9). Isso significa que:

1. **O teste estático precisa ser reescrito ou removido**, não apenas
   ajustado — sua premissa inteira (nenhuma função de `engine/` produz
   `CLASSIFICACAO_MOBILIZACAO`) deixa de valer no exato momento em que
   `classificar_investimento`/`classificar_ativo_fisico` (as duas funções que
   a §14.14 já dá em pseudocódigo) passam a existir. Manter o teste sem
   alteração tornaria a própria implementação da §14 impossível de mergear —
   o comando `build`/`test` (`sdd.config.md` §2) reprovaria qualquer PR que
   adicionasse essa função.
2. **`CLASSIFICACAO_MOBILIZACAO` deixa de ser campo de entrada e passa a ser
   campo derivado** em `ItemAtivo`/`ItemInvestimento` — mas os dois são
   `frozen=True, slots=True` (imutáveis por valor, `engine/estado.py:1-16`,
   condição para `RF-10`/`V-01` e memoização segura). Uma dataclass frozen
   não pode ter um campo calculado *a partir dos seus próprios outros
   campos* dentro do `__post_init__` sem o padrão já usado em
   `_recusar_float` (validação, não atribuição) — `object.__setattr__` seria
   necessário, ou a classificação deixa de ser campo da dataclass e passa a
   ser **função separada** chamada pelo consumidor (`calcular_ATIVOS_RECOMENDADOS`
   e as demais funções de `ataque_imediato.py` passariam a receber os campos
   brutos do item e chamar `classificar_ativo_fisico(...)` internamente, em
   vez de ler `item.CLASSIFICACAO_MOBILIZACAO` direto). As duas soluções têm
   consequências de contrato muito diferentes:
   - **Classificação como campo derivado dentro da dataclass** (via
     `object.__setattr__` no `__post_init__`, padrão que não existe hoje em
     nenhum lugar de `engine/estado.py`): preserva a API de leitura
     (`item.CLASSIFICACAO_MOBILIZACAO` continua existindo e sendo lido pelas
     funções da Rodada 3 sem alteração), mas exige que o item carregue TODOS
     os campos brutos que a classificação usa (`ESSENCIALIDADE`,
     `POSSIBILIDADE_VENDA`, `LIQUIDEZ_INVESTIMENTOS`,
     `DISPOSICAO_USO_INVESTIMENTO`, os componentes de valor líquido) — ou
     seja, o item cresce de 3 campos para potencialmente 8-10.
   - **Classificação como função separada, nunca campo da dataclass**: os
     itens carregam só os campos brutos; nenhuma função de
     `ataque_imediato.py` lê mais `item.CLASSIFICACAO_MOBILIZACAO` — elas
     chamam `classificar_ativo_fisico(item)`/`classificar_investimento(item)`
     no próprio corpo. Isto **muda a assinatura de leitura de todo consumidor
     da Rodada 3** (`calcular_ATAQUE_IMEDIATO_POTENCIAL`,
     `calcular_INVESTIMENTOS_RECOMENDADOS`, `calcular_EXTRAORDINARIOS_RECOMENDADOS`
     não, mas `calcular_ATIVOS_RECOMENDADOS` sim, e o próprio
     `test_sem_derivacao_de_classificacao_mobilizacao.py` precisaria de
     reescrita completa da premissa, não só relaxamento).

   Nenhuma fonte lida decide qual das duas. É retipagem de contrato no
   sentido pleno que `RF-31`/`RF-41` já estabeleceram como padrão de
   cuidado nesta base (varredura de todo consumidor interno,
   `sdd.config.md` §4/§8), não simples acréscimo de campo. Ver `OQ-40`.
3. **`EC-31`** (`specs/motor-calculo.spec.md:487`, "Item de entrada chega sem
   classificação de mobilização... erro de contrato... o motor não escolhe
   uma classe por omissão") **deixa de fazer sentido como está redigido** —
   se a classificação passa a ser derivada, não existe mais "item que chega
   sem classificação": o item chega sem os campos brutos, o que é um erro de
   contrato **diferente**. `AC-67` (mesma spec, `:369`, "não existe nenhuma
   função que derive a classificação... `OQ-26` em aberto") **fica
   factualmente falso** assim que a primeira função de derivação for escrita
   — precisa de nova versão da spec que o revogue explicitamente, no mesmo
   padrão que `AC-86` já exigiu para a docstring de `OQ-23`.

Este é o achado de maior risco da rodada: **não é extensão aditiva, é
inversão de responsabilidade** sobre um contrato que a Rodada 3 desenhou
deliberadamente do jeito oposto, com um teste estático escrito
especificamente para impedir essa inversão até que ela fosse autorizada.
Ela está autorizada agora — mas o *como* fazer a inversão sem quebrar os
oito gabaritos `GAB-AI-01` a `GAB-AI-07`, que constroem `ItemAtivo`/
`ItemInvestimento` diretamente com `CLASSIFICACAO_MOBILIZACAO` já preenchida
(`tests/gabaritos_ataque_imediato/`, oito arquivos, um por gabarito),
não está decidido.

## 3. Onde vive `NECESSIDADE_IMEDIATA_DIVIDA` — acoplamento entre gates e ataque imediato

Como o §1.1 mostrou, `NECESSIDADE_IMEDIATA_DIVIDA(divida)` precisa do
`ResultadoGates`/`GATE_PENDENTE` daquela dívida, não só de `Divida`. Isso
levanta a mesma pergunta que o briefing antecipa: a função deveria viver em
`engine/gates.py` (perto de `ResultadoGates`/`ParticaoElegibilidade`, de onde
ela lê) ou em `engine/ataque_imediato.py` (perto das outras oito funções
puras que a consomem, via `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` por
parâmetro)?

A Rodada 3 já registrou, em `engine/diagnostico.py:792-803`, um ciclo de
import real entre `diagnostico` → `ataque_imediato` → `ciclo_mensal` →
`diagnostico`, contornado com **import local** dentro de
`calcular_diagnostico` — tratado como dívida técnica documentada, não
resolvido estruturalmente. Colocar `NECESSIDADE_IMEDIATA_DIVIDA` em
`ataque_imediato.py` faria esse módulo **também** importar de `engine/gates.py`
(para os tipos `DIVIDA_STATUS_ESTRATEGICO`/`GATE_PENDENTE`/`ResultadoGates`),
que por sua vez não importa de `ataque_imediato.py` hoje — checado por
`grep` em `engine/gates.py`, nenhuma ocorrência de `ataque_imediato`. Isso não
fecha um ciclo novo (gates.py não precisaria importar de volta), mas aumenta
o acoplamento de um módulo que a Rodada 3 documentou explicitamente como
"não recebe `Parametros` em nenhuma assinatura" e "toda entrada chega por
parâmetro, nunca de `EstadoFinanceiro`" (`engine/ataque_imediato.py:1-45`) —
importar tipos de `gates.py` não viola pureza (são só tipos, não leitura de
estado), mas é uma dependência de módulo que a docstring atual do arquivo não
antecipa.

A alternativa — `NECESSIDADE_IMEDIATA_DIVIDA` em `engine/gates.py`, perto de
`ParticaoElegibilidade` — mantém `ataque_imediato.py` recebendo o resultado já
somado por parâmetro (`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL: Dinheiro`,
exatamente como `RF-48` já exige das outras funções), preservando o desenho
"tudo por parâmetro" sem precisar importar tipos de gate. Mas isso divide a
lógica normativa da §14 entre dois arquivos (§14.1/§14.1.1 em `gates.py`;
§14.3–§14.13 em `ataque_imediato.py` ou em um terceiro módulo novo), quando a
spec trata a seção inteira como uma unidade.

Nenhuma fonte decide isso — nem a §14, que fala de fórmula, não de módulo
Python, nem o plano técnico (que ainda não existe para esta rodada). Ver
`OQ-41`.

## 4. A lacuna de `OQ-38` (renda de veículo) — isolável, confirmado

Reexaminando a matriz de gabaritos (§14.16, doze linhas) e a matriz resumida
(§14.15, dez linhas): **nenhuma delas menciona veículo especificamente**.
`GAB-NFI-10`/`GAB-NFI-11` (os dois que exercitam `FLUXO_LIQUIDO_RECORRENTE_ATIVO`)
usam "ativo não essencial" genérico, sem amarrar a imóvel/veículo/outro. A
matriz resumida também trata "Ativo físico" como categoria única, sem
diferenciar por tipo.

Isso confirma a hipótese do briefing: a lacuna de `OQ-38` é isolável ao ponto
exato em que `classifyPhysicalAsset` (§14.14, pseudocódigo) chega à guarda
`ativo.essencialidade == NAO_ESSENCIAL` com
`ativo.possibilidadeVenda in {SIM, JA_PRETENDE}` — regra 3.7 na notação do
briefing, linha `if ativo.fluxoLiquidoRecorrente is DESCONHECIDO: return
MOBILIZACAO_POSSIVEL` em diante (`specs/motor-calculo.spec.md:1904-1906`).
Para imóvel e outro ativo, `RENDA_IMOVEL`/`CUSTO_IMOVEL` e
`RENDA_OUTRO_ATIVO`/`CUSTO_OUTRO_ATIVO` já existem na coleta (§1.6) e o
caminho é implementável ponta a ponta. Para veículo, o mesmo ramo de código
não tem como calcular `FLUXO_LIQUIDO_RECORRENTE_ATIVO` porque falta a renda.

A recomendação do briefing (implementar tudo; para veículo, parar exatamente
antes de avaliar o fluxo recorrente, sem inventar `RENDA_RECORRENTE_VEICULO =
0`) é a única leitura consistente com `sdd.config.md` §6 ("metodologia não se
decide implementando") — assumir renda zero para veículo seria uma decisão
de metodologia (afirma implicitamente que veículo nunca gera renda
recorrente, o que não é universalmente verdade — aluguel de veículo, uso
como transporte remunerado). A alternativa de **não implementar
`classificar_ativo_fisico` para veículo** também não é isolável de forma
limpa, porque a mesma função serve os três tipos de ativo físico
(a §14 não distingue função por tipo) — o bloqueio é numa branch da mesma
função, não em uma função separada. Isso significa que
`classificar_ativo_fisico` só fica **totalmente** verificável para veículo se
tratar o caso `NAO_ESSENCIAL + {SIM, JA_PRETENDE}` como retornando um valor
que sinalize pendência explícita (ex.: propagar `DESCONHECIDO`, no mesmo
espírito da própria §14.9: *"SE o efeito recorrente for DESCONHECIDO:
CLASSIFICACAO_ATIVO = MOBILIZACAO_POSSIVEL"*) — o que, na leitura mais literal
da §14.9, já é o comportamento correto: se `FLUXO_LIQUIDO_RECORRENTE_ATIVO`
é indisponível por falta de variável de renda (não por falta de resposta do
usuário), o resultado é o mesmo `MOBILIZACAO_POSSIVEL` que a §14.9 já
prescreve para "efeito desconhecido". **Se essa leitura for aceita, `OQ-38`
não bloqueia sequer a implementação de veículo** — a ausência de
`RENDA_RECORRENTE_VEICULO` produziria `DESCONHECIDO` por construção (nenhuma
fórmula tenta somar uma variável inexistente; o código simplesmente não
constrói o argumento `RENDA_RECORRENTE_ATIVO` para veículo e usa o ramo já
previsto pela norma para "desconhecido"). Isso não é o mesmo que decidir
metodologia — é aplicar a regra que a própria §14.9 já escreveu para o caso
de informação ausente. Mas **isso também não está decidido**: é uma leitura
plausível deste discovery, não uma norma. Ver `OQ-42`.

## 5. `ATAQUE_IMEDIATO_RECOMENDADO` sai do placeholder — a mudança de maior risco desta rodada

`engine/diagnostico.py:658` (assinatura) e `:712-727` (docstring do
placeholder) são explícitos: `ATAQUE_IMEDIATO_RECOMENDADO` continua
`dinheiro(0)` "por `OQ-29`... `RF-48`/`AC-80` proíbem buscá-la [a necessidade
elegível]... de onde `calcular_diagnostico` recebe apenas `estado` e
`parametros`". A premissa citada — `OQ-29` aberta — **não é mais verdadeira**.

Isso reabre exatamente a decisão que `AMB-R3-01` fechou "provisoriamente"
(resolvida pelo usuário em 2026-09-07, opção (b): manter a assinatura). A
pergunta que `AMB-R3-01` adiou — o que muda quando a fórmula existir — chegou.
Investigando o que a assinatura precisaria receber:

`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = Σ NECESSIDADE_IMEDIATA_DIVIDA(d)`
para **todas as dívidas do inventário** (§14.1), e cada `NECESSIDADE_IMEDIATA_DIVIDA`
depende do `ResultadoGates` daquela dívida (§1.1 acima). `calcular_diagnostico`
hoje recebe `(estado: EstadoFinanceiro, parametros: Parametros)` — `estado`
tem `dividas: tuple[Divida, ...]` (`:500`), mas **não tem** o resultado dos
gates, porque aplicar os gates é responsabilidade de `engine/gates.py`,
chamada de algum lugar do pipeline que **não é** `calcular_diagnostico` (uma
busca por `aplicar_gates_1_a_4` ou `ParticaoElegibilidade` dentro de
`engine/diagnostico.py` não retorna nenhuma ocorrência). Ou seja:
`calcular_diagnostico` hoje é uma função que nunca aplica gate nenhum — quem
aplica gates é outro ponto do motor (provavelmente `engine/ordem.py` ou
`engine/motor.py`, que orquestra o snapshot completo), fora do escopo lido
neste discovery.

Três desenhos possíveis, nenhum decidido:

1. **`calcular_diagnostico` ganha um parâmetro novo** —
   `particao: ParticaoElegibilidade` (ou equivalente) — e passa a derivar
   `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` internamente, preenchendo
   `ATAQUE_IMEDIATO_RECOMENDADO` de verdade. Isto é mudança de assinatura
   pública — todo chamador de `calcular_diagnostico` (dentro de `engine/`, e
   potencialmente em `app-aluno`, que a Rodada 2/3 já registraram como
   consumidor de `Diagnostico`) precisa passar a fornecer a partição.
2. **`calcular_diagnostico` continua recebendo só `(estado, parametros)`**, e
   quem aplica os gates e calcula a necessidade elegível o faz **fora**,
   passando o resultado para uma função **diferente**, chamada depois de
   `calcular_diagnostico`, que substitui o placeholder — preservando a
   assinatura atual intocada, mas adiando (de novo) o preenchimento real do
   campo para uma segunda etapa do pipeline. Isso reabriria a mesma pergunta
   de "onde vive o segundo estágio" que a Rodada 3 já registrou para
   `ATAQUE_IMEDIATO_APROVADO` (`OQ-30`) — só que agora para o recomendado,
   não para o aprovado, o que é uma novidade: a Rodada 3 nunca cogitou que
   o *recomendado* (não só o *aprovado*) pudesse precisar de uma segunda
   passada.
3. **`Divida` ganha os campos de status estratégico/gate pendente
   diretamente** (desnormalizando `ResultadoGates` de volta para dentro de
   `Divida`), eliminando a dependência de `ParticaoElegibilidade` — mas isso
   contradiria o desenho atual, em que `DIVIDA_STATUS_ESTRATEGICO`/
   `GATE_PENDENTE` são deliberadamente **saída** de uma função (`Divida` é
   entrada pura do usuário; o status estratégico é algo que o motor calcula
   a partir dela, não algo que o usuário declara ou que entra como dado
   bruto). Reverter isso pareceria retroceder uma decisão de design já
   estabelecida desde a Rodada 1.

O desenho (1) é o que o briefing antecipa como mais provável, e a leitura
deste discovery concorda que é o mais coerente com o resto do pipeline — mas
"mais provável" não é "decidido", e o alcance de uma mudança de assinatura
pública de `calcular_diagnostico` (potencialmente maior que `RF-31` ou `RF-41`,
que mudaram só o tipo de um campo já existente, não a lista de parâmetros de
uma função pública) exige o mesmo rigor que `AMB-R3-01` recebeu: registrado
como ambiguidade explícita, não resolvido por conveniência de implementação.
Ver `OQ-43`.

## 6. Impacto em `app-aluno` — o que esta rodada desbloqueia

Sem reabrir nenhuma decisão do lado de `app-aluno` (mesma disciplina da Rodada
3, §"O que isto desbloqueia" daquele bloco): ao fechar `OQ-26`/`OQ-27`/`OQ-29`,
esta rodada remove o motivo de bloqueio de dois pontos já identificados no
discovery da Rodada 3:

- **Fatia 2C de `app-aluno`** (investimentos/ativos como coleção vazia,
  bloqueada por `OQ-26`/`OQ-27`) passa a ter, do lado do motor, a regra de
  classificação e a fórmula de valor líquido realizável disponíveis. Isso não
  significa que a fatia 2C já é executável — depende também de como
  `ItemAtivo`/`ItemInvestimento` mudam de contrato (§2 acima, `OQ-40` ainda
  aberta) e de como as respostas do Bloco 4 chegam até lá (`OQ-37`, Rodada 3,
  ainda registrada como dependente de `app-aluno`).
- **Bloco 10 de `app-aluno`** (`T-77`/`T-78`/`T-79`, bloqueado por `OQ-29`
  segundo o briefing) passa a ter, do lado do motor, a fórmula de
  `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` fechada — mas o campo que essas
  tarefas leem (`Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`) só sai do
  placeholder quando `OQ-43` (§5 acima) for resolvida. Ou seja: `OQ-29` deixar
  de bloquear na *spec* não é o mesmo que o *código* deixar de emitir
  `dinheiro(0)` — a Rodada 4 de implementação real (quando existir) ainda
  precisa entregar a mudança de `calcular_diagnostico` antes que `T-77`–`T-79`
  tenham dado real para consumir. Este discovery não decide o que `app-aluno`
  deve fazer — só registra que o desbloqueio é **parcial**: a norma está
  fechada, a implementação e o contrato de assinatura ainda não.

## 7. Gabaritos de homologação (`GAB-NFI-01` a `GAB-NFI-12`) — quantos são executáveis nesta rodada

Reexame da tabela (§14.16, doze linhas):

| ID | Depende de | Executável nesta rodada? |
| --- | --- | --- |
| `GAB-NFI-01` a `GAB-NFI-05` | `NECESSIDADE_IMEDIATA_DIVIDA` por dívida, dados de gate/ação fornecidos no enunciado | Sim, **se** `NECESSIDADE_IMEDIATA_DIVIDA` for escrita como função pura recebendo `GATE_PENDENTE`/`DIVIDA_STATUS_ESTRATEGICO`/`VALOR_ACAO_FINANCEIRA_IMEDIATA`/`VALOR_RELEVANTE_PARA_QUITACAO` por parâmetro (mesmo padrão de pureza da Rodada 3) — não exige que `OQ-39` (onde mora `VALOR_ACAO_FINANCEIRA_IMEDIATA`) esteja resolvida, porque o gabarito fornece o valor como dado de entrada, não pede que o motor o derive de `AcaoRequerida`/`Oportunidade` reais |
| `GAB-NFI-06` a `GAB-NFI-08` | `classifyInvestment` com campos brutos de investimento fornecidos | Sim, função pura recebendo os campos por parâmetro — não exige resolver `OQ-40` (onde vive a classificação dentro da dataclass), só que a função de classificação exista em algum módulo |
| `GAB-NFI-09` a `GAB-NFI-11` | `classifyPhysicalAsset` com campos brutos de ativo físico fornecidos, nenhum menciona veículo | Sim, pelo mesmo motivo — e confirma o veredito de `OQ-38` no §4: nenhum gabarito de homologação depende da renda de veículo |
| `GAB-NFI-12` | `deriveValorLiquidoRealizavelAtivo`/`_Disponivel` com os três componentes fornecidos | Sim, função pura |

**Veredito: os doze são executáveis como testes de função pura nesta rodada**,
desde que as funções sejam escritas recebendo entradas por parâmetro (mesmo
padrão de pureza que tornou `GAB-AI-01` a `GAB-AI-07` executáveis na Rodada 3
antes de `OQ-26`/`OQ-29` serem respondidas). Nenhum dos doze exige que
`OQ-39`, `OQ-40`, `OQ-41` ou `OQ-43` estejam resolvidas — todos são sobre a
**fórmula**, não sobre **onde ela vive** ou **como o contrato muda**. Isso é
a mesma distinção que a Rodada 3 já registrou em sua §11 ("sete dos oito
gabaritos são testáveis sem resolver as questões mais difíceis, desde que as
funções de derivação sejam puras"): aqui o padrão se repete, com um resultado
ainda melhor (doze de doze, não sete de oito).

O ponto que os doze gabaritos **não** cobrem é a integração — nenhum deles
testa `calcular_diagnostico` ponta a ponta, nenhum verifica que
`ATAQUE_IMEDIATO_RECOMENDADO` deixou de ser `dinheiro(0)` num `Diagnostico`
real, e nenhum verifica que `ItemAtivo`/`ItemInvestimento` reais (não
fixtures de teste unitário) chegam com os campos brutos que a classificação
precisa. Essa lacuna de cobertura é exatamente onde moram `OQ-40` e `OQ-43`.

## 8. Tamanho e proposta de fatiamento

Esta rodada é, por inventário, maior que a Rodada 3 em **superfície de
contrato tocada**, ainda que menor em número de variáveis de entrada novas
(a Rodada 3 modelou ~16 identificadores inexistentes; esta rodada modela
poucos identificadores realmente novos — `VALOR_ACAO_FINANCEIRA_IMEDIATA`,
`LIQUIDEZ_INVESTIMENTOS` no domínio de seis valores, `DISPOSICAO_USO_INVESTIMENTO`,
`ESSENCIALIDADE`/`POSSIBILIDADE_VENDA` normalizados — mas **retipa** ou
**inverte** contratos que a Rodada 3 fixou deliberadamente: `ItemAtivo`,
`ItemInvestimento` (§2), possivelmente `AcaoRequerida` ou `Divida` (§1.2,
`OQ-39`), e possivelmente a assinatura pública de `calcular_diagnostico`
(§5, `OQ-43`) — quatro superfícies de contrato diferentes, cada uma com seu
próprio raio de consumidores.

Isso é honesto de nomear: mudança de contrato em quatro pontos distintos do
motor é mais risco estrutural do que a Rodada 3, que teve **uma** mudança de
contrato clara (`RF-41`, o tipo de `RESERVA_MOBILIZAVEL`) e o resto aditivo.
Proposta de fatiamento, seguindo o mesmo critério da Rodada 3 (separar por
risco e por dependência, não por tamanho):

### Rodada 4A — Classificação de ativos/investimentos (mexe em `ItemAtivo`/`ItemInvestimento`/`engine/tipos.py`)

Implementa `classificar_investimento`/`classificar_ativo_fisico` (§14.3–§14.9,
§14.14) e `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(_DISPONIVEL)` (§14.12) como
funções puras. Resolve/decide `OQ-40` (onde a classificação passa a viver —
campo derivado via `object.__setattr__` ou função separada) antes de
codificar. Fecha `GAB-NFI-06` a `GAB-NFI-12` (sete dos doze). Trata `OQ-38`
conforme a leitura de `OQ-42` (§4): implementa veículo até o ponto em que a
norma já prevê `DESCONHECIDO`/`MOBILIZACAO_POSSIVEL`, sem inventar
`RENDA_RECORRENTE_VEICULO`. Reescreve
`tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` (ou o
substitui por um teste que documente explicitamente a data/fonte da
liberação, como a própria docstring do teste já previa). Não toca em
`calcular_diagnostico` nem em `AcaoRequerida`/`Divida`/`gates.py`.

### Rodada 4B — Necessidade financeira imediata (mexe em `Divida` ou `AcaoRequerida`, gates, possivelmente `calcular_diagnostico`)

Implementa `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`
(§14.1, §14.2). Resolve `OQ-39` (onde mora `VALOR_ACAO_FINANCEIRA_IMEDIATA`)
e `OQ-41` (onde vive a função — `gates.py` ou `ataque_imediato.py`) antes de
codificar. Fecha `GAB-NFI-01` a `GAB-NFI-05` (cinco dos doze) como testes de
função pura, com entradas fornecidas por parâmetro — **não** exige resolver
`OQ-43` para isso, pelo mesmo argumento do §7 (os gabaritos testam fórmula,
não integração).

### Rodada 4C — Integração em `calcular_diagnostico` (maior risco; resolve `AMB-R3-01`/`OQ-43`)

Liga o resultado de 4A + 4B em `calcular_diagnostico`, substituindo o
placeholder de `ATAQUE_IMEDIATO_RECOMENDADO` pelo valor real (§14.2.4,
reaproveitando a fórmula da Rodada 3 sem alteração — "integralmente
preservada", §14.2.4 é explícita). Resolve `OQ-43` (mudança de assinatura de
`calcular_diagnostico` ou desenho alternativo) antes de codificar. Depende de
4A e 4B estarem prontas. Reexecuta `GAB-A`/`GAB-B`/`GAB-C` e os cinco
invariantes (mesmo procedimento que `RF-32`/`RF-41` já exigiram nas rodadas
anteriores, tolerância zero para método recomendado/ordem/gates/status/D*).
Sinaliza `app-aluno` (hash congelado, `T-108` daquele backlog) se
`AcaoRequerida` ou `Diagnostico` mudarem de contrato.

**Recomendação:** 4A e 4B são paralelizáveis entre si (não compartilham
arquivo nem dataclass tocada, exceto pelo enum `CLASSIFICACAO_MOBILIZACAO`
em `engine/tipos.py`, que 4B só lê). 4C não pode começar antes das duas.
Diferente da Rodada 3, aqui **nenhuma das três fatias depende do
especialista** — todas as questões abertas listadas abaixo são decisão
técnica nossa (`sdd.config.md` §3, "decisão técnica nossa" no sentido da
Rodada 3), exceto `OQ-38`, que segue com o especialista e já está confirmada
como não bloqueante para nenhuma das três fatias.

## 9. Questões abertas desta rodada

Numeração continuando a partir de `OQ-39` (`OQ-38` já ocupada pela lacuna de
renda de veículo, registrada em `specs/motor-calculo.spec.md:1986`).
**Nenhuma destas é decidida neste documento.**

| ID | Questão | Por que importa | Bloqueia |
| --- | --- | --- | --- |
| `OQ-39` | **Onde mora `VALOR_ACAO_FINANCEIRA_IMEDIATA`?** Campo monetário novo em `AcaoRequerida` (mudança de contrato de dataclass já consumida por `app-aluno`, mesma classe de risco de `RF-31`/`RF-41`), campo novo em `Divida` (mas soa a dado coletado, não derivado, e duplicaria `VALOR_QUITACAO_HOJE`/`Oportunidade.beneficio` para os casos que eles já cobrem), ou terceiro desenho não cogitado aqui? | Sem decidir, `NECESSIDADE_IMEDIATA_DIVIDA` não tem de onde ler o valor para os ramos de Gate 2/4 | Rodada 4B |
| `OQ-40` | **Como a classificação passa a existir em `ItemAtivo`/`ItemInvestimento`?** Campo derivado via `object.__setattr__` no `__post_init__` (preserva API de leitura, mas exige que o item carregue todos os campos brutos, crescendo de 3 para 8-10 campos), ou função separada nunca armazenada na dataclass (muda a forma de leitura de todo consumidor da Rodada 3, incluindo os oito gabaritos `GAB-AI-*` que constroem itens já classificados)? | Determina se `EC-31`/`AC-67` (spec) precisam de nova versão formal antes ou depois do código, e se os gabaritos `GAB-AI-*` da Rodada 3 continuam válidos como estão | Rodada 4A |
| `OQ-41` | **Em que módulo vive `NECESSIDADE_IMEDIATA_DIVIDA`?** `engine/gates.py` (perto de `ParticaoElegibilidade`, evita `ataque_imediato.py` importar tipos de gate) ou `engine/ataque_imediato.py` (perto das outras funções da §13/§14, mas aumenta o acoplamento de um módulo hoje documentado como recebendo tudo por parâmetro sem depender de outros módulos de domínio) | Não altera o resultado numérico, mas altera a superfície de import entre módulos que já tem uma dívida técnica registrada (`DT-01`, ciclo de import Rodada 3) | Rodada 4B |
| `OQ-42` | **Leitura de `OQ-38` como "desconhecido por construção" é aceitável sem o especialista?** Este discovery propõe que, para veículo, a ausência de `RENDA_RECORRENTE_VEICULO` produza o mesmo resultado que a §14.9 já prescreve para "efeito recorrente desconhecido" (`MOBILIZACAO_POSSIVEL`), em vez de bloquear a implementação de `classificar_ativo_fisico` para veículo inteiramente. É uma leitura textual da norma existente, não uma decisão de metodologia nova — mas não foi confirmada pelo especialista | Se a leitura for rejeitada, `classificar_ativo_fisico` não pode ser aplicada a veículo nesta rodada, e a Rodada 4A perde cobertura para um dos três tipos de ativo físico | Rodada 4A (parcialmente) |
| `OQ-43` | **Como `ATAQUE_IMEDIATO_RECOMENDADO` sai do placeholder em `calcular_diagnostico`?** Três desenhos no §5: (1) nova assinatura recebendo `ParticaoElegibilidade`/inventário pós-gates; (2) segunda passada fora de `calcular_diagnostico`, preenchendo o campo depois; (3) desnormalizar status estratégico de volta para `Divida`. `AMB-R3-01` resolveu manter a assinatura atual *enquanto a fórmula não existisse* — ela existe agora, e a decisão que a ambiguidade adiou não foi tomada em nenhuma fonte | É a mudança de maior risco desta rodada: mexe na função pública mais central do motor, potencialmente com efeito sobre todo chamador de `calcular_diagnostico` dentro e fora de `engine/` | Rodada 4C |

## Resumo executável (checklist)

Pré-requisitos — nenhum é código:

- [ ] `OQ-39` decidida: onde mora `VALOR_ACAO_FINANCEIRA_IMEDIATA`
- [ ] `OQ-40` decidida: campo derivado (`object.__setattr__`) ou função separada para `CLASSIFICACAO_MOBILIZACAO`
- [ ] `OQ-41` decidida: módulo de `NECESSIDADE_IMEDIATA_DIVIDA`
- [ ] `OQ-42` confirmada (ou não) com o especialista: leitura de `OQ-38` como "desconhecido por construção" para veículo
- [ ] `OQ-43` decidida: como `calcular_diagnostico` deixa de emitir o placeholder
- [ ] `OQ-38` (renda de veículo) segue enviada ao especialista, sem bloquear nenhuma das três fatias (confirmado no §4/§7 — nenhum `GAB-NFI` a exige)

Rodada 4A (classificação de ativos/investimentos):

- [ ] `LIQUIDEZ_INVESTIMENTOS` (domínio de seis valores, `D0`/`D1`/`D7`/`D30`/`MAIS_30`/`BLOQUEADO`) e `DISPOSICAO_USO_INVESTIMENTO` modelados em `engine/estado.py`/`engine/tipos.py`, substituindo ou complementando `ItemInvestimento.POSSUI_LIQUIDEZ: bool`
- [ ] `ESSENCIALIDADE`/`POSSIBILIDADE_VENDA` normalizados como enums de motor, alimentados pelos seis campos já existentes na coleta (`IMOVEL_ESSENCIAL`, `VEICULO_ESSENCIAL`, `OUTRO_ATIVO_ESSENCIAL`, `POSSIBILIDADE_VENDA_IMOVEL/VEICULO/OUTRO_ATIVO`)
- [ ] `SALDO_PASSIVO_VINCULADO`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO`, `CUSTO_DESMOBILIZACAO_INVESTIMENTOS` modelados como campos brutos
- [ ] `RENDA_RECORRENTE_ATIVO`/`CUSTO_RECORRENTE_ATIVO` modelados para imóvel e outro ativo; veículo tratado conforme `OQ-42`
- [ ] `classificar_investimento`/`classificar_ativo_fisico` implementadas conforme §14.14, com `CLASSIFICACAO_MOBILIZACAO` passando a ser produzida conforme `OQ-40`
- [ ] `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO`/`_DISPONIVEL` implementadas conforme §14.12
- [ ] `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` reescrito, documentando a data/fonte da liberação
- [ ] `GAB-NFI-06` a `GAB-NFI-12` (sete gabaritos)

Rodada 4B (necessidade financeira imediata):

- [ ] `VALOR_ACAO_FINANCEIRA_IMEDIATA` modelado conforme `OQ-39`
- [ ] `NECESSIDADE_IMEDIATA_DIVIDA` implementada conforme §14.1.1, recebendo `GATE_PENDENTE`/`DIVIDA_STATUS_ESTRATEGICO`/valores por parâmetro (pureza mantida)
- [ ] `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` implementada conforme §14.1 (soma sobre o inventário pós-gates)
- [ ] `GAB-NFI-01` a `GAB-NFI-05` (cinco gabaritos)

Rodada 4C (integração):

- [ ] `OQ-43` resolvida e `calcular_diagnostico` alterada conforme a decisão
- [ ] `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` deixa de ser `dinheiro(0)` — valor real de `RF-47`/§14.2.4
- [ ] `verificar_hierarquia_ataque_imediato` (RF-50, hoje não chamada em `calcular_diagnostico`) passa a ser chamada com os dois valores reais
- [ ] `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes reexecutados, tolerância zero
- [ ] `AC-67`/`EC-31` (`specs/motor-calculo.spec.md`) atualizados ou revogados por nova versão formal da spec, coerente com `OQ-40`
- [ ] `app-aluno`: hash congelado (`T-108` daquele backlog) sinalizado se `AcaoRequerida`/`Diagnostico` mudarem de contrato

## O que isto desbloqueia

- **`app-aluno`, fatia 2C** (investimentos/ativos, bloqueada por `OQ-26`/`OQ-27`) — passa a ter regra de classificação e fórmula de valor líquido disponíveis do lado do motor; ainda depende de `OQ-37` (transporte Bloco 4 → `EstadoFinanceiro`) e de `OQ-40` estar resolvida
- **`app-aluno`, Bloco 10** (`T-77`–`T-79`, bloqueado por `OQ-29`) — a norma está fechada; o campo real só existe depois de 4C (`OQ-43`)
- **`T-91`/Rodada 3** — nenhum impacto adicional: já foi destravada por `T-114` (`RESERVA_MOBILIZAVEL` real); esta rodada só afeta o segundo placeholder, `ATAQUE_IMEDIATO_RECOMENDADO`
