# Plano Técnico — Motor de Cálculo do PIQ

| Campo  | Valor                                            |
| ------ | ------------------------------------------------ |
| Slug   | `motor-calculo`                                  |
| Spec   | [`specs/motor-calculo.spec.md`](../specs/motor-calculo.spec.md) |
| Fonte  | [`specs/piq-app-spec.md`](../specs/piq-app-spec.md) v1.0.1 |
| Status | `rascunho`                                       |
| Autor  | virtushold@gmail.com                             |
| Data   | 2026-09-01                                       |

> **Precedência.** Onde este plano e a spec divergirem, prevalece a spec; onde a
> spec do slug e a canônica divergirem, prevalece a canônica (regra da §1). Este
> plano decide **como construir**, nunca **o que a regra diz**.

---

## 1. Architecture Overview

O motor é uma **função pura**: recebe `EstadoFinanceiro` + `Parametros` e devolve
`SnapshotOrdem`. Não lê relógio, não lê rede, não escreve arquivo. Persistência e
parâmetros entram por **portas** (interfaces), cujos adaptadores vivem fora de
`engine/`. Essa é a condição para o determinismo exigido pela seção 5 da spec e
para que os gabaritos sejam reprodutíveis bit a bit.

```text
                 ┌──────────────── fora do motor (portas) ────────────────┐
                 │  FonteParametros            RepositorioSnapshots       │
                 │  ├─ arquivo JSON (testes)   ├─ arquivo JSONL (testes)  │
                 │  └─ Supabase/Postgres       └─ Supabase/Postgres       │
                 └───────────────────────────────────────────────────────┘
                                │ Parametros (imutável)      ▲ SnapshotOrdem
                                ▼                            │ (append-only)
EstadoFinanceiro ─► [1] DIAGNOSTICO ─► [2] RISCO D.4 ─► [3] CAPACIDADES
   (já coletado)      RF-14/RF-15        RF-18             RF-14
                                                             │
                                                             ▼
                                                      [4] GATES 1..4
                                                          RF-17
                                       ┌─────────────────────┴──────────────┐
                                       ▼                                    ▼
                            DIVIDAS_ELEGIVEIS                        ORDEM_ACOES
                                       │                          (fila paralela)
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
              [5] AVALANCHE      [6] BOLA_DE_NEVE   [7] HIBRIDO
               RF-05/RF-21          RF-06            RF-07
                    └──────────────────┼──────────────────┘
                                       │  cada cenário roda o mesmo
                                       │  [C] CICLO MENSAL M-01..M-12
                                       │      RF-01/RF-02/RF-03/RF-04/RF-22
                                       ▼
                            [8] COMPARACAO DE CENARIOS
                                RF-19 (empate material 1%)
                                RF-20 (proximidade 5% + 2 meses)
                                       ▼
                            [9] STATUS_METODO + RECOMENDACAO
                                RF-08 · S-01..S-05
                                       ▼
                            [10] ORDEM_QUITACAO + JUSTIFICATIVA_POSICAO
                                 RF-09 · Q-01..Q-05
                                       ▼
                            [11] SNAPSHOT carimbado
                                 RF-10 · V-01..V-03 (ENGINE_VERSION,
                                 PARAMETROS_VERSION)
```

Duas leis de arquitetura, ambas derivadas de requisito:

1. **`engine/` não conhece persistência nem Supabase.** Só assim `RF-12`
   (determinismo decimal) e a NFR de determinismo são verificáveis: um teste
   consegue rodar o motor inteiro sem processo externo.
2. **O ciclo mensal `M-01..M-12` existe uma única vez no código.** Os três
   métodos diferem apenas na *função de seleção de alvo* injetada
   (`SelecionarAlvo`). A canônica §5 é explícita: *"o que muda entre os métodos é
   a regra de seleção do alvo, não o ciclo"*. Duplicar o ciclo por método é o
   caminho mais curto para `AC-13`, `AC-14` e `AC-15` divergirem entre si.

---

## 2. Tech Stack

**Critério eliminatório** (§5 da spec, "ponto flutuante binário é proibido"):
a linguagem precisa de aritmética decimal exata e, de preferência, precisa
**recusar** a mistura acidental com binário. Toda opção que não passasse nesse
crivo foi descartada antes de qualquer outra consideração.

| Escolha | Uso | Justificativa (ancorada em `RF-NN`) |
| --- | --- | --- |
| **Python 3.12+** | linguagem do motor | `RF-12`. `decimal.Decimal` é da biblioteca padrão, precisão arbitrária, contexto explícito. Decisivo: `Decimal + float` levanta `TypeError` — a linguagem **impede** a contaminação binária, não apenas a desaconselha. Descartado **TypeScript/Node + decimal.js**: `new Decimal(x).plus(0.1)` aceita o float silenciosamente, e o risco listado na §8 da spec ("divergência de centavos nos gabaritos") deixaria de ser detectável pelo compilador. Descartado **Apps Script** — ver `RISCO-15.2` na §10. |
| **`decimal` (stdlib)** | toda aritmética monetária e de taxas | `RF-12`, `G-01`. Zero dependência. Contexto único e explícito em `engine/precisao.py` (`prec=34`, decimal128), aberto com `decimal.localcontext()` na fronteira do motor — nunca herdando o contexto ambiente, que é *thread-local* e quebraria o determinismo. |
| **`json` (stdlib) com `parse_float=Decimal`** | leitura dos 44 `P_*` | `RF-13`, `AC-17`. `json.load(f, parse_float=Decimal)` converte literais numéricos direto em `Decimal`, sem passar por `float` em nenhum momento. TOML (`tomllib`) foi descartado: seu tipo numérico é IEEE-754 e a conversão passaria por binário. |
| **`dataclasses(frozen=True, slots=True)` + `enum`** | modelo de dados | `RF-10`/`V-01` (snapshot nunca sobrescrito: imutabilidade no tipo, não na disciplina), `RF-17` (máquina de estados como `enum`, não string solta), e memoização segura (`§10`, custo do Híbrido) — instâncias congeladas são hasheáveis por valor. |
| **mypy (strict)** | verificação estática | `RF-16`/`AC-21`. `DESCONHECIDO` é modelado como tipo-soma; com `strict` + checagem de exaustividade, **esquecer de tratar `DESCONHECIDO` vira erro de compilação**, não bug silencioso de produção. É o mecanismo mais barato que existe para a trava "não inventar dado". |
| **ruff** | lint + regras customizadas | `AC-17` e `RF-12`. Além do lint padrão, hospeda a proibição de `float`/literal numérico de parâmetro dentro de `engine/` (reforçada por teste de AST — ver §9). |
| **pytest** | suíte de gabaritos, invariantes e regras | Seção 5 do `sdd.config.md`. `parametrize` mapeia 1 teste ↔ 1 `AC-NN`/regra; marcadores separam `gabarito`, `invariante`, `regra` e `desempenho`. |
| **Hypothesis** *(escopo limitado)* | testes de propriedade de `A-04` e `F-03` | `RF-03`, `RF-04`. "Nenhum valor desaparece da simulação" e "nenhum valor é contado duas vezes" são invariantes universais, não exemplos; testar por exemplo deixa buraco. Usada com `derandomize=True` para não violar o determinismo da CI. Única dependência de teste não-stdlib. |
| **Supabase (Postgres gerenciado)** | `parametros` e `snapshots` em execução real | `RF-13` e `RF-10`. Ver a avaliação honesta abaixo. |
| **psycopg 3** | driver do adaptador Postgres | `RF-12`. Mapeia `numeric` ↔ `Decimal` nativamente, sem passar por `float`. Descartado o cliente REST `supabase-py`: o transporte é JSON e reintroduziria conversão numérica na fronteira, exatamente onde `RF-12` não pode ceder. |
| **FastAPI + uvicorn** *(fronteira, opcional neste slug)* | expor o motor a `collection/` e `report/` | Não é requisito deste slug; entra aqui só para registrar que a arquitetura **não inviabiliza** os slugs seguintes. Não é implementado agora. |

### 2.1. Supabase — avaliação, não aceite automático

O usuário sugeriu Supabase. Avaliado contra requisito, e não contra
conveniência:

**Onde Supabase ganha, com requisito atrás:**

- `RF-12`: o tipo `numeric` do Postgres é decimal exato de precisão arbitrária.
  É o único armazenamento gratuito e gerenciado da mesa que **não** degrada o
  valor monetário para binário no caminho de ida e volta. Google Sheets (a
  recomendação da §15.2 da canônica) armazena tudo como `double` — reprovado no
  critério eliminatório.
- `RF-10` / `V-01`: imutabilidade do snapshot deixa de ser convenção e vira
  **privilégio**. `REVOKE UPDATE, DELETE ON snapshots` + trigger que levanta
  exceção transforma "ordem nunca sobrescrita" em garantia do banco. Nenhum
  arquivo em disco oferece isso sem código.
- `RF-13` / `US-06`: a tabela `parametros` tem editor visual. O especialista muda
  `P_MESES_VITORIA_RAPIDA` sem abrir o repositório — que é literalmente o texto
  da `US-06`.
- Slugs futuros: `collection/` precisará de Auth, upload e API; `report/` precisa
  de fila. Escolher Postgres agora evita uma migração depois.

**Onde Supabase é recusado, e isso é decisão deste plano:**

- **Nada de regra de negócio em `plpgsql`.** Nenhum gate, nenhum ranqueamento,
  nenhuma fórmula da §11. Regra em SQL não é testável contra `GAB-A`/`GAB-B`/
  `GAB-C` no mesmo processo, cria uma segunda fonte da verdade e viola o
  princípio de que a metodologia não se decide implementando.
- **`engine/` não importa nada de Supabase.** O motor fala com
  `FonteParametros` e `RepositorioSnapshots`. Trocar Supabase por Postgres nu,
  SQLite ou arquivo é trocar um adaptador de ~150 linhas.
- **Neste slug o Supabase é opcional.** Toda a suíte de homologação roda com os
  adaptadores de arquivo. Se a conta do Supabase não existir, o motor está
  igualmente pronto e verificado.

**Plano gratuito e o que acontece ao crescer** (valores do plano Free vigentes;
confirmar na contratação):

| Limite Free | Impacto no PIQ | O que fazer ao estourar |
| --- | --- | --- |
| ~500 MB de banco | Um snapshot completo de carteira de 30 dívidas fica na casa de dezenas de KB. Cabem dezenas de milhares de snapshots. Não é o gargalo do piloto. | Plano Pro (~US$ 25/mês) **ou** arquivar snapshots antigos em JSONL versionado. |
| 2 projetos ativos | Suficiente para `dev` + `piloto`. | Self-host. |
| **Pausa após ~7 dias sem atividade** | **É o risco operacional real**, não o espaço. Um piloto com uso esporádico acorda com o banco pausado. | *Keep-alive* agendado, ou aceitar o *cold start* manual, ou self-host. |
| ~5 GB de egress | Irrelevante para JSON de plano. | — |
| Sem backup automático (Free) | `V-01` fala em preservar histórico; perder o banco perde a auditoria. | Exportação periódica dos snapshots para arquivo versionado — **já necessária** pelo adaptador de arquivo existir. |

**Escada de saída, sem custo:** o núcleo do Supabase é open source (Apache-2.0) e
roda em Docker num VPS próprio. Como só usamos Postgres padrão (`numeric`,
`jsonb`, privilégios, triggers), a migração para Supabase self-hosted, Neon,
Postgres em VPS ou até SQLite é uma troca de string de conexão. Isso é
consequência direta da lei nº 1 da §1 — e é a única razão pela qual aceitar
Supabase agora não cria dependência.

---

## 3. Project Structure

Respeita a §3 do `sdd.config.md`. **Uma divergência**, declarada e justificada:
`persistencia/`.

| Caminho | Responsabilidade | Novo? |
| --- | --- | --- |
| `parameters/parametros-1.0.1.json` | Os 44 `P_*` ativos + `REGRA_*` + `ENGINE_VERSION` + `PARAMETROS_VERSION` + `DATA_VIGENCIA`. Fonte canônica, versionada no repositório. `RF-13` | sim |
| `parameters/esquema-parametros.json` | JSON Schema: nomes, tipos, obrigatoriedade. Recusa carga incompleta. `RF-13`/`AC-17` | sim |
| `parameters/DEPRECATED.md` | Registra `P_CAIXA_VS_ESTRUTURAL` como deprecado (§11.8/§11.9) e por quê | sim |
| `engine/precisao.py` | Contexto decimal único, `quantizar_exibicao`. `G-01`, `G-02` | sim |
| `engine/tipos.py` | `Dinheiro`, `DESCONHECIDO`, enums de status. `RF-12`, `RF-16` | sim |
| `engine/parametros.py` | Porta `FonteParametros` + validação de carga. `RF-13` | sim |
| `engine/estado.py` | `EstadoFinanceiro`, `Divida`, `EstadoSimulacao` | sim |
| `engine/diagnostico.py` | Resultado observado/estrutural, gap, piso, fator de segurança, três capacidades, `MODO_ESTABILIZACAO`. `RF-14`, `RF-15` | sim |
| `engine/risco.py` | Regra D.4. `RF-18` | sim |
| `engine/gates.py` | Gates 1–4, `DIVIDA_STATUS_ESTRATEGICO`, `DIVIDA_ELEGIVEL_ORDEM`, `ORDEM_ACOES`. `RF-17` | sim |
| `engine/valor_quitacao.py` | `VALOR_RELEVANTE_PARA_QUITACAO`. `RF-06`, `AC-20`, `AC-21` | sim |
| `engine/trajetoria.py` | Evolução isolada de **uma** dívida + memoização. `RF-05` | sim |
| `engine/ciclo_mensal.py` | `M-01..M-12`, resíduo e fluxo liberado. `RF-01`, `RF-03`, `RF-04` | sim |
| `engine/beneficio_marginal.py` | `BENEFICIO_MARGINAL_AMORTIZACAO` e fallback. `RF-05`, `RF-21` | sim |
| `engine/metodos/avalanche.py` | `O-01..O-03`. `RF-05` | sim |
| `engine/metodos/bola_de_neve.py` | `O-04`, `O-05`. `RF-06` | sim |
| `engine/metodos/hibrido.py` | `H-01..H-08`. `RF-07` | sim |
| `engine/comparacao.py` | `CENARIO_ECONOMICAMENTE_SUPERIOR`, `ECONOMICAMENTE_PROXIMO`. `RF-19`, `RF-20` | sim |
| `engine/status_metodo.py` | `S-01..S-05`, `REVISAO_HUMANA_OBRIGATORIA`. `RF-08` | sim |
| `engine/ordem.py` | `ORDEM_QUITACAO`, `JUSTIFICATIVA_POSICAO`. `RF-09` | sim |
| `engine/troca.py` | `CENARIO_SUBSTITUICAO_EQUIVALENTE`. `RF-11`, `T-01`, `T-02` | sim |
| `engine/eventos.py` | `EVENTO_RECALCULO`, evento futuro previsto. `RF-02`, `RF-22` | sim |
| `engine/snapshot.py` | Montagem e carimbo do snapshot. `RF-10`, `V-01..V-03` | sim |
| `engine/portas.py` | `FonteParametros`, `RepositorioSnapshots` (`Protocol`) | sim |
| `engine/motor.py` | Ponto de entrada único: `calcular_plano(...)` | sim |
| `persistencia/arquivo/` | Adaptadores JSON/JSONL. Padrão em teste e dev | sim |
| `persistencia/supabase/` | Adaptador psycopg + migrações SQL (append-only) | sim |
| `tests/gabaritos/` | `GAB-A`, `GAB-B`, `GAB-C` ponta a ponta | sim |
| `tests/invariantes/` | `GAB-01` a `GAB-05` | sim |
| `tests/regras/` | 1 arquivo por família (`M`, `R`, `A`, `F`, `O`, `H`, `S`, `Q`, `V`, `T`, `G`) | sim |
| `tests/estatica/` | `AC-17` (nenhum `P_*` no código) e `RF-12` (nenhum `float`) | sim |
| `tests/desempenho/` | Orçamento de tempo da NFR de 30 dívidas × 10 anos | sim |
| `tests/fixtures/` | Estados financeiros dos gabaritos, em JSON | sim |
| `collection/`, `report/` | Existem vazios. Escopo de outros slugs | não |

**Justificativa de `persistencia/`.** A §3 do config prevê `parameters/`,
`engine/`, `collection/`, `report/`, `tests/`. Um adaptador de banco não pertence
a nenhuma: se ele entrasse em `engine/`, o motor deixaria de ser executável sem
processo externo e a lei nº 1 da §1 cairia; se entrasse em `parameters/`,
misturaria dado com código; se fosse duplicado em `collection/` e `report/`,
haveria duas conexões e duas verdades. É pasta de infraestrutura compartilhada
pelos três slugs. **Requer atualização da §3 do `sdd.config.md` via `/sdd:config`
antes da implementação.**

---

## 4. Data Model

Contratos e assinaturas. Nomes idênticos aos da spec canônica, caractere por
caractere (§7 do config). Corpo de função é escopo de `/sdd:implement`.

```python
# engine/precisao.py — G-01, G-02
from decimal import Decimal, Context, ROUND_HALF_UP

CONTEXTO_MOTOR: Context   # prec=34 (decimal128). Aberto via localcontext()
                          # na fronteira; jamais herdado do ambiente.

def dinheiro(valor: str | int | Decimal) -> "Dinheiro": ...
    # G-01. Recusa `float` em tempo de execução E de checagem de tipo.
    # É o único construtor autorizado de valor monetário.

def quantizar_exibicao(valor: "Dinheiro") -> Decimal: ...
    # G-01: arredondamento SÓ aqui, 2 casas, ROUND_HALF_UP.
    # Nunca chamado por engine/ — apenas por report/.
```

```python
# engine/tipos.py — RF-12, RF-16
type Dinheiro = Decimal          # sempre exato; nunca float
type Taxa = Decimal              # fração mensal: 4% a.m. == Decimal("0.04")
type Meses = int

class Desconhecido(Enum):
    DESCONHECIDO = "DESCONHECIDO"

DESCONHECIDO: Final = Desconhecido.DESCONHECIDO

# Dado desconhecido é VALOR, não ausência. `None` é proibido para dado
# de negócio: ele significaria "não perguntado", que é outra coisa.
type DinheiroTalvez = Dinheiro | Desconhecido
type TaxaTalvez     = Taxa | Desconhecido

# RF-16/AC-21: com mypy strict, todo consumidor de DinheiroTalvez é obrigado
# a tratar DESCONHECIDO. Esquecer não compila.

class DIVIDA_STATUS_ESTRATEGICO(Enum):     # RF-17 · Definições §6, §7
    INFORMACAO_PENDENTE   = "INFORMACAO_PENDENTE"      # Gate 1 · QUITADA_A_CONFIRMAR
    INTERVENCAO_PENDENTE  = "INTERVENCAO_PENDENTE"     # Gates 2 e 3 — distinguidos por GATE_PENDENTE
    EM_ANALISE            = "EM_ANALISE"               # STATUS_DIVIDA = OUTRA
    PRONTA_PARA_ORDENACAO = "PRONTA_PARA_ORDENACAO"
    EM_ATAQUE             = "EM_ATAQUE"

class GATE_PENDENTE(Enum):                 # RF-17 · AC-43, AC-44 · Definições §7.1
    """Separa *o que a dívida é* de *o que a trava*. Interno ao motor —
    nunca é pergunta ao usuário. Gates 2 e 3 compartilham o mesmo estado
    estratégico e só diferem aqui."""
    INFORMACAO      = "INFORMACAO"
    CONTENCAO_RISCO = "CONTENCAO_RISCO"    # Gate 2
    TRANSFORMACAO   = "TRANSFORMACAO"      # Gate 3
    OPORTUNIDADE    = "OPORTUNIDADE"       # Gate 4
    NENHUM          = "NENHUM"

class STATUS_DIVIDA(Enum):                 # RF-17 · B5.A04 · Definições §6
    """Estado operacional declarado. NÃO decide elegibilidade — os gates decidem."""
    ATIVA = "ATIVA"; EM_ACORDO = "EM_ACORDO"
    COBRANCA_SEM_PAGAMENTO = "COBRANCA_SEM_PAGAMENTO"
    QUITADA_A_CONFIRMAR = "QUITADA_A_CONFIRMAR"; OUTRA = "OUTRA"

class NIVEL_CONTROLE(Enum):                # RF-23 · Definições §4
    FORTE = "FORTE"; PARCIAL = "PARCIAL"; FRAGIL = "FRAGIL"

class CONFIABILIDADE_DADOS(Enum):          # RF-23 · Definições §5
    ALTA = "ALTA"; MEDIA = "MEDIA"; BAIXA = "BAIXA"

class STATUS_FINANCEIRO(Enum):             # RF-26 · AC-37..AC-39 · Definições §8
    DEFICIT = "DEFICIT"                    # RESULTADO_MENSAL_ATUAL < 0 · vermelho
    EQUILIBRIO_FRAGIL = "EQUILIBRIO_FRAGIL"  # 0 <= RMA < PISO_CAPACIDADE · amarelo
    CAPACIDADE_POSITIVA = "CAPACIDADE_POSITIVA"  # RMA >= PISO · verde

@dataclass(frozen=True)
class PerfilComportamental:
    """RF-23 · Definições §5.1 — as 8 entradas do Bloco 2 que o motor exige.
    Domínios fechados: não criar valores novos. Modeladas como Enum própria
    cada uma, omitidas aqui por brevidade."""
    REGISTRO_GASTOS: REGISTRO_GASTOS
    FREQUENCIA_REGISTRO: FREQUENCIA_REGISTRO
    DEFASAGEM_REGISTRO: DEFASAGEM_REGISTRO
    COBERTURA_PEQUENOS_GASTOS: COBERTURA_PEQUENOS_GASTOS
    COBERTURA_MEIOS_PAGAMENTO: COBERTURA_MEIOS_PAGAMENTO
    CONHECIMENTO_GASTO: CONHECIMENTO_GASTO
    GASTOS_NAO_IDENTIFICADOS: GASTOS_NAO_IDENTIFICADOS
    REVISAO_SEMANAL: REVISAO_SEMANAL

class STATUS_VALIDADE_PROPOSTA(Enum):      # RF-06 · B5.B05B
    VIGENTE = "VIGENTE"; EXPIRADA = "EXPIRADA"
    VALIDADE_DESCONHECIDA = "VALIDADE_DESCONHECIDA"

class ORDEM_STATUS(Enum):                  # RF-21 · AC-09 · AC-33
    DEFINITIVA_NA_DATA = "DEFINITIVA_NA_DATA"; PROVISORIA = "PROVISORIA"

class STATUS_METODO(Enum):                 # RF-08 · S-01..S-05
    DEFINITIVO_NA_DATA = "DEFINITIVO_NA_DATA"; PROVISORIO = "PROVISORIO"

class CLASSIFICACAO_CENARIO(Enum):         # S-01, S-02 — tolerância ZERO entre os dois
    CALCULAVEL = "CALCULAVEL"
    NAO_CALCULAVEL = "NAO_CALCULAVEL"      # rebaixa
    NAO_APLICAVEL  = "NAO_APLICAVEL"       # não rebaixa

class METODO(Enum):
    AVALANCHE = "AVALANCHE"; BOLA_DE_NEVE = "BOLA_DE_NEVE"; HIBRIDO = "HIBRIDO"

class NIVEL_RISCO(Enum):                   # RF-18 · §11.4
    BAIXO = "BAIXO"; MODERADO = "MODERADO"; ALTO = "ALTO"

class EVENTO_RECALCULO(Enum):              # RF-02 · §3.2 · RF-22
    QUITACAO_CONFIRMADA = "QUITACAO_CONFIRMADA"
    ALTERACAO_RENDA = "ALTERACAO_RENDA"; ALTERACAO_DESPESAS = "ALTERACAO_DESPESAS"
    NOVA_DIVIDA = "NOVA_DIVIDA"; RENEGOCIACAO_EXECUTADA = "RENEGOCIACAO_EXECUTADA"
    TROCA_EXECUTADA = "TROCA_EXECUTADA"; RECURSO_EXTRAORDINARIO = "RECURSO_EXTRAORDINARIO"
    INFORMACAO_MATERIAL_CONHECIDA = "INFORMACAO_MATERIAL_CONHECIDA"
    MUDANCA_PATRIMONIAL = "MUDANCA_PATRIMONIAL"; PROPOSTA_TEMPORARIA = "PROPOSTA_TEMPORARIA"
    ALTERACAO_RISCO = "ALTERACAO_RISCO"; OUTRO_MATERIAL = "OUTRO_MATERIAL"
    # R-04: alteração cadastral/cosmética NÃO tem membro aqui — é inexprimível.
```

```python
# engine/estado.py
@dataclass(frozen=True, slots=True)
class Divida:
    DIVIDA_ID: str                                  # O-05/H-04: desempate final
    TIPO_DIVIDA: TIPO_DIVIDA
    STATUS_DIVIDA: STATUS_DIVIDA                    # ciclo de vida (B5.A04)
    SALDO_DEVEDOR_ATUAL: DinheiroTalvez
    VALOR_QUITACAO_HOJE: DinheiroTalvez
    QUITACAO_CONSULTADA: SimNaoTalvez
    STATUS_VALIDADE_PROPOSTA: STATUS_VALIDADE_PROPOSTA
    TAXA_EFETIVA_MENSAL_NORMALIZADA: TaxaTalvez     # fallback 1º de RF-21
    CET: TaxaTalvez                                 # fallback 2º de RF-21
    PARCELA_CONTRATUAL: DinheiroTalvez
    PAGAMENTO_MENSAL_EFETIVO: DinheiroTalvez        # AC-32/GAB-A: pode ser 0
    SEGURO_INCLUIDO_PARCELA: bool                   # GAB-01: informacional
    CUSTO_SEGURO: DinheiroTalvez                    # GAB-01: NUNCA somado à parcela
    PESO_EMOCIONAL: int | Desconhecido              # 0–10 · O-05/H-04
    RENEGOCIACAO_PENDENTE: bool                     # Gate 3
    TROCA_PENDENTE: bool                            # Gate 3
    RISCO_MATERIAL_IMINENTE: bool                   # Gate 2
    OPORTUNIDADE_VIGENTE: Oportunidade | None       # Gate 4

@dataclass(frozen=True, slots=True)
class EstadoFinanceiro:
    DATA_REFERENCIA: date        # INPUT, nunca date.today() — NFR determinismo
    RENDA_TOTAL_RECORRENTE: Dinheiro
    TIPO_RENDA: TIPO_RENDA
    DESPESAS_OPERACIONAIS_ATUAIS: Dinheiro
    DESPESAS_NAO_MENSAIS_NORMALIZADAS: Dinheiro
    CAPACIDADE_ATAQUE_DECLARADA: DinheiroTalvez
    ECONOMIA_POTENCIAL_IMEDIATA: Dinheiro           # GAB-B/EC-11: potencial ≠ base
    INVENTARIO_COMPLETO: bool                       # GAB-02/AC-09
    dividas: tuple[Divida, ...]
    sinais_comportamentais: SinaisComportamentais   # entradas da regra D.4
    CONFIABILIDADE_DADOS: CONFIABILIDADE            # ver BURACO-03
```

```python
# engine/parametros.py — RF-13, AC-17
@dataclass(frozen=True, slots=True)
class Parametros:
    PARAMETROS_VERSION: str
    ENGINE_VERSION: str
    DATA_VIGENCIA: date
    _valores: Mapping[str, Decimal | str | tuple[Decimal, ...]]

    def numero(self, nome: str) -> Decimal: ...
        # KeyError explícito e ruidoso. NUNCA um default. AC-17.

class FonteParametros(Protocol):                    # engine/portas.py
    def carregar(self, versao: str) -> Parametros: ...
```

```python
# engine/diagnostico.py — RF-14, RF-15 · §11.8 · GAB-A, GAB-B
@dataclass(frozen=True, slots=True)
class Diagnostico:
    PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES: Dinheiro
    PAGAMENTOS_EFETIVOS_DIVIDAS: Dinheiro
    RESULTADO_CAIXA_OBSERVADO: Dinheiro
    RESULTADO_MENSAL_ATUAL: Dinheiro
    GAP_CAIXA_VS_ESTRUTURAL: Dinheiro      # §11.8: diagnóstico, SEM limiar
    DEFICIT_MENSAL: Dinheiro
    PISO_CAPACIDADE: Dinheiro              # MAX(P_PISO_ABSOLUTO; P_PISO_PCT × renda)
    STATUS_FINANCEIRO: STATUS_FINANCEIRO   # ver BURACO-04
    MODO_ESTABILIZACAO: bool               # RF-15
    GAP_AUTOPERCEPCAO: bool                # §11.8, P_AUTOPERCEPCAO = 7
    BASE_CONSERVADORA: Dinheiro            # MIN(RESULTADO_MENSAL_ATUAL; DECLARADA)
    FATOR_SEGURANCA: Decimal               # piso P_FATOR_SEGURANCA_MINIMO
    CAPACIDADE_ATAQUE_ATUAL: Dinheiro      # RF-15: 0 em MODO_ESTABILIZACAO
    CAPACIDADE_ATAQUE_CONSERVADORA: Dinheiro   # a única que alimenta o cronograma
    CAPACIDADE_ATAQUE_POTENCIAL: Dinheiro      # EC-11: NUNCA entra no cronograma-base

def calcular_diagnostico(e: EstadoFinanceiro, p: Parametros) -> Diagnostico: ...
```

```python
# engine/risco.py — RF-18 · §11.4 (regra D.4)
@dataclass(frozen=True, slots=True)
class SinalD4:
    nome: str
    ativo: bool
    desconhecido: bool     # AC-25: desconhecido NÃO conta como risco positivo,
                           # mas alimenta a redução de confiabilidade se material

@dataclass(frozen=True, slots=True)
class ClassificacaoRisco:
    sinais: tuple[SinalD4, ...]        # auditabilidade: o revisor refaz a conta
    contagem: int                       # 0=BAIXO · 1–2=MODERADO · 3+=ALTO
    nivel: NIVEL_RISCO

def classificar_RISCO_RECAIDA(...) -> ClassificacaoRisco: ...              # 5 sinais
def classificar_RISCO_COMPORTAMENTAL_GERAL(...) -> ClassificacaoRisco: ... # 6 sinais
```

```python
# engine/gates.py — RF-17 · §11.3
@dataclass(frozen=True, slots=True)
class ResultadoGates:
    DIVIDA_ID: str
    DIVIDA_STATUS_ESTRATEGICO: DIVIDA_STATUS_ESTRATEGICO
    DIVIDA_ELEGIVEL_ORDEM: bool
    gate_bloqueador: Literal[1, 2, 3, 4] | None
    motivo: str                          # entra na JUSTIFICATIVA_POSICAO (Q-05)
    acao: AcaoRequerida | None            # alimenta ORDEM_ACOES

def aplicar_gates(d: Divida, ctx: ContextoGates, p: Parametros) -> ResultadoGates: ...
    # Sequência FIXA: 1 Informação → 2 Contenção → 3 Transformação → 4 Oportunidade.
    # Gate 1 NÃO bloqueia por falta apenas da simulação marginal, se o fallback
    # de §11.1 for possível (RF-21).

@dataclass(frozen=True, slots=True)
class ParticaoElegibilidade:
    elegiveis: tuple[Divida, ...]
    ORDEM_ACOES: tuple[AcaoRequerida, ...]   # fila PARALELA, não é ordem de ataque
    bloqueadas: tuple[ResultadoGates, ...]
    # EC-17: elegiveis == () → não há alvo; o plano vira ação.
```

```python
# engine/trajetoria.py — RF-05 · §11.1 · unidade cara, ver §10
@dataclass(frozen=True, slots=True)
class ChaveTrajetoria:            # hasheável por valor; Decimal compara exato
    DIVIDA_ID: str
    SALDO_DEVEDOR_ATUAL: Dinheiro
    TAXA_EFETIVA_MENSAL_NORMALIZADA: Taxa
    PAGAMENTO_MENSAL_EFETIVO: Dinheiro
    DELTA: Dinheiro
    HORIZONTE: Meses

@dataclass(frozen=True, slots=True)
class Trajetoria:
    DESEMBOLSO_FUTURO: Dinheiro
    MESES_ATE_QUITACAO: Meses | None      # None = estourou o horizonte (EC-13)
    ESTOUROU_HORIZONTE: bool

def simular_trajetoria_isolada(chave: ChaveTrajetoria) -> Trajetoria: ...
    # Pura + memoizada. O cache DEVE ser indistinguível de sua ausência (§9).
```

```python
# engine/beneficio_marginal.py — RF-05, RF-21 · §11.1
@dataclass(frozen=True, slots=True)
class BeneficioMarginal:
    DIVIDA_ID: str
    DELTA_TESTE_AVALANCHE: Dinheiro          # MIN(CAP_CONSERVADORA; VALOR_RELEVANTE)
    DELTA_REALMENTE_APLICADO: Dinheiro
    DESEMBOLSO_FUTURO_SEM_DELTA: Dinheiro
    DESEMBOLSO_FUTURO_COM_DELTA: Dinheiro
    BENEFICIO_MARGINAL_AMORTIZACAO: Decimal | Desconhecido
    origem: Literal["SIMULACAO", "FALLBACK_TAXA", "FALLBACK_CET"]   # AC-33

def calcular_beneficio_marginal(
    d: Divida, delta_disponivel: Dinheiro, p: Parametros
) -> BeneficioMarginal: ...
    # AC-14 · A-03: no reranqueamento intramês, delta_disponivel é
    # RESIDUO_ATAQUE_M — NUNCA a capacidade cheia.
    # AC-33: origem != SIMULACAO ⇒ ORDEM_STATUS = PROVISORIA.
```

```python
# engine/ciclo_mensal.py — RF-01..RF-04 · M-01..M-12
type SelecionarAlvo = Callable[[EstadoSimulacao, Dinheiro], Divida | None]
# ↑ ÚNICO ponto de variação entre Avalanche, Bola de Neve e Híbrido.

@dataclass(frozen=True, slots=True)
class EstadoSimulacao:
    mes: Meses
    saldos: Mapping[str, Dinheiro]
    quitadas: frozenset[str]
    DIVIDA_ALVO_ATUAL: str | None
    CAPACIDADE_ATAQUE_M: Dinheiro
    ATAQUE_NAO_UTILIZADO_ACUMULADO: Dinheiro     # A-04/EC-01
    DESEMBOLSO_ACUMULADO: Dinheiro

@dataclass(frozen=True, slots=True)
class ResultadoMes:
    estado_final: EstadoSimulacao
    quitacoes: tuple[str, ...]
    RESIDUO_ATAQUE_M: Dinheiro                   # A-01
    aplicacoes_residuo: tuple[AplicacaoResiduo, ...]   # A-02, cascata auditável
    ATAQUE_NAO_UTILIZADO: Dinheiro               # A-04
    VALOR_FLUXO_LIBERADO: Dinheiro               # F-01 · §11.7 · entra em m+1
    reranqueamentos: tuple[Reranqueamento, ...]  # R-03: 0, 1 ou vários

def executar_mes(e: EstadoSimulacao, sel: SelecionarAlvo,
                 p: Parametros) -> ResultadoMes: ...
    # M-01..M-09 nesta ordem, sem pular etapa. M-05: alvo preservado.
    # M-07/M-08: laço de resíduo com reranqueamento ANTES de cada aplicação (O-03).
    # F-02/F-03: VALOR_FLUXO_LIBERADO é DEVOLVIDO, não somado aqui.

@dataclass(frozen=True, slots=True)
class Cenario:
    metodo: METODO
    classificacao: CLASSIFICACAO_CENARIO
    ORDEM_QUITACAO: tuple[str, ...]
    PRAZO_TOTAL: Meses
    CUSTO_FUTURO_TOTAL: Dinheiro
    MESES_PRIMEIRA_VITORIA: Meses | None
    meses: tuple[ResultadoMes, ...]      # rastro completo para auditoria (NFR)

def simular_cenario(e: EstadoFinanceiro, dg: Diagnostico,
                    sel: SelecionarAlvo, p: Parametros) -> Cenario: ...
    # M-10/M-11: fluxo liberado incorporado só na abertura de m+1.
    # M-12/R-02: sem quitação e sem evento ⇒ NENHUM reranqueamento (AC-13).
    # EC-13: encerra em P_HORIZONTE_MAXIMO_SIMULACAO e sinaliza.
```

```python
# engine/comparacao.py — RF-19, RF-20 · §11.5 (conceitos DISTINTOS)
@dataclass(frozen=True, slots=True)
class ComparacaoCenarios:
    CENARIO_ECONOMICAMENTE_SUPERIOR: METODO
    empatados_materialmente: tuple[METODO, ...]   # < P_DIFERENCA_ECONOMICA_MATERIAL (1%)
    PENALIDADE_CUSTO: Mapping[METODO, Decimal]
    ATRASO_PRAZO: Mapping[METODO, Meses]
    ECONOMICAMENTE_PROXIMO: Mapping[METODO, bool] # ≤5% E ≤2 meses, CUMULATIVO

def comparar_cenarios(cs: Sequence[Cenario], p: Parametros) -> ComparacaoCenarios: ...
    # RF-19/AC-27/EC-19: menor custo → empate material a 1% → menor PRAZO_TOTAL.
    # RF-20/AC-29: proximidade é medida contra o SUPERIOR, com 5%/2m.
    # Os dois parâmetros nunca se cruzam (risco explícito da §8 da spec).
```

```python
# engine/snapshot.py — RF-10 · V-01..V-03
@dataclass(frozen=True, slots=True)
class PosicaoOrdem:
    posicao: int
    DIVIDA_ID: str
    JUSTIFICATIVA_POSICAO: str                    # Q-05: obrigatória
    valores_de_apoio: Mapping[str, Dinheiro | Decimal]   # o revisor refaz a conta

@dataclass(frozen=True, slots=True)
class SnapshotOrdem:
    SNAPSHOT_ID: str
    versao: int                                   # ORDEM_QUITACAO_V1, V2, ...
    snapshot_anterior_id: str | None              # cadeia preservada
    DATA_REFERENCIA: date
    MOTIVO_RECALCULO: str
    EVENTO_RECALCULO: EVENTO_RECALCULO | None
    hash_inputs: str                              # sha-256 canônico do estado
    estado_inputs: EstadoFinanceiro               # V-02: inputs relevantes
    diagnostico: Diagnostico
    cenarios: Mapping[METODO, Cenario]
    comparacao: ComparacaoCenarios
    METODO_RECOMENDADO_PIQ: METODO
    STATUS_METODO: STATUS_METODO
    ORDEM_STATUS: ORDEM_STATUS
    REVISAO_HUMANA_OBRIGATORIA: bool
    DIVIDA_ALVO_ATUAL: str | None
    PROXIMA_DIVIDA: str | None
    ORDEM_QUITACAO: tuple[PosicaoOrdem, ...]
    ORDEM_ACOES: tuple[AcaoRequerida, ...]
    ENGINE_VERSION: str                           # V-03 · AC-16
    PARAMETROS_VERSION: str                       # V-03 · AC-16

class RepositorioSnapshots(Protocol):             # engine/portas.py
    def anexar(self, s: SnapshotOrdem) -> None: ...   # V-01: append-only
    def obter(self, snapshot_id: str) -> SnapshotOrdem: ...
    def historico(self, caso_id: str) -> Sequence[SnapshotOrdem]: ...
    # Não existe `atualizar` nem `remover`. A porta torna a violação de V-01
    # inexprimível no código, antes de o banco precisar recusá-la.
```

```python
# engine/motor.py — ponto de entrada único
def calcular_plano(
    estado: EstadoFinanceiro,
    parametros: Parametros,
    anterior: SnapshotOrdem | None = None,
    evento: EVENTO_RECALCULO | None = None,
    motivo: str = "",
) -> SnapshotOrdem: ...
    # R-05/EC-09: com evento material, SEMPRE devolve novo snapshot —
    # ainda que método, D* e ordem sejam idênticos.
    # R-02/R-04: sem evento e sem quitação, o chamador NÃO deve invocar.
```

### 4.1. Máquina de estados por dívida (`RF-17`)

Dois eixos **ortogonais**, para não colidir com `STATUS_DIVIDA` (B5.A04):

```text
Eixo 1 — ciclo de vida (STATUS_DIVIDA, coletado):
    ATIVA · EM_ACORDO · COBRANCA_SEM_PAGAMENTO · QUITADA_A_CONFIRMAR · OUTRA

Eixo 2 — DIVIDA_STATUS_ESTRATEGICO (derivado pelos gates, §11.3):

                       ┌──────── Gate 1 falha ────────┐
   (entrada) ─────────►│    INFORMACAO_PENDENTE       │──── dado obtido ───┐
                       └──────────────────────────────┘                    │
                       ┌──── Gate 2 ou Gate 3 falha ──┐                    │
              ────────►│    INTERVENCAO_PENDENTE      │─ executada /       │
                       │  (+ item em ORDEM_ACOES)     │  rejeitada /       │
                       └──────────────────────────────┘  encerrada ─────┐  │
                                                                        ▼  ▼
                       ┌──────────────────────────────────────────────────────┐
                       │            PRONTA_PARA_ORDENACAO                     │
                       └──────────────────────────────────────────────────────┘
                                         │ vira DIVIDA_ALVO_ATUAL
                                         ▼
                       ┌──────────────────────────────────────────────────────┐
                       │                   EM_ATAQUE                          │
                       └──────────────────────────────────────────────────────┘
                                         │ QUITACAO_CONFIRMADA
                                         ▼  (sai do inventário ativo · R-01)

DIVIDA_ELEGIVEL_ORDEM = STATUS_DIVIDA ativa ∧ ¬QUITADA ∧ ¬SUBSTITUIDA
                      ∧ ¬SUSPENSA ∧ status ∈ {PRONTA_PARA_ORDENACAO, EM_ATAQUE}

ORDEM_ACOES é fila PARALELA. Nunca é a ORDEM_QUITACAO.
EC-15: se a própria quitação for a ação que contém o risco e for executável,
       prioridade excepcional COM justificativa expressa.
EC-16/Gate 4: desconto vigente NÃO implica primeiro lugar.
AC-23: risco alto, por si só, NUNCA torna a dívida a primeira.
```

Transições só ocorrem por `EVENTO_RECALCULO` (`R-01`) — nunca por virada de mês
(`R-02`, `AC-13`).

---

## 5. Data Flow

O caminho do dado, com o que acontece quando cada etapa falha:

1. **Carga de parâmetros** (`FonteParametros.carregar(versao)`).
   Valida contra `esquema-parametros.json`: os 44 `P_*` ativos presentes,
   `PARAMETROS_VERSION` conferindo, `P_CAIXA_VS_ESTRUTURAL` **ausente**
   (deprecado, §11.9). *Falha:* `ErroParametros`, aborta. Não existe default —
   um default seria um parâmetro no código, violando `AC-17`.

2. **Validação estrutural do `EstadoFinanceiro`.** O estado já vem coletado
   (Assumption §7 da spec); aqui só se verifica coerência de tipos e ausência de
   `float`. *Falha:* aborta com o campo culpado nomeado.

3. **Derivações comportamentais, em ordem obrigatória** (`RF-23`, `RF-24`,
   `RF-27` · spec §11.10). O grafo é acíclico, mas violá-lo produz resultado
   **silenciosamente errado** — nenhuma exceção é levantada:

   ```
   3a. NIVEL_CONTROLE          ← 8 entradas do Bloco 2 (Definições §4)
                                  ordem: FRAGIL → FORTE → PARCIAL
   3b. CONFIABILIDADE_DADOS    ← NIVEL_CONTROLE + 3 do Bloco 2 (Definições §5)
                                  ordem: BAIXA → ALTA → MEDIA
   3c. RISCO_RECAIDA e RISCO_COMPORTAMENTAL_GERAL  ← D.4 (RF-18)
   3d. INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE      ← 3a + 3c + NECESSIDADE_VITORIA
   ```

   `deriveNivelControle` é raiz e depende só de entrada coletada. **A ordem é
   imposta por construção**, não por convenção: cada função recebe o resultado da
   anterior como parâmetro obrigatório, então pular uma etapa não compila. `3d`
   segue `AC-34`/`AC-35` — `NECESSIDADE_VITORIA ≥ P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA`
   **E** ao menos um sinal comportamental; nenhum dos dois grupos basta sozinho.

4. **Diagnóstico e capacidade** (`RF-14`, `RF-25`, `RF-26`). Devidos vs. efetivos
   (`AC-32`/`GAB-A`: efetivo 0 é valor legítimo), resultado observado, resultado
   estrutural, `GAP_CAIXA_VS_ESTRUTURAL` (sem limiar, §11.8).

   `PISO_CAPACIDADE = MAX(P_ABSOLUTO, RENDA × P_PERCENTUAL)` **classifica** o
   `STATUS_FINANCEIRO` e nunca altera a capacidade (`AC-38`: resultado 200 com
   piso 300 ⇒ capacidade 200, não 0 e não 300).
   `CAPACIDADE_ATAQUE_ATUAL = MAX(0, RESULTADO_MENSAL_ATUAL)`.

   `FATOR_SEGURANCA` é **subtrativo** (`AC-36`): somar as quatro reduções, subtrair
   de 1, e só então aplicar `MAX(P_FATOR_SEGURANCA_MINIMO, ...)`. Composição
   multiplicativa é proibida. As quatro parcelas são independentes — a redução por
   risco comportamental e a por histórico de recaída não se absorvem (`AC-26`).

   *Falha:* dado monetário `DESCONHECIDO` material ⇒ diagnóstico parcial +
   `INVENTARIO_COMPLETO` tratado como falso (`GAB-02`).

5. **Modo estabilização** (`RF-15`). `RESULTADO_MENSAL_ATUAL < 0` ⇒
   `CAPACIDADE_ATAQUE_ATUAL = 0`, `MODO_ESTABILIZACAO = SIM`, cronograma
   rebaixado a fase 2 condicional (`GAB-04`). O motor **continua** e devolve os
   cenários — marcados como condicionais; quem os apresenta como fase 2 é o
   `report/` (`AC-11`).

6. **Gates 1–4** (`RF-17`), na sequência fixa. Produz `elegiveis`,
   `ORDEM_ACOES`, `bloqueadas`. *Falha total:* `elegiveis == ()` ⇒ `EC-17`, não
   há alvo, o plano é ação e o cronograma é condicional.

7. **Três cenários.** Cada um roda `simular_cenario` com sua `SelecionarAlvo`.
   Dentro do mês: `M-01`→`M-04`; se quitou, `RESIDUO_ATAQUE_M` (`A-01`);
   reranqueia (`O-03`) e aplica em cascata com
   `DELTA_TESTE_AVALANCHE_RESIDUO = MIN(RESIDUO_ATAQUE_M, VALOR_RELEVANTE)`
   (`A-03`, `AC-14`); sobrou sem elegível ⇒ `ATAQUE_NAO_UTILIZADO` (`A-04`,
   `EC-01`). No encerramento: `VALOR_FLUXO_LIBERADO` consolidado (`M-10`) e
   incorporado **só na abertura de m+1** (`M-11`, `F-02`, `AC-15`). Sem quitação
   e sem evento, o mês seguinte **não** reranqueia (`M-12`, `R-02`, `AC-13`).
   *Falha:* Híbrido sem candidata ⇒ `NAO_APLICAVEL` (`H-08`, `EC-03`), que **não**
   rebaixa `STATUS_METODO` (`S-02`); benefício marginal insimulável ⇒ fallback
   taxa → CET e `ORDEM_STATUS = PROVISORIA` (`RF-21`, `AC-33`).

8. **Eventos futuros previstos** (`RF-22`). `NOVA_DIVIDA_PREVISTA` ∈
   {SIM, TALVEZ} é filtrado **antes** do passo 7: não vira `Divida`, não altera
   saldo, não entra em `ORDEM_QUITACAO` (`AC-30`). Entra só como sinal de
   `RISCO_RECAIDA` (passo 4) e como alerta na saída.

9. **Comparação** (`RF-19`, `RF-20`) e **status do método** (`RF-08`).
   `S-04`: incompatibilidade grave sem alternativa próxima ⇒ `PROVISORIO` +
   `REVISAO_HUMANA_OBRIGATORIA`; `S-05`/`EC-04`: Híbrido `NAO_APLICAVEL` com
   Bola de Neve próxima **não** aciona revisão.

10. **Ordem publicada** (`RF-09`). `ORDEM_QUITACAO` = sequência **projetada** do
    cenário recomendado, com `JUSTIFICATIVA_POSICAO` e `valores_de_apoio` por
    posição. `Q-02`: o rótulo "projetada" é do `report/`; a variável interna não
    muda de nome.

11. **Snapshot** (`RF-10`). Carimba `ENGINE_VERSION` e `PARAMETROS_VERSION`
    (`V-03`, `AC-16`), encadeia `snapshot_anterior_id`, grava por `anexar()`.
    *Falha de persistência:* o snapshot já está calculado e é devolvido ao
    chamador; a falha é de I/O e não invalida o cálculo — mas o chamador **não**
    pode declarar o plano publicado.

---

## 6. External Interfaces

O motor **não faz chamada de rede**. As linhas abaixo descrevem os adaptadores
que o cercam.

| Serviço | Endpoint / contrato | Auth | Limites | Falha → |
| --- | --- | --- | --- | --- |
| Supabase Postgres — `parametros` | `SELECT` por `PARAMETROS_VERSION`; colunas `numeric` | `DATABASE_URL` em variável de ambiente; papel somente-leitura para o motor | Free: ~500 MB, 2 projetos, **pausa após ~7 dias sem atividade** | `ErroParametros`; **sem fallback silencioso para valor embutido** (`AC-17`). Operação usa o adaptador de arquivo. |
| Supabase Postgres — `snapshots` | `INSERT` apenas. `REVOKE UPDATE, DELETE` + trigger `impedir_sobrescrita_V01` | idem, papel de escrita restrito | idem | Erro propagado; snapshot é devolvido em memória e pode ser reanexado. Idempotência por `hash_inputs` + `versao`. |
| Adaptador de arquivo — `parameters/*.json` | `json.load(..., parse_float=Decimal)` | sistema de arquivos | — | Arquivo ausente/inválido ⇒ aborta. **Padrão em testes e dev.** |
| Adaptador de arquivo — `snapshots.jsonl` | append-only; uma linha por snapshot; `Decimal` serializado como **string** | sistema de arquivos | — | Erro de escrita propagado. |
| `collection/` e `report/` (slugs futuros) | consumirão `calcular_plano(...)` em processo, ou via FastAPI | a definir no slug | a definir | fora de escopo aqui |

> **Regra de serialização.** `Decimal` **sempre** vira string em JSON/JSONB.
> Número JSON é `double` na maioria dos consumidores e destruiria `RF-12` na
> fronteira. Colunas decisivas (custo, prazo, capacidades) são `numeric`
> tipadas, não só `jsonb`.

---

## 7. State Management

| Estado | Onde vive | Dono | Mutabilidade | Invalidação |
| --- | --- | --- | --- | --- |
| `Parametros` | carregado uma vez por execução | `FonteParametros` | imutável (`frozen`) | nova `PARAMETROS_VERSION` ⇒ nova execução, nunca *hot reload* |
| Contexto decimal | `decimal.localcontext()` na fronteira de `calcular_plano` | `engine/precisao.py` | escopo do bloco | nunca herdado do ambiente (é *thread-local*) — condição do determinismo |
| `EstadoFinanceiro` | argumento de entrada | chamador (`collection/`) | imutável | novo estado ⇒ novo snapshot |
| `EstadoSimulacao` | pilha, dentro de um cenário | `ciclo_mensal` | imutável; cada passo devolve **nova** instância | descartado ao fim do cenário |
| `DIVIDA_ALVO_ATUAL` | dentro de `EstadoSimulacao` e no snapshot | `ciclo_mensal` | só muda por `R-01` | `AC-13`: virada de mês **não** invalida |
| Cache de `simular_trajetoria_isolada` | `functools.lru_cache` por execução | `engine/trajetoria.py` | puro, chaveado por valor | limpo entre execuções; **precisa ser indistinguível de sua ausência** (teste da §9) |
| `SnapshotOrdem` | `RepositorioSnapshots` | persistência | **append-only** (`V-01`) | nunca invalidado; superado por `snapshot_anterior_id` |

**Proibições que sustentam a NFR de determinismo:**
`datetime.now`, `date.today`, `random`, `uuid4`, `os.environ` e iteração sobre
`set`/`dict` não ordenados são banidos dentro de `engine/`. `DATA_REFERENCIA` é
entrada; `SNAPSHOT_ID` é derivado de `hash_inputs` + `versao`; toda ordenação usa
chave total explícita, com `DIVIDA_ID` como desempate final (`O-05`, `H-04`).
Nenhum global mutável além do cache puro.

---

## 8. Error Handling Strategy

O motor não tem UI. A coluna "resposta ao usuário" descreve **o que o motor
devolve para o `report/` renderizar** — a redação é escopo do slug `relatorio`.

| Situação | Detecção | Resposta do motor | Recuperação |
| --- | --- | --- | --- |
| `loading` | — | Não se aplica: `calcular_plano` é síncrona e sem I/O. O indicador é do chamador. | — |
| Parâmetro ausente / versão divergente | `esquema-parametros.json` na carga | `ErroParametros` com o nome do `P_*` faltante | Corrigir a fonte externa. **Nunca** default no código (`AC-17`) |
| Dado material desconhecido em uma dívida | `DinheiroTalvez == DESCONHECIDO` | `DIVIDA_STATUS_ESTRATEGICO = INFORMACAO_PENDENTE`, trajetória `BLOQUEADO`, dívida fora da ordem-base, item em `PRIORIDADE_INFORMACAO` | Obter o dado ⇒ `EVENTO_RECALCULO = INFORMACAO_MATERIAL_CONHECIDA` (`GAB-03`, `AC-10`) |
| `VALOR_RELEVANTE_PARA_QUITACAO` = `DESCONHECIDO` | `valor_quitacao.compor` | Decisão dependente **bloqueada ou provisória conforme a materialidade** | `AC-21`; nunca estimativa |
| Proposta expirada / validade desconhecida | `STATUS_VALIDADE_PROPOSTA` | Usa `SALDO_DEVEDOR_ATUAL`; gera `PRIORIDADE_INFORMACAO` se a diferença puder mudar a decisão | `AC-20`, `EC-14` |
| Benefício marginal insimulável | `origem != SIMULACAO` | Fallback taxa efetiva mensal normalizada → `CET`; `ORDEM_STATUS = PROVISORIA` | `RF-21`, `AC-33` |
| Inventário incompleto | `INVENTARIO_COMPLETO == False` | Totais marcados **parciais**; `ORDEM_STATUS ≠ DEFINITIVA_NA_DATA`; `STATUS_METODO` no máximo `PROVISORIO` | `GAB-02`, `AC-09` |
| Modo estabilização | `RESULTADO_MENSAL_ATUAL < 0` | `CAPACIDADE_ATAQUE_ATUAL = 0`; cenários marcados condicionais; **o observado positivo nunca é rotulado sobra** | `GAB-A`, `GAB-04`, `AC-11` |
| `vazio` — nenhuma dívida elegível | `ParticaoElegibilidade.elegiveis == ()` | Sem `DIVIDA_ALVO_ATUAL`; `ORDEM_ACOES` como saída principal; cronograma condicional | `EC-17` |
| Híbrido sem candidata | `H-08` | `CENARIO_HIBRIDO = NAO_APLICAVEL`. **Não rebaixa** `STATUS_METODO` e **não fabrica** um Híbrido | `EC-03`, `S-02` |
| Resíduo sem destino | fim da cascata | `ATAQUE_NAO_UTILIZADO`, mantido como caixa do usuário | `A-04`, `EC-01` |
| Horizonte estourado | mês > `P_HORIZONTE_MAXIMO_SIMULACAO` | Encerra, `ESTOUROU_HORIZONTE = True`, sinaliza; alerta a partir de `P_HORIZONTE_ALERTA` | `EC-13` |
| Incompatibilidade grave sem alternativa próxima | `S-04` | `STATUS_METODO = PROVISORIO`, `REVISAO_HUMANA_OBRIGATORIA = SIM` | `EC-05` |
| Falha ao anexar snapshot | exceção do adaptador | Propaga. O snapshot calculado é devolvido em memória | Reanexar; idempotente por `hash_inputs` |
| Bug interno (invariante violado) | `assert` de invariante ao fim do mês | `ErroInvariante` com o mês e a conta que não fechou | **Falha ruidosa.** Jamais degradar para resultado aproximado |

> **Princípio.** Nenhuma degradação silenciosa. Toda incerteza vira estado
> nomeado (`INFORMACAO_PENDENTE`, `PROVISORIA`, `NAO_CALCULAVEL`,
> `NAO_APLICAVEL`) e viaja até a saída; nenhuma vira número estimado.

---

## 9. Testing Strategy

- **Suíte obrigatória de homologação** (`pytest -m "gabarito or invariante"`).
  A engine não é aprovada sem ela (§10 da canônica).

  | Teste | Âncora | Verifica |
  | --- | --- | --- |
  | `test_gabarito_a_deficit` | `AC-05` | 8 saídas de `GAB-A`, `MODO_ESTABILIZACAO` |
  | `test_gabarito_b_equilibrio_fragil` | `AC-06`, `AC-07` | 7 saídas de `GAB-B`; cronograma-base usa 200, nunca 600 |
  | `test_gabarito_c_avalanche` | `AC-01` | 6 meses · 23719,46 · 1ª vitória mês 4 · D001→D002→D003 |
  | `test_gabarito_c_bola_de_neve` | `AC-02` | 6 meses · 24463,97 · 1ª vitória mês 1 · D003→D002→D001 |
  | `test_gabarito_c_hibrido` | `AC-03` | 6 meses · 24107,20 · 1ª vitória mês 1 · D003→D001→D002 · `D*`=D003 · 1,635% · atraso 0 |
  | `test_gabarito_c_recomendacao` | `AC-04`, `AC-28` | `HIBRIDO`; Avalanche é o superior; 1,6347% e 3,1388% fora do empate de 1% |
  | `test_invariante_gab01_seguro` | `AC-08` | 1.000 permanece 1.000 |
  | `test_invariante_gab02_inventario` | `AC-09` | totais parciais, status rebaixado |
  | `test_invariante_gab03_rotativo` | `AC-10` | `INFORMACAO_PENDENTE`, `BLOQUEADO`, zero estimativa |
  | `test_invariante_gab04_estabilizacao` | `AC-11` | 200 nunca é "sobra"; fase 2 condicional |
  | `test_invariante_gab05_troca` | `AC-12` | equivalente só sobre 30.000; 10.000 é endividamento |

- **Duas tolerâncias, em dois helpers distintos** (`tests/conftest.py`).
  Separá-los em funções diferentes é o que impede a tolerância errada de vazar:

  ```python
  TOLERANCIA_MONETARIA: Final = Decimal("0.05")   # G-02

  def assertar_monetario(obtido: Dinheiro, esperado: Dinheiro) -> None: ...
      # ±0,05. USO EXCLUSIVO em valor monetário ACUMULADO.

  def assertar_exato(obtido: object, esperado: object) -> None: ...
      # Tolerância ZERO. Obrigatório para: METODO_RECOMENDADO_PIQ, ORDEM_QUITACAO,
      # gates, DIVIDA_STATUS_ESTRATEGICO, STATUS_METODO, ORDEM_STATUS,
      # número de meses, MESES_PRIMEIRA_VITORIA, D*, aplicação de resíduo,
      # gatilho de recálculo, e NAO_APLICAVEL vs PROVISORIO.
  ```

  Um teste de lint (`tests/estatica/test_uso_de_tolerancia.py`) varre a AST de
  `tests/` e falha se `assertar_monetario` for chamado sobre qualquer símbolo da
  lista de tolerância zero. A tolerância errada deixa de ser possível por
  descuido.

- **Unitários por regra** (`tests/regras/`), um arquivo por família, cada teste
  nomeado com o ID: `test_M07_residuo_reranqueia_antes_de_aplicar`,
  `test_R02_virada_de_mes_nao_reranqueia` (`AC-13`),
  `test_A03_delta_do_residuo_nao_usa_capacidade_cheia` (`AC-14`),
  `test_F02_fluxo_liberado_entra_em_m_mais_1` (`AC-15`),
  `test_H04_desempate_lexicografico_seis_niveis`,
  `test_H08_sem_candidata_nao_fabrica_hibrido` (`EC-03`),
  `test_S05_hibrido_nao_aplicavel_nao_aciona_revisao` (`EC-04`),
  `test_O05_cadeia_de_desempate_da_bola_de_neve`,
  `test_D4_desconhecido_nao_conta_como_risco` (`AC-25`),
  `test_D4_reducoes_separadas` (`AC-26`),
  `test_gate2_risco_alto_nao_e_primeira_divida` (`AC-23`),
  `test_RF22_nova_divida_prevista_fora_da_projecao` (`AC-30`).
  Testam **saída observável do motor**, nunca função interna (§5 do config).

- **Testes estáticos** (`tests/estatica/`) — o que revisão humana esquece:
  - `test_nenhum_parametro_no_codigo`: varre a AST de `engine/`; falha se
    qualquer nome `P_*` receber literal, ou se um número da tabela da §8
    aparecer como literal. `AC-17`, lado A.
  - `test_parametro_externo_muda_resultado`: roda `GAB-C` com
    `P_MESES_VITORIA_RAPIDA = 0` e exige `CENARIO_HIBRIDO = NAO_APLICAVEL`.
    `AC-17`, lado B — prova que a fonte externa é de fato lida.
  - `test_sem_float_no_motor`: falha se `float`, literal de ponto flutuante ou
    `math.*` aparecer em `engine/`. `RF-12`.
  - `test_motor_e_deterministico`: falha se `datetime.now`, `date.today`,
    `random` ou `uuid4` for importado em `engine/`. NFR de determinismo.
  - `test_toda_regra_citada`: cada módulo de `engine/` declara
    `REGRAS: Final[tuple[str, ...]]`; falha se alguma das regras `M-01..G-02`
    não for citada por nenhum módulo. §4 do config.

- **Integração** — as costuras reais deste slug:
  - `FonteParametros`: arquivo e Postgres carregam `Parametros` idênticos, campo
    a campo, com `Decimal` exato. `RF-13`.
  - `RepositorioSnapshots`: `anexar` duas vezes preserva as duas versões;
    `UPDATE`/`DELETE` direto no Postgres é **recusado pelo banco**. `RF-10`,
    `V-01`.
  - Round-trip `SnapshotOrdem` → JSON/`numeric` → `SnapshotOrdem` com igualdade
    exata de todo `Decimal`. `RF-12`.
  - Equivalência cache: `GAB-C` com e sem `lru_cache` produz snapshots idênticos.
    Guarda o determinismo contra a otimização da §10.

- **Propriedade** (Hypothesis, `derandomize=True`), duas propriedades apenas:
  - `A-04`: para qualquer carteira gerada, `ataque aplicado + ATAQUE_NAO_UTILIZADO
    == ataque disponível` em todo mês. Nenhum valor desaparece.
  - `F-03`: nenhum valor aparece simultaneamente como pagamento normal de *m* e
    como capacidade adicional de *m*. Sem dupla contagem.

- **Desempenho** (`pytest -m desempenho`, fora da suíte padrão): carteira de 30
  dívidas, horizonte 120 meses, três métodos + recomendação, com orçamento
  declarado na §10. Medido, não presumido — a §8 da spec manda medir antes de
  otimizar.

- **E2E:** não se aplica neste slug. Não há interface. O equivalente ponta a
  ponta é `EstadoFinanceiro` → `SnapshotOrdem`, coberto pelos gabaritos.

- **Fora de teste automatizado:** redação dos textos ao usuário (`Q-03`, escopo
  de `relatorio`); conformidade jurídica/LGPD (`PEND-01`); e a **correção
  metodológica das próprias regras** — a suíte prova que o código faz o que a
  spec diz, não que a spec está certa. Isso é revisão do especialista.

---

## 10. Risks & Trade-offs

| Decisão | Alternativa descartada | Por quê | Risco assumido |
| --- | --- | --- | --- |
| **`RISCO-15.2`** — Python + Postgres em vez de Apps Script + Google Sheets | Desenho recomendado na §15.2 da canônica | Sheets guarda tudo como `double` binário e Apps Script não tem decimal nativo: reprovados no critério eliminatório de `RF-12`. Somam-se o teto de ~6 min por execução, que colide com o custo do Híbrido (`RF-07`), e a ausência de testes automatizados, sem os quais os gabaritos não são suíte. A §15 é explicitamente "recomendada", e a §9 da spec do slug põe infraestrutura na mão do plano | Divergir de uma recomendação da canônica. **Exige confirmação humana e, se aceita, errata registrando que a §15.2 é indicativa, não normativa** |
| Supabase para `parametros` e `snapshots`, **fora** do `engine/` | Supabase como plataforma completa, com regra em `plpgsql`; ou só arquivos | `numeric` exato (`RF-12`), imutabilidade por privilégio (`RF-10`/`V-01`) e edição de parâmetro sem código (`RF-13`/`US-06`). Regra em SQL criaria segunda fonte da verdade e sairia do alcance dos gabaritos | Plano Free **pausa após ~7 dias sem atividade** e não tem backup automático. Mitigação: adaptador de arquivo sempre funcional, exportação periódica, e saída para self-host (Apache-2.0) ou Pro ~US$ 25/mês sem tocar no motor |
| `Decimal` com `prec=34` e arredondamento **só** na exibição | Inteiros de centavos | Taxas compostas (4% a.m.) geram dízimas; inteiro de centavo truncaria a cada mês e os gabaritos não fechariam. `G-01` pede precisão integral | `prec=34` ainda é finita. Mitigado pelos gabaritos e pela tolerância de `G-02`. `ROUND_HALF_UP` **deixou de ser escolha do plano** — é norma desde as Definições §9 (`AC-40`) |
| Um único `ciclo_mensal` com `SelecionarAlvo` injetada | Um ciclo por método | `M-01..M-12` é idêntico nos três (§5 da canônica). Duplicar faria `AC-13`/`AC-14`/`AC-15` divergirem entre métodos — exatamente a divergência que a errata `E-06` registra em 8,5% de 400 carteiras | Indireção a mais para ler. Compensa: uma correção de ciclo corrige os três |
| Memoização de `simular_trajetoria_isolada` | Simulação ingênua | Custo do Híbrido: para N=30 e H=120, ~29 cenários completos × ~60 reranqueamentos × 30 dívidas × 2 trajetórias ≈ **1,2 × 10⁷ passos-mês** — inaceitável em CPython. A trajetória isolada é função pura de (saldo, taxa, pagamento, delta, horizonte) e repete muito entre cenários, derrubando isso a ~10⁵ | Chave de cache errada quebra o determinismo silenciosamente. Mitigação: `frozen` + `Decimal` (hash por valor) e **teste obrigatório de equivalência cache-on/cache-off**. Orçamento declarado: **3 métodos + recomendação para N=30, H=120 em ≤ 10 s**; medir antes de otimizar mais |
| `DESCONHECIDO` como tipo-soma, `None` proibido para dado de negócio | `Optional[Decimal]` | `None` significa "não perguntado"; `DESCONHECIDO` significa "perguntado e não sabido". `AC-25` depende da diferença. Com mypy strict, ignorar `DESCONHECIDO` não compila | Verbosidade em todo consumidor. É o preço de `RF-16` ser garantido pelo compilador |
| `persistencia/` como nova pasta de topo | Adaptadores dentro de `engine/` | Supabase dentro de `engine/` quebraria a pureza da qual dependem `RF-12` e a NFR de determinismo | Diverge da §3 do config. **Exige `/sdd:config` antes da implementação** |
| Hypothesis como única dependência de teste externa | Só testes por exemplo | `A-04` e `F-03` são universais ("nenhum valor desaparece", "nada é contado duas vezes"); exemplo deixa buraco justamente onde a §8 da spec aponta risco alto | Aleatoriedade em CI. Mitigado com `derandomize=True` |
| Python, com `collection/` possivelmente em TypeScript | Monolinguagem TS | `RF-12` é eliminatório e decidiu sozinho | Duas linguagens no repositório. Mitigação: motor atrás de uma fronteira HTTP/JSON com `Decimal` serializado como string. **Confirmar com o usuário** |
| **`RISCO-CANONICA`** (herdado da §8 da spec) | — | Parte das definições ainda vive na §11 da spec do slug | **Reduzido a médio em 2026-09-02:** o *Fechamento das Definições Remanescentes da Engine* absorveu oito temas com regra de precedência própria. Resta consolidar gates, D.4 e a separação empate material × proximidade econômica |
| **Ordem de derivação imposta por assinatura**, não por convenção | Funções independentes lendo um contexto compartilhado | O grafo `NIVEL_CONTROLE → CONFIABILIDADE_DADOS → D.4 → INCOMPATIBILIDADE → FATOR_SEGURANCA` produz resultado errado **sem erro visível** se executado fora de ordem (`RF-27`). Passar o resultado anterior como parâmetro obrigatório faz o mypy recusar a ordem errada | Encadeamento explícito é mais verboso que um objeto de contexto. É o preço de a ordem ser verificável em vez de documentada |

### 10.1. Buracos da spec — todos fechados em 2026-09-02

Os oito buracos sinalizados na análise inicial foram respondidos pelo documento
*Fechamento das Definições Remanescentes da Engine*
([`specs/piq-definicoes-engine.md`](../specs/piq-definicoes-engine.md)).
Nenhum foi resolvido por decisão de implementação.

| ID | Buraco | Decisão normativa | Onde |
| --- | --- | --- | --- |
| `BURACO-01` | Estado da dívida desviada pelo Gate 2 | `INTERVENCAO_PENDENTE` + `GATE_PENDENTE = CONTENCAO_RISCO`. **Não** se cria estado por gate: o estado diz o que a dívida é, o novo atributo diz o que a trava | Definições §7 · `AC-43` |
| `BURACO-02` | `SUBSTITUIDA`/`SUSPENSA` fora do domínio de `STATUS_DIVIDA` | `STATUS_DIVIDA` **não decide** elegibilidade — os gates decidem. Os cinco status reais ganharam tratamento explícito | Definições §6 · `AC-41`, `AC-42`, `AC-44`, `AC-45` |
| `BURACO-03` | `NIVEL_CONTROLE` e `CONFIABILIDADE_DADOS` sem fórmula | Regras determinísticas sobre 8 variáveis do Bloco 2, com ordem de avaliação obrigatória. Deixam de ser entrada e passam a ser derivadas | Definições §4, §5 · `RF-23`, `AC-46` |
| `BURACO-04` | Domínio de `STATUS_FINANCEIRO` e função do piso | `DEFICIT` · `EQUILIBRIO_FRAGIL` · `CAPACIDADE_POSITIVA`. O piso **classifica** e nunca altera a capacidade | Definições §8 · `RF-26`, `AC-37`–`AC-39` |
| `BURACO-05` | `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` sem regra | `NECESSIDADE_VITORIA ≥ P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA` **E** (abandono **OU** recaída alta **OU** controle frágil). Nenhum grupo basta sozinho | Definições §1 · `RF-24`, `AC-34`, `AC-35` |
| `BURACO-06` | `FATOR_SEGURANCA` subtrativo ou multiplicativo | **Subtrativo.** Somar as quatro reduções, subtrair de 1, aplicar o piso por último. Multiplicativa proibida | Definições §3 · `RF-25`, `AC-36` |
| `BURACO-07` | Horizonte de `DESEMBOLSO_FUTURO` | Cada trajetória até seu próprio `SALDO = 0`. Proibido truncar no menor prazo ou usar horizonte fixo. Permitido horizonte comum com desembolso 0 após a quitação, se equivalente | Definições §2 · `AC-47` |
| `BURACO-08` | Modo de arredondamento | `ROUND_HALF_UP`, oficial e não mais provisório | Definições §9 · `AC-40` |

**Efeito colateral favorável do `BURACO-07`:** a autorização de usar horizonte
comum com `DESEMBOLSO_MENSAL = 0` após cada quitação permite calcular as duas
trajetórias no mesmo laço, o que ajuda diretamente o orçamento de desempenho da
memoização.

**Efeito colateral adverso do `BURACO-03`:** `NIVEL_CONTROLE` e
`CONFIABILIDADE_DADOS` deixaram de ser entrada e viraram derivação — o que criou
o grafo de dependência da §5 passo 3 e o requisito `RF-27`.

### 10.2. Pontas soltas remanescentes

Registradas na spec como `OQ-17` a `OQ-19`. **Nenhuma bloqueia a implementação.**
Os termos órfãos `SUBSTITUIDA`/`SUSPENSA` ficaram sem referente, o valor
pós-confirmação de `QUITADA_A_CONFIRMAR` não está no domínio publicado, e a
dívida que amortiza deterministicamente além de `P_HORIZONTE_MAXIMO_SIMULACAO`
fica entre a regra da §2 e a exceção da §2.1.

## 11. Traceability

| Requisito | Coberto por (seção do plano) |
| --- | --- |
| `RF-01` — ciclo mensal `M-01..M-12` | §1 (lei nº 2) · §3 `engine/ciclo_mensal.py` · §4 `executar_mes`, `simular_cenario` · §5 passo 7 · §9 `tests/regras/M` |
| `RF-02` — recálculo só por quitação ou evento material | §3 `engine/eventos.py` · §4 `EVENTO_RECALCULO` (sem membro cadastral, `R-04`) · §5 passo 7 · §7 (`DIVIDA_ALVO_ATUAL`) · §9 `test_R02_...` (`AC-13`) |
| `RF-03` — cascata do resíduo e `ATAQUE_NAO_UTILIZADO` | §4 `ResultadoMes.aplicacoes_residuo`, `ATAQUE_NAO_UTILIZADO` · §5 passo 7 · §8 (resíduo sem destino) · §9 propriedade `A-04` |
| `RF-04` — fluxo liberado só em *m+1*, sem dupla contagem | §4 `VALOR_FLUXO_LIBERADO` devolvido e não somado no mês · §5 passo 7 · §9 `test_F02_...` (`AC-15`) e propriedade `F-03` |
| `RF-05` — Avalanche por benefício marginal | §3 `engine/beneficio_marginal.py`, `engine/metodos/avalanche.py` · §4 `BeneficioMarginal`, `Trajetoria` · §5 passo 7 · §10 (memoização) · §9 `AC-01`, `AC-19` |
| `RF-06` — Bola de Neve por `VALOR_RELEVANTE_PARA_QUITACAO` | §3 `engine/valor_quitacao.py`, `engine/metodos/bola_de_neve.py` · §4 `STATUS_VALIDADE_PROPOSTA` · §8 (`AC-20`, `AC-21`) · §9 `AC-02`, `test_O05_...` |
| `RF-07` — Híbrido em seis etapas | §3 `engine/metodos/hibrido.py` · §4 `Cenario`, `CLASSIFICACAO_CENARIO` · §5 passo 7 · §9 `AC-03`, `test_H04_...`, `test_H08_...` · §10 (custo) |
| `RF-08` — `NAO_CALCULAVEL` vs `NAO_APLICAVEL` e `STATUS_METODO` | §3 `engine/status_metodo.py` · §4 `CLASSIFICACAO_CENARIO`, `STATUS_METODO`, `REVISAO_HUMANA_OBRIGATORIA` · §5 passo 9 · §8 (`EC-04`, `EC-05`) · §10.1 `BURACO-05` |
| `RF-09` — `ORDEM_QUITACAO` com `JUSTIFICATIVA_POSICAO` | §3 `engine/ordem.py` · §4 `PosicaoOrdem` · §5 passo 10 |
| `RF-10` — snapshot por quitação ou evento, sem sobrescrita | §3 `engine/snapshot.py`, `persistencia/` · §4 `SnapshotOrdem`, `RepositorioSnapshots` (sem `atualizar`) · §6 (`REVOKE`+trigger) · §7 (append-only) · §9 integração `V-01` |
| `RF-11` — troca com `DINHEIRO_NOVO > 0` | §3 `engine/troca.py` · §4 (`T-01`, `T-02`) · §9 `test_invariante_gab05_troca` (`AC-12`) |
| `RF-12` — precisão decimal integral | §2 (Python, `decimal`, `parse_float=Decimal`, psycopg `numeric`) · §3 `engine/precisao.py` · §4 `Dinheiro`, `dinheiro()`, `quantizar_exibicao` · §6 (regra de serialização) · §9 `test_sem_float_no_motor` |
| `RF-13` — parâmetros de fonte externa, zero no código | §2 (`json`+Supabase) · §3 `parameters/`, `engine/parametros.py` · §4 `Parametros`, `FonteParametros` · §5 passo 1 · §6 · §9 `test_nenhum_parametro_no_codigo` + `test_parametro_externo_muda_resultado` (`AC-17`) |
| `RF-14` — diagnóstico e as três capacidades | §3 `engine/diagnostico.py` · §4 `Diagnostico` · §5 passos 3–4 · §9 `AC-05`, `AC-06`, `AC-07` · §10.1 `BURACO-03`, `BURACO-04`, `BURACO-06` |
| `RF-15` — `MODO_ESTABILIZACAO` | §4 `Diagnostico.MODO_ESTABILIZACAO`, `CAPACIDADE_ATAQUE_ATUAL` · §5 passo 5 · §8 (linha modo estabilização) · §9 `AC-11` |
| `RF-16` — bloquear o que depende de dado ausente | §2 (mypy strict) · §4 `DESCONHECIDO`, `DinheiroTalvez` · §5 passo 3 · §8 (3 linhas de dado desconhecido) · §9 `AC-10`, `AC-21` |
| `RF-17` — quatro gates, `DIVIDA_STATUS_ESTRATEGICO`, `ORDEM_ACOES` | §3 `engine/gates.py` · §4 `ResultadoGates`, `ParticaoElegibilidade` e §4.1 (máquina de estados) · §5 passo 6 · §7 (transição só por `R-01`) · §9 `AC-22`, `AC-23` · §10.1 `BURACO-01`, `BURACO-02` |
| `RF-18` — regra D.4 | §3 `engine/risco.py` · §4 `SinalD4`, `ClassificacaoRisco`, `NIVEL_RISCO` · §5 passo 4 · §9 `AC-24`, `AC-25`, `AC-26` |
| `RF-19` — `CENARIO_ECONOMICAMENTE_SUPERIOR` (1%) | §3 `engine/comparacao.py` · §4 `ComparacaoCenarios.empatados_materialmente` · §5 passo 9 · §9 `AC-27`, `AC-28`, `EC-19` |
| `RF-20` — `ECONOMICAMENTE_PROXIMO` (5% **e** 2 meses) | §3 `engine/comparacao.py` · §4 `PENALIDADE_CUSTO`, `ATRASO_PRAZO`, `ECONOMICAMENTE_PROXIMO` · §5 passo 9 · §9 `AC-29` |
| `RF-21` — fallback por taxa e `ORDEM_STATUS = PROVISORIA` | §4 `BeneficioMarginal.origem`, `ORDEM_STATUS` · §5 passo 7 · §8 (benefício insimulável) · §9 `AC-33` |
| `RF-22` — evento futuro provável fora da projeção-base | §3 `engine/eventos.py` · §4 `EVENTO_RECALCULO.NOVA_DIVIDA` · §5 passo 8 (filtro antes da simulação) · §9 `AC-30`, `AC-31` |

| `RF-23` — `NIVEL_CONTROLE` e `CONFIABILIDADE_DADOS` derivados do Bloco 2 | §3 `engine/comportamento.py` · §4 `PerfilComportamental`, `NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS` · §5 passos 3a–3b · §9 `AC-46` · §10.1 `BURACO-03` |
| `RF-24` — `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` | §3 `engine/comportamento.py` · §5 passo 3d · §9 `AC-34`, `AC-35`, `AC-04` · §10.1 `BURACO-05` |
| `RF-25` — `FATOR_SEGURANCA` subtrativo com piso ao final | §3 `engine/diagnostico.py` · §5 passo 4 · §9 `AC-36`, `AC-26` · §10.1 `BURACO-06` |
| `RF-26` — `STATUS_FINANCEIRO` e piso classificatório | §3 `engine/diagnostico.py` · §4 `STATUS_FINANCEIRO` · §5 passo 4 · §9 `AC-37`, `AC-38`, `AC-39` · §10.1 `BURACO-04` |
| `RF-27` — ordem de derivação obrigatória | §5 passo 3 (encadeamento por assinatura) · §10 (decisão de impor por tipo, não por convenção) · §9 teste de ordem |

**Cobertura:** 27 de 27 requisitos. Nenhuma seção deste plano existe sem
requisito atrás — as escolhas de §2 e §9 rastreiam para `RF-12`, `RF-13` e `RF-16`
ou para NFRs explícitas da §5 da spec.

> Requisito sem cobertura é buraco no plano. Item de plano sem requisito é
> over-engineering.

---
---

# Rodada 2 — Extensão de `AcaoRequerida`/`Diagnostico` (2026-09-04)

| Campo  | Valor                                            |
| ------ | ------------------------------------------------ |
| Slug   | `motor-calculo`                                  |
| Spec   | [`specs/motor-calculo.spec.md`](../specs/motor-calculo.spec.md) §2 (`RF-28`–`RF-35`), §12 |
| Pedido por | slug `app-aluno` (`T-77`/`T-78`/`T-79` bloqueadas) |
| Status | `rascunho`                                       |
| Autor  | virtushold@gmail.com                             |
| Data   | 2026-09-04                                       |

> **Escopo desta seção.** Cobre exclusivamente `RF-28` a `RF-35`. As seções 1
> a 11 acima (Rodada 1, 78/78 concluída) **não são alteradas** por esta
> rodada — permanecem a fonte de verdade para tudo que já existia antes de
> 2026-09-04. Onde esta rodada estende uma decisão da Rodada 1 (ex.: `engine/
> gates.py::AcaoRequerida`), o texto abaixo aponta explicitamente a seção
> original em vez de duplicá-la.
>
> **Precedência inalterada.** Onde este plano e a spec divergirem, prevalece
> a spec (`specs/motor-calculo.spec.md`); a decisão de *o quê* mudar em
> `AcaoRequerida`/`Diagnostico` já foi tomada pelo especialista e está fechada
> em `specs/app-aluno.spec.md` §10 (`OQ-10`, `OQ-13`, `OQ-14`, `OQ-15`,
> `OQ-17`, `OQ-18`) — este plano decide só **como** transcrever isso para
> código, nunca reabre o *o quê*.

## R2.1. Architecture Overview

Nenhum componente novo. A extensão entra em **três pontos** do fluxo já
descrito no diagrama da §1 (Rodada 1), sem alterar a ordem dos 11 passos nem
introduzir um estágio novo:

```text
                            [4] GATES 1..4  (engine/gates.py)
                                RF-17 (R1) · RF-28..RF-32, RF-34 (R2)
                     ┌─────────────────────┴──────────────────────┐
                     ▼                                             ▼
              DIVIDAS_ELEGIVEIS                              ORDEM_ACOES
           (Rodada 1, inalterado)              ┌── Gate 1 (R2: RF-32) → AcaoRequerida
                                                │      TIPO_ACAO="INFORMACAO"
                                                ├── Gate 3 (R1, campo novo R2: RF-30)
                                                │      TIPO_ACAO="RENEGOCIACAO"|"TROCA"
                                                └── fora dos gates (R2: RF-33)
                                                       TIPO_ACAO="ECONOMIA", DIVIDA_ID=None
                                                       ← ECONOMIA_POTENCIAL_IMEDIATA (estado)
                     │
                     ▼
              [1] DIAGNOSTICO  (engine/diagnostico.py)
                  RF-14 (R1) · RF-35 (R2: + RESERVA_MOBILIZAVEL,
                                        ATAQUE_IMEDIATO_RECOMENDADO)
```

Três pontos de mudança, exatamente como o pedido do `app-aluno` delimita
(§12 da spec):

1. **`engine/gates.py::AcaoRequerida`** — dataclass ganha `ACAO_ID`,
   `TIPO_ACAO`, `CAMPO_PENDENTE`; `DIVIDA_ID` relaxa para `str | None`
   (`RF-28`, `RF-29`, `RF-31`, `RF-34`).
2. **`engine/gates.py::aplicar_gate_1_informacao`** — os dois ramos de
   bloqueio passam a construir `AcaoRequerida` em vez de `acao=None`
   (`RF-32`); **`engine/gates.py::aplicar_gate_3_transformacao`** passa a
   preencher `TIPO_ACAO` (`RF-30`).
3. **Emissão da ação de economia** — novo ponto de emissão fora do fluxo de
   gates, condicionado a `ECONOMIA_POTENCIAL_IMEDIATA > 0` (`RF-33`).
4. **`engine/diagnostico.py::Diagnostico`** — dois campos novos no bloco de
   "campos comportamentais adicionais" já existente (`RF-35`).

Nenhuma lei de arquitetura da §1 (Rodada 1) é violada: `engine/` continua sem
importar `persistencia/`, sem I/O, sem relógio. A extensão é aditiva em três
dos quatro pontos (`RF-28`, `RF-29`, `RF-30`, `RF-33`, `RF-34`, `RF-35`); o
quarto (`RF-31`, relaxamento de `DIVIDA_ID`) é mudança de invariante e é
tratado com o mesmo rigor de uma quebra de contrato (ver R2.10).

## R2.2. Tech Stack

**Nenhuma dependência nova.** A stack é a mesma da Rodada 1 (§2 acima):
Python 3.12+, `decimal` da stdlib, `dataclasses(frozen=True, slots=True)` +
`enum`, `mypy --strict`, `ruff`, `pytest`. Confirmado por leitura direta do
código atual (`engine/gates.py`, `engine/diagnostico.py`, `engine/tipos.py`,
`engine/valor_quitacao.py`): todos usam `from __future__ import annotations`,
`@dataclass(frozen=True, slots=True)`, `Final`, `Literal`, e nenhum símbolo
de biblioteca externa além da stdlib. A extensão desta rodada é puramente
estrutural (campos de dataclass + `Literal`/`Enum` + lógica de composição de
string) — nada aqui exige ferramenta que a Rodada 1 já não tenha justificado.

| Escolha | Uso | Justificativa (ancorada em `RF-NN`) |
| --- | --- | --- |
| `Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"]` (typing, stdlib) | tipo de `AcaoRequerida.CAMPO_PENDENTE` | `RF-34`. Domínio fechado de exatamente dois valores — `Literal` faz o `mypy --strict` recusar um terceiro valor em tempo de checagem, mesma técnica já usada em `AcaoRequerida.gate_origem: Literal[2, 3]` (Rodada 1, `engine/gates.py:141`). Descartado `Enum`: os dois valores nomeiam campos de `Divida` (não um conceito de domínio próprio como `GATE_PENDENTE`), e `Literal[str, str]` já é o padrão do próprio arquivo para esse caso |
| `str` (não `Enum`) para `TIPO_ACAO` | tipo de `AcaoRequerida.TIPO_ACAO` | `RF-29` fixa `str` explicitamente (não `Enum`) — decisão já tomada em `app-aluno.spec.md` §10 `OQ-13`, transcrita literalmente aqui. Não introduzir um `Enum` por preferência de estilo seria reabrir o *o quê*, que este slug não faz (§9 Out of Scope da spec) |
| `str \| None` (stdlib) | tipo de `AcaoRequerida.DIVIDA_ID` | `RF-31`. `None` aqui é correto e não contradiz a convenção de `DESCONHECIDO` (`engine/tipos.py`, Rodada 1): `DESCONHECIDO` modela "dado de negócio perguntado e não sabido" (`DinheiroTalvez`/`TaxaTalvez`); `DIVIDA_ID: str \| None` modela "este campo estruturalmente não se aplica" (a ação de economia não é sobre nenhuma dívida) — mesma distinção que `EstadoFinanceiro`/`Divida` já fazem ao usar `None` só onde a ausência é estrutural (`Divida.OPORTUNIDADE_VIGENTE: Oportunidade \| None`, Rodada 1) |
| `mypy --strict` (já em uso, Rodada 1) | verificação estática do relaxamento de `DIVIDA_ID` | `RF-31`, `AC-55`, `EC-21`. É o mecanismo que torna a varredura de consumidores (R2.10) verificável por máquina em vez de por revisão manual: todo `acao.DIVIDA_ID` usado como `str` sem checar `None` primeiro passa a ser erro de tipo no comando `build` já definido em `sdd.config.md` §2 |

## R2.3. Project Structure

Nenhum arquivo novo. Todos os quatro pontos de mudança são edições em
arquivos que já existem — a extensão é aditiva de campo/função dentro de
módulos da Rodada 1, exatamente como o docstring de `AcaoRequerida` já
antecipava (spec §7, Assumptions).

| Caminho | Mudança | Novo? |
| --- | --- | --- |
| `engine/gates.py` | `AcaoRequerida`: +`ACAO_ID`, +`TIPO_ACAO`, +`CAMPO_PENDENTE`, `DIVIDA_ID` relaxado para `str \| None` (`RF-28`, `RF-29`, `RF-31`, `RF-34`). `aplicar_gate_1_informacao`: dois ramos passam a construir `AcaoRequerida` (`RF-32`). `aplicar_gate_3_transformacao`: preenche `TIPO_ACAO` (`RF-30`). Nova função privada de composição de `ACAO_ID` (R2.4) | não |
| `engine/diagnostico.py` | `Diagnostico`: +`RESERVA_MOBILIZAVEL`, +`ATAQUE_IMEDIATO_RECOMENDADO` no bloco de campos comportamentais extras (`RF-35`) | não |
| `engine/motor.py` ou `engine/gates.py` (ver R2.5 para a decisão) | ponto de emissão da `AcaoRequerida` de economia, fora do fluxo de gates (`RF-33`) | não |
| `engine/ordem.py` | consumidor de `resultado.DIVIDA_ID`/`particao.bloqueadas` (linha 269, `{resultado.DIVIDA_ID for resultado in particao.bloqueadas}`) — **não** lê `AcaoRequerida.DIVIDA_ID` (lê `ResultadoGates.DIVIDA_ID`, campo diferente, sempre `str`, não tocado por `RF-31`). Auditado e confirmado fora do escopo da varredura de `RF-31` (ver R2.10) | não |
| `tests/regras/test_gates.py` | novos casos para `RF-28`–`RF-34`; ajuste dos `assert resultado.acao is not None` existentes que hoje presumem `gate_origem`/ausência de `TIPO_ACAO` | não |
| `tests/regras/test_diagnostico.py` | novos casos para `RF-35` | não |
| `tests/gabaritos/`, `tests/invariantes/` | reexecução obrigatória (`AC-58`–`AC-60`) — arquivos existentes, expectativas de `ORDEM_ACOES` atualizadas onde `RF-32` mudar a saída | não |
| `tests/estatica/` | novo teste de composição determinística de `ACAO_ID` (R2.4); nenhum teste estático da Rodada 1 muda de comportamento | possivelmente 1 novo arquivo |

**Nota de escopo explícita (Out of Scope, spec §9).** `app/motor/acoes.py`,
`app/casos/*.py` e `tests/app_aluno/estatica/hashes_congelados.json`
aparecem no grep de consumidores de `AcaoRequerida`/`ORDEM_ACOES`/
`ECONOMIA_POTENCIAL_IMEDIATA`, mas pertencem ao slug `app-aluno` — fora do
plano deste slug. A atualização do hash congelado é procedimento do
`app-aluno` (`AC-44` daquela spec), disparado **depois** que esta mudança for
mesclada.

## R2.4. Data Model

Contratos e assinaturas — nomes idênticos à spec, caractere por caractere
(§7 do `sdd.config.md`). Corpo de função é escopo de `/sdd:implement`.

```python
# engine/gates.py — estado ATUAL (Rodada 1, linhas 125–142, citado aqui só
# como referência do que muda; NÃO reescrever o docstring de contexto
# histórico da Rodada 1, só estender a dataclass)
@dataclass(frozen=True, slots=True)
class AcaoRequerida:
    DIVIDA_ID: str
    descricao: str
    gate_origem: Literal[2, 3]
    prioridade_excepcional: bool = False
```

```python
# engine/gates.py — CONTRATO NOVO da Rodada 2 (RF-28, RF-29, RF-31, RF-34)
@dataclass(frozen=True, slots=True)
class AcaoRequerida:
    ACAO_ID: str
    DIVIDA_ID: str | None            # RF-31: None só para TIPO_ACAO="ECONOMIA"
    TIPO_ACAO: str                   # RF-29: domínio fechado, ver TIPO_ACAO_VALORES
    descricao: str
    gate_origem: Literal[1, 2, 3] | None
    # ↑ RF-32 amplia o domínio de gate_origem para incluir 1 (Gate 1 passa a
    # emitir AcaoRequerida) e None (ação de economia, RF-33, não vem de
    # gate algum). Campo já existente na Rodada 1 (Literal[2, 3]); a
    # ampliação de domínio é consequência direta de RF-32/RF-33, não uma
    # decisão nova deste plano.
    prioridade_excepcional: bool = False
    CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"] | None = None
    # RF-34: só preenchido quando TIPO_ACAO="INFORMACAO" (Gate 1). None nos
    # demais TIPO_ACAO — RF-34 não define um terceiro valor de domínio para
    # "não se aplica", e forçar CAMPO_PENDENTE não-opcional obrigaria todo
    # AcaoRequerida de RENEGOCIACAO/TROCA/ECONOMIA a inventar um valor sem
    # sentido normativo, o que a §6 do sdd.config.md proíbe.

TIPO_ACAO_VALORES: Final[frozenset[str]] = frozenset(
    {"INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"}
)
# RF-29 · AC-49: domínio fechado, ASCII, sem parênteses, exatamente estes
# quatro literais. Usado por teste estático (R2.9) para recusar um quinto
# valor introduzido por engano em runtime.
```

**Composição determinística de `ACAO_ID` — resolve `OQ-21`/`OQ-22` (já
`respondida`; formato de serialização é decisão deste plano, propriedade de
determinismo não é reaberta).**

```python
# engine/gates.py — nova função privada, chamada pelos três pontos de
# emissão (Gate 1, Gate 3, ação de economia)
def _compor_ACAO_ID(*, divida_id: str | None, tipo_acao: str) -> str:
    """RF-28 · OQ-21/OQ-22 (respondida) — ACAO_ID determinístico por
    composição, sem contador, sem UUID, sem estado externo.

    Ações ligadas a gate (INFORMACAO, RENEGOCIACAO, TROCA):
        ACAO_ID = f"{divida_id}:{tipo_acao}"
    Ação de economia (ECONOMIA, sem DIVIDA_ID):
        ACAO_ID = f"ACAO:{tipo_acao}"     # ex.: "ACAO:ECONOMIA"

    Formato de serialização (decisão deste plano, spec deixou em aberto):
      - separador ':' — já usado em identificadores compostos do domínio
        (nenhum DIVIDA_ID observado em fixtures/gabaritos contém ':', então
        não há colisão entre "D001:INFORMACAO" e um DIVIDA_ID literal
        "D001:INFORMACAO" hipotético que reaproveitasse o separador)
      - caixa alta preservada — TIPO_ACAO já é ASCII maiúsculo (RF-29);
        DIVIDA_ID preserva a caixa do domínio (ex. "D001", Rodada 1)
      - prefixo "ACAO:" só no caso sem DIVIDA_ID, para diferenciar
        estruturalmente do padrão "<DIVIDA_ID>:<TIPO_ACAO>" — sem prefixo
        aqui, "ECONOMIA" sozinho poderia colidir textualmente com um
        DIVIDA_ID futuro chamado literalmente "ECONOMIA"
    """
```

**Ponto de decisão explícito (não ambíguo, mas registrado por
auditabilidade).** A spec (§10, `OQ-21`) deixa o formato de serialização a
critério do plano, com uma única restrição: preservar o determinismo puro
por composição. O formato acima (`"{DIVIDA_ID}:{TIPO_ACAO}"` /
`"ACAO:{TIPO_ACAO}"`) é a escolha deste plano — **qualquer separador,
caixa ou prefixo alternativo que preserve unicidade e determinismo seria
igualmente válido perante a spec**; esta não é uma ambiguidade não resolvida
(não vai para Open Questions), é uma decisão de plano dentro do espaço que a
spec delegou explicitamente.

```python
# engine/diagnostico.py — Diagnostico, RF-35 · §12.6
# Adição ao bloco "campos comportamentais adicionais" já existente
# (engine/diagnostico.py:623–630, Rodada 1) — mesmo bloco, não um novo:
@dataclass(frozen=True, slots=True)
class Diagnostico:
    # ... catorze campos literais do plano (Rodada 1, inalterados) ...
    # --- campos comportamentais adicionais (Rodada 1) ---
    NIVEL_CONTROLE: NIVEL_CONTROLE
    CONFIABILIDADE_DADOS: CONFIABILIDADE_DADOS
    RISCO_RECAIDA: NIVEL_RISCO
    RISCO_COMPORTAMENTAL_GERAL: NIVEL_RISCO
    INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE: bool
    classificacao_risco_recaida: ClassificacaoRisco
    classificacao_risco_comportamental_geral: ClassificacaoRisco
    # --- Rodada 2 (RF-35, mesmo bloco) ---
    RESERVA_MOBILIZAVEL: Dinheiro
    ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro
```

**Nota de ambiguidade explícita — fórmula de `RESERVA_MOBILIZAVEL` e de
`ATAQUE_IMEDIATO_RECOMENDADO` (regra `sdd.config.md` §3, ambiguidade não se
adivinha).** Nem a spec deste slug (§12.6), nem `app-aluno.spec.md` §10
`OQ-17`, nem a canônica publicam a fórmula de derivação destes dois campos —
apenas o nome, o tipo (`Dinheiro`) e a posição (mesmo bloco dos demais
campos comportamentais extras). A Assumption da spec (§7) confirma:
*"`RESERVA_MOBILIZAVEL`/`ATAQUE_IMEDIATO_RECOMENDADO` não existem hoje em
nenhum lugar de `engine/*.py` — só aparecem em condição de exibição e em
prosa de 'uso pelo motor' na canônica, nunca implementados como campo real
antes desta rodada."` Este plano **não inventa** a fórmula (§6 do
`sdd.config.md` proíbe decidir metodologia na implementação) — fica
registrado aqui como ponto que a tarefa (`/sdd:tasks`) precisa endereçar
como uma pergunta explícita ao especialista antes da implementação, **não**
como uma escolha arbitrária deste plano. Ver R2.10 (Risks) para o risco
correspondente.

## R2.5. Data Flow

Estende o passo 6 (Gates) e acrescenta um sub-passo ao passo 11 (Snapshot) da
§5 (Rodada 1) — a numeração de 11 passos não muda; o que muda é o que o
passo 6 produz.

**Passo 6 revisto — Gates 1–4, agora com `ORDEM_ACOES` mais rica:**

1. **Gate 1 (`aplicar_gate_1_informacao`, `RF-32`).** Nos dois ramos de
   bloqueio, em vez de `acao=None`:
   - Ramo `STATUS_DIVIDA == QUITADA_A_CONFIRMAR`: constrói `AcaoRequerida`
     com `TIPO_ACAO="INFORMACAO"`, `CAMPO_PENDENTE="STATUS_DIVIDA"`,
     `gate_origem=1`, `DIVIDA_ID=divida.DIVIDA_ID`,
     `ACAO_ID=_compor_ACAO_ID(divida_id=divida.DIVIDA_ID, tipo_acao="INFORMACAO")`.
   - Ramo `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` (dentro de
     `compor_VALOR_RELEVANTE_PARA_QUITACAO`, `engine/valor_quitacao.py` —
     mas a `AcaoRequerida` é montada em `aplicar_gate_1_informacao`, que já
     recebe `resultado_valor_relevante` como parâmetro; `valor_quitacao.py`
     não precisa mudar, só o consumidor em `gates.py`): idêntico, com
     `CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL"`.
   - `EC-22` confirma que os dois ramos são mutuamente exclusivos por
     construção (o segundo `if` só é avaliado quando o primeiro não
     retornou) — `CAMPO_PENDENTE` nunca é ambíguo.

2. **Gate 3 (`aplicar_gate_3_transformacao`, `RF-30`).** Já constrói
   `AcaoRequerida` (Rodada 1) distinguindo `RENEGOCIACAO_PENDENTE` de
   `TROCA_PENDENTE` internamente (variável `origem`, hoje só usada em texto
   livre). Passa a também preencher `TIPO_ACAO="RENEGOCIACAO"` ou
   `TIPO_ACAO="TROCA"` a partir do mesmo discriminador — nunca a partir de
   `gate_origem` (que seria só `3`, insuficiente para diferenciar os dois,
   conforme `RF-30`/§12.2). Quando ambos `RENEGOCIACAO_PENDENTE` e
   `TROCA_PENDENTE` são `True` simultaneamente (caso já tratado no texto
   livre "RENEGOCIACAO_PENDENTE e TROCA_PENDENTE", Rodada 1, linha 369):
   **ambiguidade explícita, ver R2.10** — nem `RF-30` nem `app-aluno.spec.md`
   §10 `OQ-14` resolvem qual `TIPO_ACAO` único emitir nesse caso combinado.

3. **Gate 2 (`aplicar_gate_2_contencao_risco`).** **Fora de escopo desta
   rodada.** `RF-30` só mapeia Gate 1 → `INFORMACAO`, Gate 3 →
   `RENEGOCIACAO`/`TROCA`, fora dos gates → `ECONOMIA`. Gate 2 não aparece
   no mapeamento de `RF-30` nem em nenhum `AC-NN` desta rodada — a
   `AcaoRequerida` que o Gate 2 já emite (Rodada 1, `RISCO_MATERIAL_
   IMINENTE`) recebe `ACAO_ID` (toda `AcaoRequerida` precisa do campo,
   `RF-28` não distingue por gate de origem) mas **não** recebe `TIPO_ACAO`
   de nenhum dos quatro valores do domínio — ver ambiguidade explícita em
   R2.10.

4. **Ação de economia (`RF-33`), fora do fluxo de gates.** Ponto de emissão
   novo: quando `estado.ECONOMIA_POTENCIAL_IMEDIATA > 0` (dinheiro,
   `engine/estado.py:340`, Rodada 1), emite uma `AcaoRequerida` com
   `TIPO_ACAO="ECONOMIA"`, `DIVIDA_ID=None`, `gate_origem=None`,
   `CAMPO_PENDENTE=None`,
   `ACAO_ID=_compor_ACAO_ID(divida_id=None, tipo_acao="ECONOMIA")`. Decisão
   de **onde** no código (ver R2.6): dentro de `engine/motor.py::
   calcular_plano`, porque é o único ponto do fluxo que já tem `estado`
   (para ler `ECONOMIA_POTENCIAL_IMEDIATA`) **e** monta `ORDEM_ACOES` final
   antes do snapshot — `particionar_elegibilidade` (gates.py) opera por
   dívida e não recebe `EstadoFinanceiro` inteiro hoje, só `Divida`
   individuais, e não deveria passar a receber um parâmetro estrutural só
   para um caso que não é sobre dívida nenhuma (`EC-20`).
   `ECONOMIA_POTENCIAL_IMEDIATA = 0` não emite nada (`AC-54`) — é o caso
   comum, não uma falha.

5. **Consolidação.** A `AcaoRequerida` de economia é concatenada ao
   `particao.ORDEM_ACOES` (saída de `particionar_elegibilidade`) dentro de
   `calcular_plano`, antes de repassar para `publicar_ORDEM_QUITACAO`
   (`engine/ordem.py`, que já apenas repassa `particao.ORDEM_ACOES` tal como
   veio — Rodada 1, linha 265). `EC-20` exige que a ação de economia
   coexista com ações de informação do Gate 1 no mesmo `ORDEM_ACOES` — a
   concatenação simples satisfaz isso porque as duas fontes (gates +
   economia) são independentes por construção.

*Falha desta rodada, adicionada à tabela da §8 (Rodada 1):* nenhuma nova —
`ECONOMIA_POTENCIAL_IMEDIATA` já é `Dinheiro` não-opcional em
`EstadoFinanceiro` (Rodada 1, nunca `DinheiroTalvez`), então não há estado
"desconhecido" a tratar aqui que a Rodada 1 não trate já.

## R2.6. External Interfaces

Nenhuma interface externa nova. O motor continua sem chamada de rede
(inalterado da §6, Rodada 1). Nota de decisão de localização de código,
registrada aqui por não caber melhor em outra seção do template:

| Decisão | Onde | Por quê |
| --- | --- | --- |
| Emissão da ação de economia vive em `engine/motor.py::calcular_plano`, não em `engine/gates.py` | R2.5 item 4 | `engine/gates.py` é sobre avaliar gates de UMA dívida por vez (`Divida` como parâmetro); a ação de economia não é sobre dívida nenhuma (`DIVIDA_ID=None`, `RF-33`) e depende de um campo de `EstadoFinanceiro` (`ECONOMIA_POTENCIAL_IMEDIATA`) que nenhuma função de `gates.py` recebe hoje. Colocar em `motor.py` evita alterar a assinatura de `particionar_elegibilidade`/`aplicar_gates_1_a_4` para um caso que estruturalmente não é sobre gate |
| `_compor_ACAO_ID` vive em `engine/gates.py`, reaproveitada por `motor.py` | R2.4, R2.5 | Os três pontos de emissão (Gate 1, Gate 3, economia) precisam da mesma função determinística; `gates.py` já define `AcaoRequerida` e é importado por `motor.py` (Rodada 1, `from engine.gates import particionar_elegibilidade`) — expor `_compor_ACAO_ID` como função não-privada de `gates.py` (ou um módulo minúsculo `engine/acao_id.py` se a equipe preferir isolar) evita duplicar a lógica de composição em dois arquivos |

## R2.7. State Management

Nenhuma mudança na tabela de estado da §7 (Rodada 1). `ACAO_ID` não é estado
mutável — é uma função pura de `(DIVIDA_ID, TIPO_ACAO)`, recalculada a cada
`calcular_plano`, nunca armazenada ou lida de um contador externo. Isso é a
própria razão de a estabilidade entre snapshots (`AC-48`) funcionar sem
persistência: dois snapshots que calculam a mesma dívida com o mesmo
`TIPO_ACAO` produzem o mesmo `ACAO_ID` porque é a mesma função pura aplicada
aos mesmos dois insumos, não porque algo foi lembrado entre chamadas. Mesma
proibição já vigente (Rodada 1, §7): nenhum `uuid4`, nenhum contador
`itertools.count`, nenhum estado global mutável para gerar `ACAO_ID`.

## R2.8. Error Handling Strategy

| Situação | Detecção | Resposta do motor | Recuperação |
| --- | --- | --- | --- |
| Dívida bloqueada no Gate 1 por `STATUS_DIVIDA == QUITADA_A_CONFIRMAR` | `aplicar_gate_1_informacao`, ramo 1 | `AcaoRequerida(TIPO_ACAO="INFORMACAO", CAMPO_PENDENTE="STATUS_DIVIDA")` em `ORDEM_ACOES`, em vez de `acao=None` (Rodada 1) | `AC-56` |
| Dívida bloqueada no Gate 1 por `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` | `aplicar_gate_1_informacao`, ramo 2 | `AcaoRequerida(TIPO_ACAO="INFORMACAO", CAMPO_PENDENTE="SALDO_DEVEDOR_ATUAL")` em `ORDEM_ACOES` | `AC-57` |
| `ECONOMIA_POTENCIAL_IMEDIATA = 0` | `calcular_plano`, antes de emitir a ação de economia | Nenhuma `AcaoRequerida` de `TIPO_ACAO="ECONOMIA"` é adicionada — não é erro, é o caso comum | `AC-54` |
| Consumidor interno de `engine/` lê `AcaoRequerida.DIVIDA_ID` presumindo `str` | `mypy --strict` (comando `build`, `sdd.config.md` §2) | Falha de tipagem **antes** de chegar a runtime — nunca comportamento silencioso | `AC-55`, `EC-21` |
| Gates 1/3/economia geram `ACAO_ID` colidente por acaso (dois insumos diferentes produzindo a mesma string) | Não detectável em runtime sem custo adicional — mitigado por desenho do formato (R2.4: separador que não aparece em `DIVIDA_ID`/`TIPO_ACAO` observados) | N/A — ver R2.10 para o risco assumido | Auditoria de fixtures/gabaritos na revisão desta mudança |

**Regra herdada, reafirmada.** Nenhuma degradação silenciosa (princípio da
§8, Rodada 1) continua valendo: um `TIPO_ACAO` fora do domínio fechado, ou um
`CAMPO_PENDENTE` fora dos dois valores, é erro de tipagem/execução detectável
— nunca um valor aceito e propagado.

## R2.9. Testing Strategy

**Estratégia central desta rodada: a mudança de maior risco (`RF-32`) exige
reexecução ativa da suíte de homologação da Rodada 1, não apenas testes
novos.** Isso é tratado como trabalho de primeira classe, não nota de
rodapé — a spec (`AC-58`–`AC-60`, tolerância zero) e o risco documentado em
§8 da spec (linha "Gate 1 passa a emitir `AcaoRequerida`") exigem isso
explicitamente.

- **Reexecução obrigatória, tolerância zero** (`pytest -m "gabarito or
  invariante"`, mesmo marcador já definido na §9 Rodada 1):

  | Teste | Âncora | O que muda nesta rodada |
  | --- | --- | --- |
  | `test_gabarito_a_deficit` (`GAB-A`) | `AC-58`, `AC-60` | Reexecutar; se `GAB-A` tiver dívida bloqueada no Gate 1, `ORDEM_ACOES` esperada precisa ser atualizada de `()` para a `AcaoRequerida` correspondente |
  | `test_gabarito_b_equilibrio_fragil` (`GAB-B`) | `AC-58`, `AC-60` | Idem — auditar se `GAB-B` toca Gate 1 |
  | `test_gabarito_c_*` (`GAB-C`) | `AC-58`, `AC-60` | Idem — auditar se `GAB-C` toca Gate 1. `AC-01`–`AC-04` (método/ordem/custo/prazo) são tolerância zero e **não** devem mudar — só `ORDEM_ACOES`, que é fila paralela, pode mudar |
  | `test_invariante_gab03_rotativo` (`GAB-03`) | `AC-58` (citado nominalmente na spec) | Dívida rotativa sem saldo/pagamento é exatamente o cenário do Gate 1/ramo 2 (`SALDO_DEVEDOR_ATUAL is DESCONHECIDO`) — `ORDEM_ACOES` que hoje vem vazia passa a conter a `AcaoRequerida` de informação. Teste **precisa** ser reescrito, não só reexecutado |
  | `test_invariante_gab01/02/04/05` | `AC-60` | Reexecutar; mudança esperada só se alguma dessas dívidas também estiver bloqueada no Gate 1 (auditar fixture a fixture) |
  | Cenário `EC-17` (todas bloqueadas pelos gates) | `AC-59` | `ORDEM_ACOES` que hoje vem vazia (se todas bloqueadas forem por Gate 1) passa a vir preenchida com as ações de informação correspondentes. Teste dedicado a `EC-17` precisa ser localizado (`tests/regras/test_gates.py` ou onde `EC-17` já está coberto na Rodada 1) e sua asserção de `ORDEM_ACOES == ()` corrigida |

  **Procedimento obrigatório, não opcional:** rodar a suíte completa (`pytest
  -q`) **antes** de escrever qualquer teste novo desta rodada, registrar
  quais gabaritos tocam Gate 1 (grep por `QUITADA_A_CONFIRMAR` ou
  `SALDO_DEVEDOR_ATUAL.*DESCONHECIDO` nas fixtures de `tests/fixtures/`), e
  só então implementar `RF-32`. Depois de implementado, rodar de novo e
  atualizar cada expectativa de `ORDEM_ACOES` divergente — nunca ajustar o
  código para "não quebrar o teste antigo" quando o teste antigo está
  correto e é a mudança de comportamento que é esperada.

- **Unitários novos** (`tests/regras/test_gates.py`, mesmo arquivo da
  Rodada 1):

  | Teste | Âncora |
  | --- | --- |
  | `test_gate1_quitada_a_confirmar_emite_acao_informacao` | `AC-56` |
  | `test_gate1_saldo_desconhecido_emite_acao_informacao` | `AC-57` |
  | `test_gate1_dois_ramos_mutuamente_exclusivos` | `EC-22` |
  | `test_tipo_acao_dominio_fechado_ascii` | `AC-49` |
  | `test_tipo_acao_gate1_informacao` | `AC-50` |
  | `test_tipo_acao_gate3_renegociacao` | `AC-51` |
  | `test_tipo_acao_gate3_troca` | `AC-52` |
  | `test_acao_economia_emitida_quando_potencial_positivo` | `AC-53` |
  | `test_acao_economia_nao_emitida_quando_potencial_zero` | `AC-54` |
  | `test_acao_economia_coexiste_com_acoes_gate1` | `EC-20` |
  | `test_acao_id_estavel_entre_snapshots_mesma_divida_mesmo_tipo` | `AC-48` |
  | `test_acao_id_estavel_para_acao_economia_entre_snapshots` | `OQ-22` (decisão fechada, verificação obrigatória) |

- **Novo teste estático** (`tests/estatica/`, mesmo padrão da Rodada 1):
  - `test_acao_id_determinismo_puro`: chama `_compor_ACAO_ID` (ou a função
    exposta) duas vezes com os mesmos insumos e exige igualdade; chama com
    insumos diferentes e exige `ACAO_ID` diferente (não é prova de ausência
    total de colisão, mas cobre o contrato de determinismo exigido por
    `OQ-21`).
  - `test_tipo_acao_apenas_quatro_valores`: varre `TIPO_ACAO_VALORES` e
    falha se um quinto literal aparecer em qualquer `AcaoRequerida`
    construída pela suíte de gabaritos — reforça `AC-49` como propriedade
    estrutural, não só por exemplo.

- **`RF-31` — auditoria de consumidores (`AC-55`, `EC-21`).** Não é um teste
  de comportamento; é uma verificação de **cobertura de tipo**. Procedimento:
  1. `mypy --strict engine/` (comando `build` já definido em
     `sdd.config.md` §2) roda **depois** de `DIVIDA_ID` ser relaxado para
     `str | None` — qualquer uso de `acao.DIVIDA_ID` como `str` sem checar
     `None` primeiro (`is None`, `is not None`, `match`) passa a falhar a
     checagem de exaustividade, mesmo mecanismo já usado para `DESCONHECIDO`
     (Rodada 1, §2). Auditado nesta rodada: `engine/ordem.py:269` lê
     `ResultadoGates.DIVIDA_ID` (campo diferente, sempre `str`, não afetado);
     nenhum outro ponto de `engine/*.py` lê `AcaoRequerida.DIVIDA_ID` hoje
     (confirmado por grep nesta rodada de planejamento — ver R2.3). Se a
     implementação introduzir um novo consumidor, o `mypy --strict` já
     pego pela suíte de CI (`sdd.config.md` §2, comando `build`) é a rede de
     segurance.
  2. Reportar no PR/tarefa de implementação a lista de arquivos tocados por
     essa checagem, para que a revisão confirme que `EC-21` (falha visível
     no `build`, não silenciosa) se cumpriu.

- **E2E:** inalterado da Rodada 1 — não se aplica a este slug.

- **Fora de teste automatizado:** a fórmula de `RESERVA_MOBILIZAVEL`/
  `ATAQUE_IMEDIATO_RECOMENDADO` (R2.4, ambiguidade explícita) não pode ser
  testada por comportamento até a fórmula ser fechada pelo especialista —
  só o **contrato de tipo/posição** (`AC-61`: existe, é `Dinheiro`, está no
  bloco certo) é testável nesta rodada.

## R2.10. Risks & Trade-offs

| Decisão | Alternativa descartada | Por quê | Risco assumido |
| --- | --- | --- | --- |
| `ACAO_ID = f"{DIVIDA_ID}:{TIPO_ACAO}"` / `f"ACAO:{TIPO_ACAO}"` (R2.4) | UUID; contador incremental; hash SHA de campos | A spec (`OQ-21`, respondida) exige determinismo puro por composição, sem estado externo — UUID e contador são não-determinísticos por natureza (dependem de quando/em que ordem são gerados); hash SHA seria determinístico mas ofusca a leitura humana do `ACAO_ID` em log/debug sem ganho, já que não há requisito de opacidade | Nenhuma prova formal de ausência de colisão entre um `DIVIDA_ID` que contenha `:` e o padrão. Mitigado: auditoria de fixtures atuais (nenhum `DIVIDA_ID` observado contém `:`) e teste estático (R2.9) que cobre o contrato de determinismo, não colisão exaustiva. **Se o domínio de `DIVIDA_ID` vier a admitir `:` no futuro, este formato precisa ser revisitado** |
| Emissão da ação de economia em `engine/motor.py`, não em `engine/gates.py` (R2.5, R2.6) | Adicionar `EstadoFinanceiro`/`ECONOMIA_POTENCIAL_IMEDIATA` como parâmetro de `particionar_elegibilidade` | `particionar_elegibilidade` e toda a cadeia de gates são, por desenho da Rodada 1, sobre avaliar **uma dívida por vez** — introduzir um parâmetro estrutural para um caso que não é sobre dívida nenhuma quebraria essa uniformidade e obrigaria todo teste existente de gates a passar um `EstadoFinanceiro` que não usa | Lógica de `ORDEM_ACOES` fica dividida entre dois módulos (`gates.py` para as três primeiras origens, `motor.py` para a quarta) em vez de centralizada. Mitigado: `_compor_ACAO_ID` é a única lógica compartilhada, e `motor.py` já orquestra o passo 6 inteiro (Rodada 1) |
| `TIPO_ACAO: str` livre, não `Enum` (R2.2) | `Enum` com quatro membros | `RF-29`/`OQ-13` fixam `str`, decisão já tomada pelo especialista, fora do escopo de reabertura deste slug (§9 Out of Scope da spec) | Domínio fechado não é imposto pelo `mypy` como seria com `Enum` — só por teste estático (`TIPO_ACAO_VALORES`, R2.9) e por revisão de código. Risco aceito porque a spec já decidiu o tipo |
| `CAMPO_PENDENTE: Literal[...] \| None = None`, default `None` (R2.4) | Campo obrigatório em toda `AcaoRequerida` | `RF-34` só faz sentido para `TIPO_ACAO="INFORMACAO"`; forçar um valor em `RENEGOCIACAO`/`TROCA`/`ECONOMIA` inventaria semântica que a spec não define, violando §6 do `sdd.config.md` | Um consumidor que esqueça de checar `TIPO_ACAO == "INFORMACAO"` antes de usar `CAMPO_PENDENTE` recebe `None` silenciosamente em vez de erro — mitigado por `mypy --strict` (campo é `X \| None`, exige checagem) e por ser fora do escopo de `engine/` (consumo é do `app-aluno`) |

### R2.10.1. Ambiguidades explícitas — resolvidas pelo usuário em 2026-09-04 (regra `sdd.config.md` §3)

Registradas aqui em vez de decididas em silêncio pelo agente. `AMB-R2-02` e
`AMB-R2-03` foram respondidas diretamente pelo usuário (autoridade de
especialista para esta sessão) e não bloqueiam mais `/sdd:tasks`.
`AMB-R2-01` **permanece bloqueante** — envolve fórmula de cálculo financeiro,
e a regra do projeto de tolerância zero (§10.3 da spec) exige que ela venha
do especialista do método, não de suposição — foi promovida a `OQ-23` na
spec (ver `specs/motor-calculo.spec.md` §10, Rodada 2).

| ID | Ambiguidade | Onde aparece | Status |
| --- | --- | --- | --- |
| `AMB-R2-01` → `OQ-23` | Fórmula de `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO` — nenhuma fonte publica o cálculo, só nome/tipo/posição (`RF-35`) | R2.4 | **bloqueante** — `AC-61` só pode ser verificado por tipo/posição até a fórmula ser fechada pelo especialista; `/sdd:tasks` deve restringir a tarefa de `RF-35` ao contrato (shape/tipo), com o cálculo real como tarefa separada de backlog dependente de `OQ-23` |
| `AMB-R2-02` | `TIPO_ACAO` do Gate 2 (`RISCO_MATERIAL_IMINENTE`, contenção de risco) — `RF-30` só mapeia Gate 1/Gate 3/economia; Gate 2 não tem `TIPO_ACAO` no domínio de quatro valores | R2.5 item 3 | **resolvida (usuário, 2026-09-04)** — Gate 2 emite `TIPO_ACAO = "RENEGOCIACAO"`. Racional: contenção de risco em dívida já comprometida é semanticamente mais próxima de renegociação do que dos outros três valores do domínio fechado (não introduz quinto valor, preservando `RF-29`) |
| `AMB-R2-03` | `TIPO_ACAO` quando `RENEGOCIACAO_PENDENTE` e `TROCA_PENDENTE` são ambos `True` na mesma dívida (Gate 3) | R2.5 item 2 | **resolvida (usuário, 2026-09-04)** — prioridade fixa: `RENEGOCIACAO` prevalece sobre `TROCA` quando ambos pendentes na mesma dívida. `TIPO_ACAO = "RENEGOCIACAO"` é emitido nesse caso combinado; `"TROCA"` só é emitido quando `TROCA_PENDENTE` é `True` e `RENEGOCIACAO_PENDENTE` é `False` |

> `AMB-R2-02` e `AMB-R2-03` não reabrem `OQ-21`/`OQ-22` (formato de
> `ACAO_ID` e sua estabilidade, ambas fechadas) — eram lacunas **novas**,
> específicas do detalhamento de implementação que a spec ainda não havia
> examinado neste nível, agora fechadas. `AMB-R2-01` segue como `OQ-23`,
> registrada em `specs/motor-calculo.spec.md` §10, até resposta do
> especialista do método.

## R2.11. Traceability

| Requisito | Coberto por (seção do plano) |
| --- | --- |
| `RF-28` — `ACAO_ID` estável entre snapshots | R2.1 (ponto 1) · R2.4 (`_compor_ACAO_ID`) · R2.7 (por que é estável sem estado) · R2.9 (`AC-48`, `test_acao_id_estavel_...`) |
| `RF-29` — `TIPO_ACAO` domínio fechado de 4 valores | R2.2 (decisão `str` não `Enum`) · R2.4 (`TIPO_ACAO_VALORES`) · R2.9 (`AC-49`, `test_tipo_acao_dominio_fechado_ascii`) · R2.10 (trade-off `str` vs `Enum`) |
| `RF-30` — `TIPO_ACAO` derivado de `GATE_PENDENTE`, nunca `gate_origem` | R2.5 (itens 1–2) · R2.9 (`AC-50`–`AC-52`) · R2.10.1 (`AMB-R2-02`, `AMB-R2-03` — Gate 2 → `RENEGOCIACAO`, e prioridade `RENEGOCIACAO` > `TROCA` no caso combinado do Gate 3, ambas resolvidas) |
| `RF-31` — `DIVIDA_ID: str \| None`, varredura de consumidores | R2.2 (`mypy --strict` como mecanismo) · R2.4 (contrato) · R2.3 (auditoria de `engine/ordem.py`) · R2.9 (`AC-55`, `EC-21`, procedimento de auditoria) |
| `RF-32` — Gate 1 emite `AcaoRequerida` nos dois ramos | R2.1 (ponto 2) · R2.5 (item 1) · R2.9 (reexecução obrigatória, `AC-56`–`AC-60`, tabela de gabaritos) · R2.10 (risco "maior risco desta rodada") |
| `RF-33` — ação de economia fora do fluxo de gates | R2.1 (ponto 3) · R2.5 (item 4) · R2.6 (decisão de localização em `motor.py`) · R2.9 (`AC-53`, `AC-54`, `EC-20`) |
| `RF-34` — `CAMPO_PENDENTE` domínio fechado de 2 valores | R2.2 (`Literal`) · R2.4 (contrato, default `None`) · R2.5 (item 1, mapeamento por ramo) · R2.9 (`AC-56`, `AC-57`) · R2.10 (trade-off do default) |
| `RF-35` — `Diagnostico.RESERVA_MOBILIZAVEL`/`ATAQUE_IMEDIATO_RECOMENDADO` | R2.1 (ponto 4) · R2.4 (contrato + ambiguidade de fórmula) · R2.9 (`AC-61`, limitado a tipo/posição) · R2.10.1 (`OQ-23`, ex-`AMB-R2-01`, ainda bloqueante) |

**Cobertura desta rodada:** 8 de 8 requisitos (`RF-28`–`RF-35`). Nenhum
requisito da Rodada 2 ficou sem seção correspondente. Das três ambiguidades
levantadas, duas (`AMB-R2-02`, `AMB-R2-03`) foram resolvidas pelo usuário em
2026-09-04 e não bloqueiam mais `/sdd:tasks`. A terceira (`AMB-R2-01`) foi
promovida a `OQ-23` na spec e **permanece bloqueante** para a tarefa de
cálculo real de `RF-35` — a tarefa de contrato/shape pode prosseguir, a de
fórmula depende de resposta do especialista do método.

> Requisito sem cobertura é buraco no plano. Item de plano sem requisito é
> over-engineering.

---

# Rodada 3 — Ataque Imediato e Reserva, fatias 3A e 3B (2026-09-07)

| Campo  | Valor                                            |
| ------ | ------------------------------------------------ |
| Slug   | `motor-calculo`                                  |
| Spec   | [`specs/motor-calculo.spec.md`](../specs/motor-calculo.spec.md) §2 (`RF-36`–`RF-52`), §13 |
| Fonte normativa | §13 da spec — transcrição integral do documento canônico *"PIQ v1.0.1 — Definição Canônica de `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO`"* (2026-09-07), **congelado** |
| Discovery | [`specs/motor-calculo.discovery.md`](../specs/motor-calculo.discovery.md) §13 (rodada de 2026-09-07) |
| Status | `rascunho`                                       |
| Autor  | virtushold@gmail.com                             |
| Data   | 2026-09-07                                       |

> **Escopo desta seção.** Cobre exclusivamente `RF-36` a `RF-52` — a fatia
> **3A (modelagem de estado)** e a fatia **3B (cálculo puro)**. As seções 1–11
> (Rodada 1) e R2.1–R2.11 (Rodada 2) **não são alteradas**: continuam a fonte
> de verdade de tudo que existia antes de 2026-09-07. Onde esta rodada estende
> uma decisão anterior (ex.: `Diagnostico`, `EstadoFinanceiro`), o texto abaixo
> aponta a seção original em vez de duplicá-la.
>
> **A fatia 3C está fora de escopo** (spec §9): `ATAQUE_IMEDIATO_APROVADO`, o
> passo de confirmação do usuário e a injeção no cronograma-base. Consequência
> operacional deste plano: **nenhum item desta rodada toca
> `engine/ciclo_mensal.py`**. Nem a trava de conservação de igualdade exata
> (`:596`), nem `mes_primeira_vitoria` (`:809-812`), nem a redação de
> `RF-14`/`RF-15` (`:748-750`).
>
> **Precedência inalterada.** A §13 é normativa e congelada
> (*"Nenhuma dessas decisões fica a critério do desenvolvedor"*). Este plano
> decide **como** transcrevê-la para código — nunca **o que** ela diz. Onde a
> §13 não publicou regra (`OQ-26`, `OQ-27`, `OQ-29`, `OQ-30`, `OQ-31`,
> `OQ-32`, `OQ-35`), este plano **não inventa**: modela a lacuna como entrada
> de contrato e registra em R3.10.1.

## R3.1. Architecture Overview

Nenhuma camada nova, nenhuma dependência nova, nenhum ponto de I/O novo. A
rodada acrescenta **um módulo de cálculo puro** ao motor e **estende o
contrato de entrada** que já existe.

```text
 (fora de engine/ — app-aluno, OQ-37)
  respostas Bloco 3/4  ──montador de estado──┐
                                             ▼
 [0] CONTRATO DE ENTRADA — engine/estado.py  (3A: RF-36..RF-39)
     EstadoFinanceiro
       + RESERVA_EXISTE, RESERVA_TOTAL, DISPOSICAO_USO_RESERVA,
         VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO          ← RF-36
       + DINHEIRO_DISPONIVEL                             ← RF-37
       + investimentos: tuple[ItemInvestimento, ...]     ← RF-38
       + ativos:        tuple[ItemAtivo, ...]            ← RF-38
       + recursos_extraordinarios:
                        tuple[RecursoExtraordinario, ...]← RF-39
     engine/tipos.py + CLASSIFICACAO_MOBILIZACAO (4 valores)  ← RF-40
                                             │
                                             ▼
 [1] CÁLCULO PURO — engine/ataque_imediato.py  (3B: RF-43..RF-50, RF-52)
     ┌────────────────────────────────────────────────────────────┐
     │ derivar_RESERVA_MOBILIZAVEL(...)         §13.1  → RF-43     │
     │ calcular_ATAQUE_IMEDIATO_POTENCIAL(...)  §13.2  → RF-44     │
     │ calcular_CAIXA_RECOMENDADO(...)                             │
     │ calcular_INVESTIMENTOS_RECOMENDADOS(...) §13.3  → RF-45     │
     │ calcular_ATIVOS_RECOMENDADOS(...)                           │
     │ calcular_EXTRAORDINARIOS_RECOMENDADOS(...)                  │
     │ calcular_NECESSIDADE_RESIDUAL(...)       §13.4  → RF-46     │
     │ derivar_RESERVA_RECOMENDADA(...)                            │
     │ calcular_ATAQUE_IMEDIATO_RECOMENDADO(...)§13.3  → RF-47     │
     └────────────────────────────────────────────────────────────┘
       ↑ TODAS as entradas por parâmetro (NFR Pureza · RF-48)
         NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL entra como argumento
                                             │
                                             ▼
 [2] DIAGNOSTICO — engine/diagnostico.py  (RF-41, RF-51)
     Diagnostico.RESERVA_MOBILIZAVEL: Dinheiro → DinheiroTalvez  ← RF-41
     Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro (inalterado)
     calcular_diagnostico() chama [1] em vez de dinheiro(0)      ← RF-51
```

**Quatro pontos de mudança, e só quatro:**

1. **`engine/tipos.py`** — enum `CLASSIFICACAO_MOBILIZACAO`, domínio fechado
   de quatro valores (`RF-40`). Sem função de derivação (`AC-67`, `OQ-26`).
2. **`engine/estado.py`** — três dataclasses de item novas
   (`ItemInvestimento`, `ItemAtivo`, `RecursoExtraordinario`), dois enums de
   domínio de reserva, e nove campos novos em `EstadoFinanceiro`
   (`RF-36`–`RF-39`).
3. **`engine/ataque_imediato.py`** (arquivo **novo**) — as nove funções puras
   da §13 (`RF-43`–`RF-47`, `RF-52`) e o invariante de hierarquia (`RF-50`).
4. **`engine/diagnostico.py`** — mudança de tipo de `RESERVA_MOBILIZAVEL`
   (`RF-41`), substituição dos dois `dinheiro(0)` (`RF-51`) e reescrita da
   docstring que cita `OQ-23` como aberta.

Mais uma edição de **uma linha** fora de `engine/`:
`collection/registros/bloco-04.yaml:156` (`RF-42`).

**Nenhuma lei de arquitetura é violada.** `engine/` continua sem importar
`persistencia/`, `app/`, `collection/` ou `report/`; sem I/O; sem relógio;
sem parâmetro `P_*` embutido (nenhuma fórmula da §13 usa parâmetro
calibrável — todas as entradas vêm do estado ou do argumento). O motor
continua não conhecendo pergunta: `B4.03A` aparece na §13.1 como **ID de
pergunta**, e este plano o traduz para o campo de domínio
`VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO: DinheiroTalvez` — a mesma fronteira
já firmada na Rodada 2 para `CAMPO_PENDENTE` (discovery, mudança 7).

## R3.2. Tech Stack

**Nenhuma dependência nova.** Verificado por leitura direta do código atual
(`engine/tipos.py`, `engine/estado.py`, `engine/precisao.py`,
`engine/diagnostico.py`): stdlib pura — `decimal`, `dataclasses`, `enum`,
`typing.Final`, `from __future__ import annotations`. `pyproject.toml`
confirma `dependencies = []` para o pacote do motor. A stack desta rodada é
a mesma da Rodada 1 (§2) e da Rodada 2 (R2.2); **a decisão aqui é mantê-la**,
e isso também se justifica requisito a requisito:

| Escolha | Uso | Justificativa (ancorada em `RF-NN`) |
| --- | --- | --- |
| `Decimal` via `engine/precisao.dinheiro()` (stdlib `decimal`, já em uso) | todo valor monetário das fórmulas da §13 | `RF-43`–`RF-47` + NFR "Tolerância dos `GAB-AI`: zero". `MIN`/`MAX`/soma sobre `Decimal` são exatos por construção; `float` produziria `Decimal("8000.000000001")` em `NECESSIDADE_RESIDUAL` e falharia `AC-75` sob tolerância zero. Alternativa descartada: `float` — proibido pela NFR de precisão e pelo teste estático `tests/estatica/test_sem_float_no_motor.py` |
| `DinheiroTalvez = Dinheiro \| Desconhecido` (`engine/tipos.py`, já existente) | `RESERVA_TOTAL`, `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`, `Diagnostico.RESERVA_MOBILIZAVEL` | `RF-36`, `RF-41`, `RF-43`, `AC-62`, `AC-68`, `AC-73`. A §13.1 exige `DESCONHECIDA` como **valor**, não ausência — e a §13.1 já diz explicitamente *"alinha-se ao `DESCONHECIDO` já existente em `engine/tipos.py`"*. **Reaproveitar o sentinela existente, não criar mecanismo novo**: é o mesmo tipo que `SALDO_DEVEDOR_ATUAL`/`VALOR_RELEVANTE_PARA_QUITACAO` já usam. Alternativas descartadas: `Optional[Decimal]` (`None` significa "não perguntado", outra coisa — `RF-16`); um segundo sentinela `RESERVA_INDECISA` (duplicaria o mecanismo e quebraria a exaustividade que `mypy --strict` já garante) |
| `Enum` de domínio fechado (stdlib `enum`, já em uso) | `CLASSIFICACAO_MOBILIZACAO` (`RF-40`), `RESERVA_EXISTE`, `DISPOSICAO_USO_RESERVA` (`RF-36`), `CERTEZA_RECURSO_EXTRAORDINARIO`, `JANELA_RECURSO_EXTRAORDINARIO` (`RF-39`) | `AC-66` exige *"exatamente quatro membros, sem quinto valor"* — `Enum` é o único mecanismo do projeto que torna um quinto valor inexprimível em runtime **e** em `mypy --strict`. Alternativa descartada: `Literal[...]` (usado em `CAMPO_PENDENTE`, R2.2), rejeitado aqui porque a classificação é conceito de domínio próprio da §13, com nome normativo — mesmo caso de `GATE_PENDENTE`/`NIVEL_RISCO`, não de "dois nomes de campo de `Divida`" |
| `@dataclass(frozen=True, slots=True)` (stdlib, já em uso) | `ItemInvestimento`, `ItemAtivo`, `RecursoExtraordinario` (`RF-38`, `RF-39`) | `RF-38`/`AC-64` exigem coleção **imutável** de itens; `frozen=True` é o que faz `EstadoFinanceiro` continuar hasheável por valor (`RF-10`/`V-01`, snapshot nunca sobrescrito) e o que permite `_serializar_canonico` (`engine/snapshot.py:136`) tratar os itens novos sem nenhuma alteração |
| `tuple[X, ...]` (stdlib) | as três coleções em `EstadoFinanceiro` (`RF-38`, `RF-39`) | `RF-38` fixa o padrão `tuple[Divida, ...]` explicitamente. Ordem preservada e imutável — `_serializar_canonico` já trata `tuple` como sequência significativa (`engine/snapshot.py:154-156`), sem mudança |
| `mypy --strict` (comando `build`, `sdd.config.md` §2 — já em uso) | varredura de consumidores de `RF-41` | `RF-41`, `AC-68`. É o mecanismo que torna a quebra de contrato verificável por máquina: todo consumidor que trate `Diagnostico.RESERVA_MOBILIZAVEL` apenas no ramo `Dinheiro` passa a falhar a checagem. Mesma técnica de `RF-31` na Rodada 2 (R2.2) |
| `pytest` + `tests/conftest.py::assertar_exato` (já em uso) | os sete `GAB-AI` (`AC-70`–`AC-76`) | NFR "Tolerância dos `GAB-AI`: **zero**" (spec §5, `OQ-34` respondida). **`assertar_monetario` (± R$ 0,05) é proibido aqui** — os `GAB-AI` são `MIN`/`MAX`/soma sem acumulação, e a régua é a de tolerância zero. Ver R3.9 |

**Contagem de dependências novas desta rodada: 0.**

## R3.3. Project Structure

| Caminho | Mudança | Novo? |
| --- | --- | --- |
| `engine/tipos.py` | `+ CLASSIFICACAO_MOBILIZACAO` (4 membros, `RF-40`). Nenhuma função — o módulo continua sendo só modelagem de dado, isento de `REGRAS` pelo lint de `tests/estatica/test_toda_regra_citada.py` | não |
| `engine/estado.py` | `+ RESERVA_EXISTE`, `+ DISPOSICAO_USO_RESERVA`, `+ CERTEZA_RECURSO_EXTRAORDINARIO`, `+ JANELA_RECURSO_EXTRAORDINARIO` (enums de domínio); `+ ItemInvestimento`, `+ ItemAtivo`, `+ RecursoExtraordinario` (dataclasses); `EstadoFinanceiro` ganha 9 campos (`RF-36`–`RF-39`) | não |
| `engine/ataque_imediato.py` | **arquivo novo** — as nove funções puras da §13 + `REGRAS: Final[tuple[str, ...]]` (obrigatório: o módulo tem função pública, `tests/estatica/test_toda_regra_citada.py` exige) | **sim** |
| `engine/diagnostico.py` | `RESERVA_MOBILIZAVEL: Dinheiro → DinheiroTalvez` (`RF-41`); `dinheiro(0)` de `:764-765` substituído pelas chamadas reais (`RF-51`); docstring `:674-687` reescrita (`AC-86`) | não |
| `collection/registros/bloco-04.yaml` | **uma linha**: `:156` `VARIAVEL_GRAVADA: RESERVA_MOBILIZAVEL` → `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`. `ID: B4.03A` **não muda** (`RF-42`, `AC-69`) | não |
| `persistencia/arquivo/repositorio_snapshots.py` | consumidor de contrato: `_estado_financeiro` (`:331-346`) ganha os 9 campos novos; `_diagnostico` (`:400`) troca `_decimal(...)` por `_dinheiro_talvez(...)` em `RESERVA_MOBILIZAVEL`; novos `_item_investimento`/`_item_ativo`/`_recurso_extraordinario` no padrão de `_divida` (`:280`). **Fora de `engine/`, mas dentro deste slug** | não |
| `tests/fixtures/carregar.py` | `carregar_estado_financeiro` (`:174-188`) ganha os 9 campos novos | não |
| `tests/fixtures/gab_a.json`, `gab_b.json`, `gab_c.json` | os 9 campos novos com valores neutros (reserva ausente, coleções vazias, `DINHEIRO_DISPONIVEL = "0"`), para que `AC-87` seja de fato "nada mudou" | não |
| `tests/gabaritos_ataque_imediato/` | **diretório novo** — `GAB-AI-01` a `GAB-AI-07` (`AC-70`–`AC-76`). Ver R3.9 para a decisão de localização e marcador | **sim** |
| `tests/regras/test_ataque_imediato.py` | **arquivo novo** — `AC-77`–`AC-83`, `EC-23`–`EC-31` | **sim** |
| `tests/regras/test_diagnostico.py`, `tests/regras/test_estado.py` (onde existir) | `AC-62`–`AC-66`, `AC-68`, `AC-85`, `AC-86` | não |
| `tests/estatica/` | novo teste: ausência de percentual automático de `RESERVA_TOTAL` (`AC-81`, `RF-49`) e ausência de função de derivação de classificação (`AC-67`) | **sim** (1 arquivo) |
| `tests/regras/*.py` e `tests/invariantes/*.py` que constroem `Diagnostico(...)` ou `EstadoFinanceiro(...)` à mão | **13 arquivos**, listados em R3.10.2 — todos precisam dos campos novos e do `RESERVA_MOBILIZAVEL` retipado | não |
| `pyproject.toml` | `[tool.pytest.ini_options] markers`: registrar `gabarito_ataque_imediato` (R3.9) | não |

**Nota de escopo (spec §9, Out of Scope).** `app/montagem/estado.py:1326`
constrói `EstadoFinanceiro` e vai quebrar por argumento faltante — é o
montador do slug **`app-aluno`** (`OQ-37`), não deste. Este plano **não** o
edita; a coordenação é: 3A entrega o contrato, `app-aluno` preenche.
Idem `tests/app_aluno/estatica/hashes_congelados.json` — a atualização do
hash congelado é procedimento de `app-aluno` (`AC-44` daquela spec), e desta
vez ele cobre **cinco** arquivos (`engine/tipos.py`, `engine/estado.py`,
`engine/diagnostico.py`, `engine/ataque_imediato.py` novo,
`persistencia/arquivo/repositorio_snapshots.py`), não um só. Sinalizar **uma
vez**, ao fim da rodada inteira — não campo a campo (mitigação do risco de
§8 da spec).

## R3.4. Data Model

Contratos e assinaturas. Nomes de **campo** idênticos à §13, caractere por
caractere (`sdd.config.md` §7). Corpo de função é escopo de `/sdd:implement`.

### R3.4.1. Enum de classificação de mobilização — `RF-40`

```python
# engine/tipos.py — RF-40 · §13.2, §13.3, §13.7 · piq-app-spec.md:2614
class CLASSIFICACAO_MOBILIZACAO(Enum):
    """RF-40 · §13 — domínio FECHADO de exatamente quatro valores.

    A canônica (`piq-app-spec.md:2614`) fecha que a classificação é
    DERIVADA pelo motor e PROÍBE perguntá-la. A *regra* de derivação não
    está publicada por nenhuma fonte (`OQ-26`, aberta). Esta rodada entrega
    o DOMÍNIO e recebe a classificação já feita, por item — nunca a deriva.
    Não existe, e não deve existir enquanto `OQ-26` estiver aberta, nenhuma
    função neste projeto que produza um destes quatro valores a partir de
    `LIQUIDEZ_INVESTIMENTOS`, `CUSTO_DESMOBILIZACAO_INVESTIMENTOS`,
    `DISPOSICAO_USO_INVESTIMENTO`, `IMOVEL_POSSUI_PASSIVO` ou tipo de ativo
    (`AC-67`).
    """

    MOBILIZACAO_POSSIVEL = "MOBILIZACAO_POSSIVEL"
    MOBILIZACAO_RECOMENDAVEL = "MOBILIZACAO_RECOMENDAVEL"
    MOBILIZACAO_COM_RESSALVAS = "MOBILIZACAO_COM_RESSALVAS"
    NAO_MOBILIZAR = "NAO_MOBILIZAR"
```

### R3.4.2. Domínios de reserva e de recurso extraordinário — `RF-36`, `RF-39`

```python
# engine/estado.py — RF-36 · §13.1 · B4.02, B4.03 (domínio de coleta,
# traduzido para domínio de motor: o motor não conhece pergunta)
class RESERVA_EXISTE(Enum):
    """RF-36 · §13.1 Regra 1 · B4.02. Ternário: a §13.1 só distingue
    `NAO` de não-`NAO`, mas `SIM` e `INFORMAL` são estados de coleta
    distintos e colapsá-los aqui perderia informação que a devolutiva usa
    (`OQ-25`, aberta — não bloqueia: a aritmética só olha `NAO`)."""

    SIM = "SIM"
    INFORMAL = "INFORMAL"
    NAO = "NAO"


class DISPOSICAO_USO_RESERVA(Enum):
    """RF-36 · §13.1 Regra 1 · B4.03. Quatro valores; a §13.1 reduz a
    `NAO`/não-`NAO`. Os outros três são preservados no estado pelo mesmo
    motivo de `RESERVA_EXISTE` (`OQ-25`)."""

    PARTE = "PARTE"
    GRANDE_PARTE = "GRANDE_PARTE"
    TALVEZ = "TALVEZ"
    NAO = "NAO"


class JANELA_RECURSO_EXTRAORDINARIO(Enum):
    """RF-39 · §13.3 (`EXTRAORDINARIOS_RECOMENDADOS`) · B3.05C — janela de
    recebimento. `ATE_30D` é a única janela do "momento atual"; as demais
    são futuro, e recurso apenas previsto para o futuro NÃO compõe o
    recomendado (§13.3)."""

    ATE_30D = "ATE_30D"
    UM_A_TRES_MESES = "1_3M"
    QUATRO_A_SEIS_MESES = "4_6M"
    SETE_A_DOZE_MESES = "7_12M"
    NAO_SEI = "NAO_SEI"


class CERTEZA_RECURSO_EXTRAORDINARIO(Enum):
    """RF-39 · §13.3 · B3.05D — grau de certeza. Só `CONFIRMADO` satisfaz
    "confirmados, disponíveis e aptos no momento atual" (§13.3)."""

    CONFIRMADO = "CONFIRMADO"
    PROVAVEL = "PROVAVEL"
    POSSIVEL = "POSSIVEL"
```

### R3.4.3. Itens de patrimônio — `RF-38`, `RF-39`

**Decisão de nomenclatura, tomada por este plano.** A spec fixa forma e
domínio, deliberadamente **sem** fixar identificador de classe (§13 nomeia
variáveis, não estruturas). Estilo adotado, idêntico ao que já existe em
`engine/estado.py`: **PascalCase para a dataclass que agrupa**
(`Divida`, `Oportunidade`, `SinaisComportamentais`, `PerfilComportamental`),
**SCREAMING_CASE para enum de domínio fechado com nome normativo**
(`TIPO_DIVIDA`, `STATUS_DIVIDA`, `JANELA_NOVA_DIVIDA`), e **nome de campo
caractere por caractere como na §13** (`sdd.config.md` §7). Racional
completo e alternativas descartadas em R3.10.

```python
# engine/estado.py — RF-38 · §13.2, §13.3, §13.7
@dataclass(frozen=True, slots=True)
class ItemInvestimento:
    """RF-38 · §13.2 (`INVESTIMENTOS_LIQUIDOS_MOBILIZAVEIS`) · §13.3
    (`INVESTIMENTOS_RECOMENDADOS`) — UM investimento, nunca um total
    agregado (`AC-64`).

    Ficha repetível `B4.04A`–`B4.06B` da coleta (`[COND, REP]`). O valor
    líquido realizável chega JÁ APURADO (`OQ-27`, aberta — a fórmula de
    `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` não está publicada), e a
    classificação chega JÁ FEITA (`OQ-26`, aberta).
    """

    ITEM_ID: str  # identidade estável do item — origem econômica única (§13.8)
    VALOR_LIQUIDO_REALIZAVEL: Dinheiro
    POSSUI_LIQUIDEZ: bool  # §13.3: "com liquidez" é condição do recomendado
    CLASSIFICACAO_MOBILIZACAO: CLASSIFICACAO_MOBILIZACAO  # RF-40 · obrigatório (EC-31)


@dataclass(frozen=True, slots=True)
class ItemAtivo:
    """RF-38 · §13.2 · §13.3 (`Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`
    dos ativos `MOBILIZACAO_RECOMENDAVEL`) — UM ativo (ficha de imóvel
    `B4.I01`–`B4.I04A` e demais bens), nunca um total agregado (`AC-64`)."""

    ITEM_ID: str
    VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL: Dinheiro  # nome literal da §13.3
    CLASSIFICACAO_MOBILIZACAO: CLASSIFICACAO_MOBILIZACAO  # RF-40 · obrigatório (EC-31)


@dataclass(frozen=True, slots=True)
class RecursoExtraordinario:
    """RF-39 · §13.2 (`RECURSOS_EXTRAORDINARIOS_POTENCIAIS`) · §13.3
    (`EXTRAORDINARIOS_RECOMENDADOS`) — UM recebimento previsto
    (`B3.05A`–`B3.05D`, `[COND, REP]`).

    `AC-65`: os três campos abaixo bastam para decidir, POR ITEM e sem
    consultar nenhum outro campo, se o recurso é "confirmado, disponível e
    apto no momento atual" (§13.3):
      confirmado  = CERTEZA_RECURSO_EXTRAORDINARIO is CONFIRMADO
      momento atual = JANELA_RECURSO_EXTRAORDINARIO is ATE_30D
    """

    ITEM_ID: str
    VALOR_RECURSO_EXTRAORDINARIO: Dinheiro
    JANELA_RECURSO_EXTRAORDINARIO: JANELA_RECURSO_EXTRAORDINARIO
    CERTEZA_RECURSO_EXTRAORDINARIO: CERTEZA_RECURSO_EXTRAORDINARIO
```

> **`ITEM_ID` é campo deste plano, não da §13.** Justificativa contra
> requisito: `RF-52`/`AC-83` exigem que cada item componha **no máximo um**
> componente do recomendado, e a §13.8 exige "origem econômica única". Sem
> identidade por item, "este item apareceu em dois componentes" é
> inexprimível como asserção de teste. É o mínimo que satisfaz `RF-52` —
> não há campo adicional além dele.

### R3.4.4. `EstadoFinanceiro` estendido — `RF-36`, `RF-37`, `RF-38`, `RF-39`

```python
# engine/estado.py — EstadoFinanceiro, Rodada 3
@dataclass(frozen=True, slots=True)
class EstadoFinanceiro:
    # ... os 14 campos das Rodadas 1/2, INALTERADOS ...

    # --- Rodada 3 · reserva (RF-36 · §13.1) ---
    RESERVA_EXISTE: RESERVA_EXISTE                       # B4.02
    RESERVA_TOTAL: DinheiroTalvez                        # B4.02A · Regra 3
    DISPOSICAO_USO_RESERVA: DISPOSICAO_USO_RESERVA       # B4.03
    VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO: DinheiroTalvez  # B4.03A · RF-42

    # --- Rodada 3 · caixa (RF-37 · §13.2, §13.3 CAIXA_RECOMENDADO) ---
    DINHEIRO_DISPONIVEL: Dinheiro
    # ↑ SEMPRE presente, nunca DinheiroTalvez (AC-63). O enunciado de B4.01
    # já qualifica "que não esteja comprometido com as despesas normais": a
    # garantia é de COLETA e o motor NÃO revalida (`OQ-28`, encaminhada).
    # Valor comprometido não integra — quem exclui é a coleta, não o motor.

    # --- Rodada 3 · patrimônio por item (RF-38, RF-39) ---
    investimentos: tuple[ItemInvestimento, ...]
    ativos: tuple[ItemAtivo, ...]
    recursos_extraordinarios: tuple[RecursoExtraordinario, ...]
    # ↑ AC-64: NÃO existe, e não deve existir, nenhum campo escalar de total
    # agregado de investimentos ou de ativos em EstadoFinanceiro.
```

Nove campos novos, **numa leva só** (mitigação do risco de §8 da spec: o
`hash_inputs` muda uma vez, não nove). Campos de coleção em minúscula
(`investimentos`, `ativos`, `recursos_extraordinarios`) seguindo o
precedente literal de `EstadoFinanceiro.dividas` — a §13 não publica nome
de campo de coleção, só nome de variável derivada; `RF-38` cita `dividas`
como o padrão a seguir.

### R3.4.5. Contrato do módulo de cálculo — `RF-43` a `RF-48`, `RF-52`

```python
# engine/ataque_imediato.py — NOVO · RF-43..RF-52 · §13.1..§13.4, §13.7
"""Ataque imediato e reserva — §13 da spec do slug (documento canônico
PIQ v1.0.1, congelado em 2026-09-07).

TODA função deste módulo é PURA no sentido forte da NFR "Pureza (Rodada 3)":
recebe todas as entradas por parâmetro, não consulta `EstadoFinanceiro`,
não consulta `Diagnostico`, não lê relógio, arquivo nem variável global.
É essa propriedade — e não uma fórmula adivinhada — que torna `GAB-AI-01` a
`GAB-AI-07` verificáveis com `OQ-26` e `OQ-29` ainda abertas.

REGRAS: Final[tuple[str, ...]] = ("§13.1", "§13.2", "§13.3", "§13.4",
                                  "§13.7", "§13.8", "RF-43", ..., "RF-52")
"""

def derivar_RESERVA_MOBILIZAVEL(
    *,
    RESERVA_EXISTE: RESERVA_EXISTE,
    DISPOSICAO_USO_RESERVA: DISPOSICAO_USO_RESERVA,
    RESERVA_TOTAL: DinheiroTalvez,
    VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO: DinheiroTalvez,
) -> DinheiroTalvez:
    """RF-43 · §13.1 · §13.9 `deriveReservaMobilizavel`.

    As três regras da §13.1 aplicadas NA ORDEM REGISTRADA:
      Regra 1 vence Regra 2 (EC-23): RESERVA_EXISTE=NAO ou
              DISPOSICAO_USO_RESERVA=NAO -> dinheiro(0), ignorando o valor
              informado — nunca somando-o.
      Regra 3 vence Regra 2 (EC-25): RESERVA_TOTAL desconhecida ou
              VALOR_MAXIMO... desconhecido -> DESCONHECIDO.
      Regra 2: MIN(RESERVA_TOTAL, MAX(0, VALOR_MAXIMO...)) — o MAX(0, ...)
              zera valor negativo ANTES do MIN (EC-24).

    TRAVA CANÔNICA (§13.1, RF-49): NUNCA percentual automático de
    RESERVA_TOTAL. As três formas proibidas — 30% x, 50% x, e
    RESERVA_TOTAL - RESERVA_MINIMA_PADRAO — não existem em lugar nenhum
    deste módulo (AC-81, teste estático em R3.9).
    """


def calcular_ATAQUE_IMEDIATO_POTENCIAL(
    *,
    DINHEIRO_DISPONIVEL: Dinheiro,
    RESERVA_MOBILIZAVEL: DinheiroTalvez,
    investimentos: tuple[ItemInvestimento, ...],
    recursos_extraordinarios: tuple[RecursoExtraordinario, ...],
    ativos: tuple[ItemAtivo, ...],
) -> Dinheiro:
    """RF-44 · §13.2 — soma das cinco parcelas.

    Ativos: só os classificados MOBILIZACAO_POSSIVEL **ou**
    MOBILIZACAO_RECOMENDAVEL (AC-77). MOBILIZACAO_COM_RESSALVAS e
    NAO_MOBILIZAR NÃO entram nem aqui (EC-30).

    RESERVA_MOBILIZAVEL desconhecida contribui 0 para a soma — a §13.1 é
    explícita: "nenhum valor da reserva entra numericamente no recomendado
    ou aprovado até existir decisão válida". A pendência é registrada, não
    convertida em informação (ver R3.8).

    `ECONOMIA_POTENCIAL_IMEDIATA` NÃO entra nesta soma: `OQ-31` está aberta
    e a §13.2 não a menciona (spec §9).
    """


def calcular_CAIXA_RECOMENDADO(*, DINHEIRO_DISPONIVEL: Dinheiro) -> Dinheiro:
    """RF-45 · §13.3 — `CAIXA_RECOMENDADO = DINHEIRO_DISPONIVEL`.

    Identidade, não cálculo: a qualificação "realmente livre, não
    comprometido, não contado em outra variável" é garantia de COLETA
    (`RF-37`, `AC-63`, `OQ-28`). A função existe para dar nome normativo à
    parcela e para que a §13.7 (ordem de utilização) seja legível no
    código — não para revalidar nada.
    """


def calcular_INVESTIMENTOS_RECOMENDADOS(
    *, investimentos: tuple[ItemInvestimento, ...]
) -> Dinheiro:
    """RF-45 · §13.3 — soma do VALOR_LIQUIDO_REALIZAVEL dos investimentos
    COM liquidez E classificados MOBILIZACAO_RECOMENDAVEL.
    MOBILIZACAO_POSSIVEL fica só no potencial (AC-78)."""


def calcular_ATIVOS_RECOMENDADOS(*, ativos: tuple[ItemAtivo, ...]) -> Dinheiro:
    """RF-45 · §13.3 — Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL dos
    ativos MOBILIZACAO_RECOMENDAVEL. COM_RESSALVAS e NAO_MOBILIZAR não
    entram automaticamente (AC-78, EC-30)."""


def calcular_EXTRAORDINARIOS_RECOMENDADOS(
    *, recursos_extraordinarios: tuple[RecursoExtraordinario, ...]
) -> Dinheiro:
    """RF-45 · §13.3 — só CERTEZA=CONFIRMADO e JANELA=ATE_30D.
    Recurso apenas previsto para o futuro não compõe o recomendado atual
    (AC-79), ainda que componha RECURSOS_EXTRAORDINARIOS_POTENCIAIS."""


def calcular_NECESSIDADE_RESIDUAL(
    *,
    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL: Dinheiro,   # RF-48: POR PARÂMETRO
    CAIXA_RECOMENDADO: Dinheiro,
    INVESTIMENTOS_RECOMENDADOS: Dinheiro,
    EXTRAORDINARIOS_RECOMENDADOS: Dinheiro,
    ATIVOS_RECOMENDADOS: Dinheiro,
) -> Dinheiro:
    """RF-46 · §13.4 — MAX(0, elegível - os quatro não protetivos).
    EC-29: quando os não protetivos já cobrem a necessidade, resulta 0."""


def derivar_RESERVA_RECOMENDADA(
    *,
    RESERVA_MOBILIZAVEL: DinheiroTalvez,
    NECESSIDADE_RESIDUAL: Dinheiro,
    RESULTADO_MENSAL_ATUAL: Dinheiro,   # RF-48: POR PARÂMETRO, não de Diagnostico
) -> Dinheiro:
    """RF-46 · §13.4 · §13.9 `deriveReservaRecomendada` — a reserva é o
    ÚLTIMO componente (§13.7, ordem 5).

    TRAVA MODO_ESTABILIZACAO (§13.4): se RESULTADO_MENSAL_ATUAL < 0, então
    RESERVA_RECOMENDADA = 0 — a reserva não mascara déficit estrutural
    (AC-74). A trava é avaliada AQUI, sobre o valor recebido por parâmetro;
    `Diagnostico.MODO_ESTABILIZACAO` deriva da MESMA condição
    (`engine/diagnostico.py:486`) e é o campo que o teste de `AC-74` lê para
    confirmar `MODO_ESTABILIZACAO = SIM` — mas esta função não o consulta,
    porque consultá-lo quebraria a NFR de Pureza.

    RESERVA_MOBILIZAVEL desconhecida -> 0 "até decisão válida" (§13.9,
    EC-26) — e a pendência é registrada, nunca convertida silenciosamente em
    zero como informação (§13.1, ver R3.8).

    Nos demais casos: MIN(RESERVA_MOBILIZAVEL, NECESSIDADE_RESIDUAL).
    """


def calcular_ATAQUE_IMEDIATO_RECOMENDADO(
    *,
    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL: Dinheiro,   # RF-48: POR PARÂMETRO
    CAIXA_RECOMENDADO: Dinheiro,
    INVESTIMENTOS_RECOMENDADOS: Dinheiro,
    EXTRAORDINARIOS_RECOMENDADOS: Dinheiro,
    ATIVOS_RECOMENDADOS: Dinheiro,
    RESERVA_RECOMENDADA: Dinheiro,
) -> Dinheiro:
    """RF-47 · §13.3 · §13.9 `deriveAtaqueImediatoRecomendado` —
    MIN(elegível, soma dos cinco componentes recomendados).

    AC-76/GAB-AI-07: 10.000 elegível contra 25.000 de recursos dá 10.000.
    EC-28: elegível = 0 dá 0, mesmo com recursos positivos — a §13.5 proíbe
    recomendar recurso sem destinação financeira elegível.
    """


def verificar_hierarquia_ataque_imediato(
    *, ATAQUE_IMEDIATO_POTENCIAL: Dinheiro, ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro
) -> None:
    """RF-50 · §13.6 HIERARQUIA CANÔNICA — a parte verificável sem 3C:
    POTENCIAL >= RECOMENDADO >= 0. Tolerância ZERO (AC-82).

    Levanta `ErroInvariante` (mesmo padrão de `engine/ciclo_mensal.py:596`,
    A-04) — nunca corrige, nunca degrada silenciosamente. O ramo
    `>= ATAQUE_IMEDIATO_APROVADO >= 0` da §13.6 fica para 3C (`OQ-30`).
    """
```

**Assinaturas só com argumento nomeado (`*`).** Decisão deste plano, contra
requisito: `RF-48`/`AC-80` exigem que
`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` seja passada **explicitamente**
como argumento. Com seis parâmetros `Dinheiro` de mesmo tipo em
`calcular_ATAQUE_IMEDIATO_RECOMENDADO`, a passagem posicional tornaria uma
troca de ordem (ex.: elegível ↔ caixa) um erro silencioso que nenhum tipo
pega e que os `GAB-AI` só detectariam por sorte. É o mesmo raciocínio de
"chamada obrigatória e posicional" já usado na §11.10 da Rodada 1 para forçar
a ordem de derivação — aqui aplicado ao inverso, por segurança de nome.

### R3.4.6. `Diagnostico` — mudança de tipo — `RF-41`, `RF-51`

```python
# engine/diagnostico.py — Diagnostico (bloco da Rodada 2, RF-35)
    # --- Rodada 2 (RF-35) · Rodada 3 (RF-41: mudança de TIPO) ---
    RESERVA_MOBILIZAVEL: DinheiroTalvez   # era Dinheiro (R2) — §13.1 Regra 3
    ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro # inalterado: sempre numérico (§13.3)
```

`ATAQUE_IMEDIATO_RECOMENDADO` **continua `Dinheiro`**, e isso é decisão
justificada, não omissão: a §13.3 é um `MIN` de somas em que a parcela
desconhecida da reserva contribui `0` (§13.9 `deriveReservaRecomendada`
devolve `0`, não `DESCONHECIDA`). Não existe caminho da §13 em que
`ATAQUE_IMEDIATO_RECOMENDADO` seja desconhecido — `AC-73` exige apenas que
**nenhum valor da reserva entre nele**, o que é satisfeito com
`RESERVA_RECOMENDADA = 0`.

```python
# engine/diagnostico.py::calcular_diagnostico — RF-51 · AC-85, AC-86
# ANTES (T-90, a substituir):
#     RESERVA_MOBILIZAVEL=dinheiro(0),          # :764
#     ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(0),  # :765
# DEPOIS: as duas chamadas reais de engine/ataque_imediato.py, com
# NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL vindo por parâmetro.
```

> **Ambiguidade técnica nova, registrada e não decidida aqui — `AMB-R3-01`.**
> `RF-51` manda substituir o placeholder de `ATAQUE_IMEDIATO_RECOMENDADO`
> pelo cálculo de `RF-47`, mas `RF-48`/`AC-80` proíbem que
> `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` seja buscada em
> `EstadoFinanceiro` ou em `Diagnostico` — e `calcular_diagnostico(estado,
> parametros)` só tem esses dois insumos. Ver R3.10.1: a questão é **de onde
> `calcular_diagnostico` obtém esse argumento**, e ela não se resolve neste
> plano.

## R3.5. Data Flow

Não altera a numeração dos 11 passos da §5 (Rodada 1). Acrescenta um
sub-fluxo **antes** do passo 1 (contrato de entrada) e **dentro** do passo 1
(diagnóstico).

**3A — entrada:**

1. O montador de estado de `app-aluno` (`OQ-37`, fora deste slug) lê as
   respostas dos Blocos 3 e 4 e constrói `EstadoFinanceiro` com os nove
   campos novos. **Falha aqui:** campo obrigatório ausente é `TypeError` na
   construção da dataclass — `frozen=True` não admite preenchimento
   posterior. `EC-31` (item sem classificação) cai exatamente neste ramo: a
   classificação é campo obrigatório de `ItemInvestimento`/`ItemAtivo`, sem
   default, porque derivá-la está fora de escopo (`OQ-26`) e o motor não
   escolhe classe por omissão.
2. `_recusar_float` (`engine/estado.py:256`) já percorre os campos da
   dataclass e recusa `float` nomeando o campo culpado — vale
   automaticamente para os campos monetários novos, sem código adicional.
   **Nota de implementação:** `_recusar_float` percorre os campos do objeto,
   não os itens de uma `tuple` aninhada; `ItemInvestimento`, `ItemAtivo` e
   `RecursoExtraordinario` precisam chamar `_recusar_float(self)` no próprio
   `__post_init__`, como `Divida` já faz (`:296-297`).

**3B — cálculo, na ordem de precedência da §13.7:**

```text
                DINHEIRO_DISPONIVEL ──────────────► CAIXA_RECOMENDADO        (ordem 1)
        investimentos[] ─ liquidez + RECOMENDAVEL ► INVESTIMENTOS_RECOMENDADOS(ordem 2)
 recursos_extraordinarios[] ─ CONFIRMADO+ATE_30D ─► EXTRAORDINARIOS_RECOMENDADOS(ordem 3)
              ativos[] ─ só RECOMENDAVEL ────────► ATIVOS_RECOMENDADOS       (ordem 4)
                                                          │
   NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL ──────────────┤ (RF-48, parâmetro)
                                                          ▼
                                             NECESSIDADE_RESIDUAL  (§13.4)
                                                          │
  RESERVA_EXISTE ┐                                        │
  DISPOSICAO_USO_RESERVA ├─► RESERVA_MOBILIZAVEL ─────────┤
  RESERVA_TOTAL          │        (§13.1)                 │
  VALOR_MAXIMO_...       ┘                                ▼
                          RESULTADO_MENSAL_ATUAL ──► RESERVA_RECOMENDADA     (ordem 5)
                                (< 0 ⇒ 0, trava)             │
                                                             ▼
                            MIN(elegível, Σ dos cinco) ► ATAQUE_IMEDIATO_RECOMENDADO
                                                             │
                     verificar_hierarquia(POTENCIAL, RECOMENDADO)  ← RF-50
```

**Falhas em cada etapa:**

| Etapa | Falha possível | Comportamento |
| --- | --- | --- |
| `derivar_RESERVA_MOBILIZAVEL` | entrada inconsistente (`RESERVA_EXISTE=NAO` com valor informado, `EC-23`) | Regra 1 vence: `0`. Não é erro — é a ordem normativa |
| `derivar_RESERVA_MOBILIZAVEL` | total ou valor máximo desconhecido | devolve `DESCONHECIDO`, nunca `0` (`AC-73`) |
| `derivar_RESERVA_RECOMENDADA` | `RESERVA_MOBILIZAVEL` desconhecida | `0` **e pendência registrada** (R3.8), nunca conversão silenciosa |
| `calcular_*_RECOMENDADOS` | coleções vazias (`EC-27`) | `0`. Nenhum erro, nenhum desconhecido fabricado |
| `calcular_ATAQUE_IMEDIATO_RECOMENDADO` | elegível `= 0` com recursos positivos (`EC-28`) | `0` (§13.5) |
| `verificar_hierarquia_ataque_imediato` | `POTENCIAL < RECOMENDADO` | `ErroInvariante` — bug do motor, nunca dado do usuário |

**Dupla contagem (`RF-52`, §13.8) — onde cada caso vedado é prevenido:**

| Caso vedado (§13.8) | Prevenido em | Verificado por |
| --- | --- | --- |
| Reserva em CDB contada como reserva **e** investimento | **Coleta**: `B4.04` pergunta "além dos valores que você já informou como reserva" (`bloco-04.yaml:169-170`) | `AC-84` — teste lê o enunciado do registro |
| Dinheiro comprometido contado como `DINHEIRO_DISPONIVEL` | **Coleta**: `B4.01` já qualifica (`RF-37`, `OQ-28`) | `AC-63` |
| Venda de ativo contada como ativo **e** como dinheiro | **Modelagem**: cada item tem `ITEM_ID` e uma única categoria; `CAIXA_RECOMENDADO` é escalar de outra origem | `AC-83` |
| Item em dois componentes do recomendado | **Modelagem**: `ItemInvestimento` só alimenta `INVESTIMENTOS_RECOMENDADOS`, `ItemAtivo` só `ATIVOS_RECOMENDADOS` — são tipos distintos, um item não pode estar nas duas coleções | `AC-83` |
| Extraordinário como aprovado **e** como evento independente | **fora de escopo** — depende de `ATAQUE_IMEDIATO_APROVADO` (3C) | — (`OQ-33`, parcial) |

## R3.6. External Interfaces

Nenhuma interface externa nova; o motor continua sem chamada de rede
(inalterado da §6, Rodada 1). Duas **fronteiras internas** merecem registro:

| Fronteira | Contrato | Quem preenche | Falha → |
| --- | --- | --- | --- |
| `app-aluno` → `EstadoFinanceiro` (9 campos novos) | R3.4.4 | montador de `app/montagem/estado.py` (`OQ-37`, slug `app-aluno`) | `TypeError` na construção — argumento obrigatório ausente. Visível no `build` (`mypy --strict`) antes de runtime |
| `persistencia/arquivo` ↔ `SnapshotOrdem` | round-trip exato de `Decimal` e de `DESCONHECIDO` (`_dinheiro_talvez`, `:236-239`, já existente) | este slug (R3.3) | Se `_estado_financeiro`/`_diagnostico` não forem atualizados, `KeyError` no round-trip — pego pelos testes de `tests/integracao/test_repositorio_snapshots.py` |

`_serializar_canonico` (`engine/snapshot.py:136`) **não muda**: já trata
`dataclass` genericamente (dict ordenado por nome de campo), `tuple` como
sequência ordenada e `Enum` (inclusive `Desconhecido`) por `.value`. As três
coleções e o novo enum serializam sem nenhuma linha nova — mas o `hash_inputs`
resultante muda para todo snapshot, por construção (ver R3.10).

## R3.7. State Management

Nenhuma mudança na tabela de estado da §7 (Rodada 1). Quatro afirmações que
esta rodada precisa deixar explícitas:

- **Todo o estado novo é de entrada, imutável, e vive em
  `EstadoFinanceiro`.** `frozen=True, slots=True` nos três tipos de item e
  nas coleções `tuple[...]`: nada é mutado depois de montado (`V-01`).
- **Nenhum valor derivado da §13 vira estado.** As nove funções de
  `engine/ataque_imediato.py` são puras e recalculadas a cada chamada; nada
  é memoizado, persistido entre chamadas ou lido de global. É essa
  propriedade que faz a NFR de determinismo continuar valendo sem nenhuma
  verificação nova.
- **A classificação de mobilização é dado, nunca estado derivado.** Ela
  **entra** por item e sai igual. Não há cache, não há função de derivação,
  não há default (`AC-67`, `OQ-26`).
- **`ATAQUE_IMEDIATO_APROVADO` não existe nesta rodada** — nem como campo,
  nem como parâmetro, nem como `None`. Introduzi-lo agora criaria estado
  cujo dono (`OQ-30`) e cujo momento de aplicação (`OQ-35`) não estão
  decididos.

## R3.8. Error Handling Strategy

| Situação | Detecção | Resposta do motor | Recuperação |
| --- | --- | --- | --- |
| `RESERVA_MOBILIZAVEL` desconhecida (`GAB-AI-04`, `EC-26`) | `derivar_RESERVA_MOBILIZAVEL` devolve `DESCONHECIDO` | `RESERVA_RECOMENDADA = 0` e o `Diagnostico` carrega `RESERVA_MOBILIZAVEL = DESCONHECIDO` — a pendência fica **legível na saída**, não é apagada. É o que a §13.1 quer dizer com "a engine registra a pendência" | `AC-73`, `EC-26`. Reabrir `B4.03A` é da camada de coleta (`OQ-25`), não do motor |
| Entrada inconsistente: `RESERVA_EXISTE=NAO` com valor informado (`EC-23`) | ordem das regras da §13.1 | `0` — Regra 1 vence, valor informado ignorado. **Não é erro**, é a norma | `AC-72` |
| `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` negativo (`EC-24`) | `MAX(0, ...)` da Regra 2 | parcela zerada antes do `MIN`; resultado nunca negativo | `EC-24` |
| Coleções vazias e `DINHEIRO_DISPONIVEL = 0` (`EC-27`) | soma de coleção vazia | `0` em potencial e recomendado. Nenhum erro, nenhum desconhecido fabricado | `EC-27` |
| Item chega sem classificação (`EC-31`) | construção da dataclass — campo obrigatório, sem default | `TypeError` na construção de `ItemInvestimento`/`ItemAtivo` | `EC-31`. O motor **não escolhe** classe por omissão (`OQ-26`) |
| `float` em campo monetário novo | `_recusar_float` no `__post_init__` de cada item | `TypeError` nomeando o campo culpado | Padrão já existente (`engine/estado.py:256`) |
| Consumidor interno lê `Diagnostico.RESERVA_MOBILIZAVEL` como `Dinheiro` puro | `mypy --strict` (comando `build`) | Falha de tipagem **antes** de runtime | `AC-68`. Ver R3.10.2 para a lista completa de consumidores |
| `POTENCIAL < RECOMENDADO` (§13.6 violada) | `verificar_hierarquia_ataque_imediato` | `ErroInvariante` (padrão `A-04`, `engine/ciclo_mensal.py:596`) | `AC-82`. É bug do motor, não dado ruim — nunca degradar |

**Regra herdada, reafirmada.** Nenhuma degradação silenciosa (§8, Rodada 1):
`DESCONHECIDO` nunca vira `0` **como informação**; ele vira `0` apenas como
*contribuição aritmética* para uma soma, e essa distinção fica visível no
`Diagnostico`, que carrega o `DESCONHECIDO` original.

## R3.9. Testing Strategy

### R3.9.1. Onde vivem os `GAB-AI` — decisão deste plano

**Decisão: diretório novo `tests/gabaritos_ataque_imediato/`, marcador novo
`gabarito_ataque_imediato`, registrado em `pyproject.toml`.**

Conferido no repositório antes de decidir:

- `tests/gabaritos/` — `GAB-A`/`GAB-B`/`GAB-C`, marcador `@pytest.mark.gabarito`
  (`test_gabarito_a_deficit.py:40`), carregam `EstadoFinanceiro` **inteiro** de
  fixture JSON (`tests/fixtures/gab_*.json`) e verificam a saída do motor
  completo. O marcador está descrito no `pyproject.toml` como *"reproduz
  gabarito numérico **ponta a ponta** (GAB-A, GAB-B, GAB-C — seção 10 da
  canônica)"*.
- `tests/invariantes/` — `GAB-01`..`GAB-05`, marcador `@pytest.mark.invariante`
  (`test_gab01_seguro.py:135`), descrito como *"prova invariante GAB-01 a
  GAB-05"*.

`GAB-AI-01` a `GAB-AI-07` não são nenhum dos dois: são casos numéricos
pontuais (não propriedades, logo não `invariante`) sobre **uma fórmula
isolada com 3 a 6 entradas dadas no enunciado** (não ponta a ponta, sem
dívidas, sem gates, sem cronograma, logo não `gabarito`). Reusar
`@pytest.mark.gabarito` faria `pytest -m "gabarito or invariante"` — o
comando de homologação em uso — passar a incluir sete testes que **não são**
ponta a ponta, tornando a descrição do marcador no `pyproject.toml` falsa e
diluindo o significado do portão de homologação da seção 10 da canônica.

Consequências operacionais, explícitas para `/sdd:tasks`:

- O comando de homologação passa a ser
  `pytest -m "gabarito or invariante or gabarito_ataque_imediato"`.
- Os `GAB-AI` continuam sendo coletados por `pytest -q` (a suíte padrão), como
  os demais — o marcador **seleciona**, não exclui.
- `GAB-AI-08` **não** é escrito nesta rodada (spec §4): depende de
  `ATAQUE_IMEDIATO_APROVADO` (3C). Quando existir, ele **sim** é ponta a
  ponta e vai para `tests/gabaritos/` com `@pytest.mark.gabarito` — a família
  se divide por natureza, não por prefixo de nome, e isso é deliberado.

### R3.9.2. Os sete `GAB-AI` — tolerância zero

Um arquivo por variável derivada, dentro de
`tests/gabaritos_ataque_imediato/`:

| Teste | Gabarito | Âncora | Entradas (do enunciado da §13.10) |
| --- | --- | --- | --- |
| `test_gab_ai_01_valor_aceito_abaixo_do_total` | `GAB-AI-01` | `AC-70` | total `20.000`, aceita `5.000` → `5.000` |
| `test_gab_ai_02_limitado_pelo_total` | `GAB-AI-02` | `AC-71` | total `20.000`, informa `30.000` → `20.000` |
| `test_gab_ai_03_sem_disposicao_de_uso` | `GAB-AI-03` | `AC-72` | `DISPOSICAO_USO_RESERVA = NAO` → `0` |
| `test_gab_ai_04_decidir_depois_e_desconhecido` | `GAB-AI-04` | `AC-73` | "prefiro decidir depois" → `DESCONHECIDO`, e reserva **não entra** em `RESERVA_RECOMENDADA` nem em `ATAQUE_IMEDIATO_RECOMENDADO` |
| `test_gab_ai_05_modo_estabilizacao_zera_reserva` | `GAB-AI-05` | `AC-74` | `RESULTADO_MENSAL_ATUAL = -1.000`, mobilizável `20.000` → `MODO_ESTABILIZACAO = SIM`, recomendada `0` |
| `test_gab_ai_06_residual_e_recomendado_completo` | `GAB-AI-06` | `AC-75` | elegível `20.000` (**por parâmetro**), caixa `5.000`, invest. `7.000`, extra `0`, ativos `0`, mobilizável `10.000` → residual `8.000`, reserva rec. `8.000`, recomendado `20.000` |
| `test_gab_ai_07_teto_da_necessidade_elegivel` | `GAB-AI-07` | `AC-76` | elegível `10.000` (**por parâmetro**), recursos `25.000` → `10.000`, nunca `25.000` |

**Tolerância zero, obrigatoriamente com `assertar_exato`** (`tests/conftest.py:36`).
`assertar_monetario` (± R$ 0,05) é **proibido** nestes sete: são
`MIN`/`MAX`/soma sem acumulação de arredondamento (spec §5, `OQ-34`
respondida). Nota para quem implementar: `tests/estatica/test_uso_de_tolerancia.py`
faz lint por **nome de identificador** contra uma lista fechada de símbolos
de tolerância zero — os nomes desta rodada (`RESERVA_MOBILIZAVEL`,
`ATAQUE_IMEDIATO_RECOMENDADO`, `NECESSIDADE_RESIDUAL`) **não** estão nessa
lista, então o lint atual não impediria o uso errado. Acrescentar esses três
símbolos à lista de `SIMBOLOS_TOLERANCIA_ZERO` é trabalho desta rodada
(`RF-49`/`AC-82` dependem da régua certa) e cabe numa tarefa de R3.3
(`tests/estatica/`).

### R3.9.3. Unitários de regra — `tests/regras/test_ataque_imediato.py`

| Teste | Âncora |
| --- | --- |
| `test_potencial_soma_apenas_possivel_e_recomendavel` | `AC-77` |
| `test_ativo_possivel_fica_so_no_potencial` | `AC-78` |
| `test_extraordinario_futuro_nao_compoe_recomendado` | `AC-79` |
| `test_elegivel_entra_por_argumento_explicito` | `AC-80` |
| `test_hierarquia_potencial_maior_ou_igual_recomendado` | `AC-82`, `RF-50` |
| `test_item_compoe_no_maximo_um_componente` | `AC-83`, `RF-52` |
| `test_reserva_existe_nao_vence_valor_informado` | `EC-23` |
| `test_valor_maximo_negativo_zera_antes_do_min` | `EC-24` |
| `test_reserva_total_desconhecida_vence_regra_2` | `EC-25` |
| `test_mobilizavel_desconhecida_com_residual_positivo` | `EC-26` |
| `test_colecoes_vazias_resultam_zero` | `EC-27` |
| `test_elegivel_zero_com_recursos_positivos` | `EC-28` |
| `test_nao_protetivos_cobrem_tudo_residual_zero` | `EC-29` |
| `test_com_ressalvas_nao_entra_em_potencial_nem_recomendado` | `EC-30` |
| `test_item_sem_classificacao_falha_na_construcao` | `EC-31` |

### R3.9.4. Contrato de estado — `AC-62` a `AC-66`, `AC-69`

| Teste | Âncora |
| --- | --- |
| `test_estado_tem_os_quatro_campos_de_reserva_com_nome_literal` | `AC-62` |
| `test_dinheiro_disponivel_sempre_presente_sem_revalidacao` | `AC-63` |
| `test_investimentos_e_ativos_sao_colecao_por_item_sem_total_agregado` | `AC-64` |
| `test_recurso_extraordinario_decidivel_por_item` | `AC-65` |
| `test_classificacao_mobilizacao_tem_exatamente_quatro_membros` | `AC-66` |
| `test_bloco04_b4_03a_grava_valor_maximo_informado` (lê o YAML) | `AC-69`, `RF-42` |
| `test_b4_04_continua_excluindo_valores_de_reserva` (lê o YAML) | `AC-84` |

### R3.9.5. Testes estáticos novos — `tests/estatica/`

- `test_sem_percentual_automatico_de_reserva` (`AC-81`, `RF-49`): varre a AST
  de `engine/**/*.py` procurando qualquer `BinOp` de multiplicação ou
  subtração que tenha `RESERVA_TOTAL` como operando e produza
  `RESERVA_MOBILIZAVEL` — as três formas proibidas da §13.1. Falha nomeando
  arquivo e linha. Mesmo padrão de lint por AST já usado em
  `test_uso_de_tolerancia.py` e `test_nenhum_parametro_no_codigo.py`.
- `test_sem_derivacao_de_classificacao_mobilizacao` (`AC-67`, `RF-40`): falha
  se alguma função de `engine/` **retornar** `CLASSIFICACAO_MOBILIZACAO`
  (anotação de retorno) — a classificação entra como dado, nunca é produzida.
  Enquanto `OQ-26` estiver aberta, este teste é o portão que impede a
  metodologia de ser decidida no código.

### R3.9.6. Não-regressão obrigatória — `AC-87`

`RF-41` (mudança de tipo) e `RF-51` (substituição do placeholder) tocam
`Diagnostico`, que entra em `SnapshotOrdem`. Procedimento **obrigatório**,
no mesmo rigor da R2.9:

1. Rodar `pytest -q` **antes** de qualquer mudança e guardar a saída.
2. Implementar 3A inteira (os nove campos de uma vez), corrigir os 13
   arquivos da R3.10.2 e rodar de novo. Toda divergência aqui é
   **mecânica** (argumento faltante), nunca numérica: se algum número mudar
   nesta etapa, a modelagem está errada.
3. Implementar 3B, rodar de novo. `GAB-A`/`GAB-B`/`GAB-C` e `GAB-01`..`GAB-05`
   **devem continuar idênticos** (`AC-87`), com as mesmas tolerâncias da
   seção 5. Nas fixtures atuais, reserva ausente e coleções vazias ⇒
   `RESERVA_MOBILIZAVEL = 0`, `ATAQUE_IMEDIATO_RECOMENDADO = 0`, exatamente
   os valores que o placeholder produzia. **Se algum gabarito mudar, é
   regressão, não expectativa nova** — o oposto da Rodada 2, onde a mudança
   de `ORDEM_ACOES` era esperada.
4. Nenhum arquivo de `engine/ciclo_mensal.py` aparece em nenhuma etapa. Se
   aparecer, a fatia 3C vazou para dentro desta rodada.

- **E2E:** inalterado — não se aplica a este slug.
- **Fora de teste automatizado:** a derivação real de
  `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (`OQ-29`), a regra de
  classificação (`OQ-26`), a fórmula de
  `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` (`OQ-27`) e `GAB-AI-08`
  (`OQ-30`/`OQ-32`/`OQ-35`). Não são testáveis porque não existem — e não
  devem ser adivinhadas para virarem testáveis.

## R3.10. Risks & Trade-offs

| Decisão | Alternativa descartada | Por quê | Risco assumido |
| --- | --- | --- | --- |
| `ItemInvestimento` / `ItemAtivo` / `RecursoExtraordinario` (PascalCase) + `CLASSIFICACAO_MOBILIZACAO` (SCREAMING_CASE) | `Investimento`/`Ativo` secos; `Ativo`/`Investimento` num único tipo `ItemPatrimonial` com campo `categoria`; `MobilizacaoClassificacao` em PascalCase | O prefixo `Item` marca "uma unidade da coleção", que é exatamente o que `RF-38`/`AC-64` exigem e o que `AC-64` proíbe confundir com total agregado; `Ativo` seco colidiria conceitualmente com `ATIVOS_TOTAIS`/`PATRIMONIO_LIQUIDO` da canônica, que são agregados. Um tipo único com `categoria` foi descartado porque tornaria `AC-83` (item em no máximo um componente) dependente de um campo em runtime em vez de do sistema de tipos. `CLASSIFICACAO_MOBILIZACAO` em SCREAMING_CASE segue `TIPO_DIVIDA`/`STATUS_DIVIDA`/`JANELA_NOVA_DIVIDA`, o padrão do arquivo para enum de domínio normativo | Os nomes de **classe** não constam da §13 — se o especialista publicar nomes canônicos para essas estruturas (plausível junto com `OQ-26`/`OQ-27`), haverá rename. Mitigado: os nomes de **campo** são literais da §13 e não mudam; o rename de classe é mecânico e pego pelo `mypy` |
| `tests/gabaritos_ataque_imediato/` + marcador `gabarito_ataque_imediato` | Reusar `tests/gabaritos/` + `@pytest.mark.gabarito`; reusar `tests/invariantes/`; pôr tudo em `tests/regras/` sem marcador | Ver R3.9.1. `gabarito` está descrito no `pyproject.toml` como "ponta a ponta"; sete dos oito `GAB-AI` não são. `invariante` é para propriedade, não para caso numérico. `tests/regras/` sem marcador perderia a distinção "gabarito de homologação" vs. "teste de regra", que a seção 10 da canônica trata como portão de aprovação | O comando de homologação muda (`pytest -m "gabarito or invariante or gabarito_ataque_imediato"`). Quem rodar o comando antigo terá cobertura silenciosamente menor. Mitigado: o comando novo deve ser registrado na tarefa e no `sdd.config.md` §2 se e quando o `e2e`/`run` forem preenchidos |
| Nove campos de `EstadoFinanceiro` numa leva só | Adicionar em três levas (reserva; caixa; coleções) | `hash_inputs` (`engine/snapshot.py:119-120`) muda a cada campo adicionado — três levas significam três invalidações do hash congelado de `app-aluno` e três coordenações. Mitigação explícita do risco de §8 da spec | Um único commit grande, com 13 arquivos de teste tocados por argumento faltante. Mitigado: a divergência é mecânica (`TypeError`/`mypy`), nunca numérica — `AC-87` prova |
| `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` por parâmetro, nunca derivada | Derivar como `Σ VALOR_RELEVANTE_PARA_QUITACAO` das elegíveis pós-gate | `OQ-29` aberta; a §13.5 só define em prosa; a discovery mostra **duas** leituras plausíveis com números muito diferentes, e a diferença cai direto no valor recomendado ao usuário sob tolerância zero. `sdd.config.md` §6: metodologia não se decide implementando | `calcular_diagnostico` não tem de onde tirar esse argumento hoje — ver `AMB-R3-01` em R3.10.1. É o principal ponto que exige confirmação humana antes de `/sdd:tasks` |
| `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` continua `Dinheiro` | Retipar também para `DinheiroTalvez`, "por simetria" com `RESERVA_MOBILIZAVEL` | A §13.9 devolve `0` (não `DESCONHECIDA`) quando a reserva é desconhecida; não existe caminho da §13 que torne o recomendado desconhecido. Retipar seria inventar um estado que a norma não tem, e ampliaria a quebra de contrato sem requisito que a peça | Se `OQ-29` for respondida com uma fórmula que admita "elegível desconhecida", este campo precisará ser retipado numa rodada futura — uma segunda quebra de contrato. Aceito: inventar agora é pior |
| `ITEM_ID` em cada item de patrimônio | Nenhum identificador; posição na tupla como identidade | `RF-52`/`AC-83` exigem afirmar "este item compôs no máximo um componente"; posição em tupla não sobrevive a filtro nem a serialização e não é auditável por um revisor humano (NFR de auditabilidade) | Campo que a §13 não pede. Justificado contra `RF-52`; se o especialista publicar identidade própria para itens, o campo é substituído, não somado |
| `verificar_hierarquia_ataque_imediato` como função separada, chamada explicitamente | Invariante embutido dentro de `calcular_ATAQUE_IMEDIATO_RECOMENDADO` | Embutir obrigaria a função a receber também `ATAQUE_IMEDIATO_POTENCIAL`, que não é insumo da fórmula da §13.3 — poluiria a assinatura de uma fórmula normativa com um argumento que ela não usa | O invariante só roda se alguém chamar. Mitigado: `AC-82` é teste dedicado, e `calcular_diagnostico` (`RF-51`) chama as duas funções e pode chamar a verificação no mesmo ponto |

### R3.10.1. Ambiguidades — o que NÃO se decide aqui

**Ambiguidade técnica nova, levantada por este plano.** Registrada, não
decidida (`sdd.config.md` §3, `CLAUDE.md` regra 3).

| ID | Ambiguidade | Onde aparece | Encaminhamento |
| --- | --- | --- | --- |
| `AMB-R3-01` | **De onde `calcular_diagnostico` obtém `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`?** `RF-51`/`AC-85` exigem que `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` carregue o valor derivado por `RF-47`; `RF-47` exige o elegível; `RF-48`/`AC-80` proíbem buscá-lo em `EstadoFinanceiro` ou `Diagnostico`; e `calcular_diagnostico(estado, parametros)` só recebe esses dois. Saídas possíveis: (a) parâmetro novo na assinatura pública; (b) `dinheiro(0)` no campo enquanto `OQ-29` estiver aberta; (c) campo em `EstadoFinanceiro` | R3.4.6, R3.4.5 | **RESOLVIDA (usuário, 2026-09-07) — opção (b).** `calcular_diagnostico` **mantém** a assinatura `(estado, parametros)`; `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` **segue com `dinheiro(0)`** enquanto `OQ-29` não for respondida. `Diagnostico.RESERVA_MOBILIZAVEL`, que **não** depende do elegível, passa a receber o valor real de `RF-43` normalmente. **Razão:** (a) quebraria o contrato do ponto de entrada do motor e obrigaria a atualizar ~22 chamadas de `calcular_diagnostico` (`engine/motor.py:241`, gabaritos, testes) por uma variável cuja fórmula ninguém sabe calcular ainda — risco alto por benefício nenhum hoje; (c) violaria `AC-80` e fingiria que um valor derivado é dado coletado. As nove funções puras de `RF-43`–`RF-48` ficam implementadas e testadas de qualquer forma, e os 7 `GAB-AI` cobertos passam recebendo o elegível por parâmetro — que é o que torna a fatia 3B verificável sem o especialista. **Consequência a registrar nas tarefas:** `AC-85` fica **parcialmente satisfeito** nesta rodada (cumprido para `RESERVA_MOBILIZAVEL`, pendente para `ATAQUE_IMEDIATO_RECOMENDADO`); a tarefa de `RF-51` deve documentar isso no código, citando `OQ-29`, no mesmo padrão que `T-90` usou para `OQ-23`. Quando `OQ-29` for respondida, a derivação real alimenta o mesmo ponto — nenhuma das funções puras precisa mudar |

**Questões que exigem o especialista do método — não se resolvem neste
plano, e nada aqui as antecipa** (spec §10, Rodada 3):

| ID | O que fica bloqueado | O que este plano fez em vez de adivinhar |
| --- | --- | --- |
| `OQ-26` | regra de derivação da classificação de mobilização | Entrega o **enum** (`RF-40`) e recebe a classificação por item; teste estático proíbe qualquer função que a derive (`AC-67`) |
| `OQ-27` | fórmula de `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` | O valor chega **já apurado** por item (`ItemAtivo`) |
| `OQ-29` | fórmula de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` | Entra **por parâmetro** (`RF-48`); ver `AMB-R3-01` |
| `OQ-30`, `OQ-32`, `OQ-35` | fatia 3C inteira, `GAB-AI-08` | Nada de `ATAQUE_IMEDIATO_APROVADO`; nada em `engine/ciclo_mensal.py` |
| `OQ-31` | relação `ECONOMIA_POTENCIAL_IMEDIATA` × `ATAQUE_IMEDIATO_POTENCIAL` | Não incluída na soma da §13.2; nenhuma capacidade alterada |
| `OQ-25` | distinção fina "decidir depois" × "não sei" | Colapsadas em `DESCONHECIDO` **só na aritmética** (é o que a §13.1 Regra 3 manda); os enums `RESERVA_EXISTE`/`DISPOSICAO_USO_RESERVA` preservam os estados de coleta |
| `OQ-28` | quem valida "livre / não comprometido" | Encaminhada como **garantia de coleta** (`RF-37`, `AC-63`); se o especialista decidir que cabe validação no motor, é acréscimo, não reescrita |
| `OQ-33` | onde vivem as travas da §13.8 | Híbrido no que é verificável sem 3C: origem única por modelagem (`AC-83`) + não-relançamento na coleta (`AC-84`) |

### R3.10.2. `RF-41` — varredura completa de consumidores

**Lição aprendida da Rodada 2, aplicada aqui:** o campo "Arquivos" da tarefa
precisa listar **todos** os consumidores, não só os de `engine/` — senão a
correção fica órfã. Lista abaixo levantada por `grep` nesta rodada de
planejamento; `/sdd:tasks` deve transcrevê-la inteira.

**Consumidores de `Diagnostico.RESERVA_MOBILIZAVEL` (muda de `Dinheiro` para
`DinheiroTalvez` — quebra de contrato, `RF-41`):**

| Arquivo | Linha | O que muda |
| --- | --- | --- |
| `engine/diagnostico.py` | `:637` (declaração), `:764` (construção) | tipo do campo + valor real (`RF-51`) |
| `persistencia/arquivo/repositorio_snapshots.py` | `:400` | `_decimal(...)` → `_dinheiro_talvez(...)` (helper já existe, `:236`) |
| `tests/regras/test_troca.py` | `:91` | construção de `Diagnostico` de fixture |
| `tests/regras/test_simular_cenario.py` | `:135` | idem |
| `tests/regras/test_R.py` | `:128` | idem |
| `tests/regras/test_M.py` | `:121` | idem |
| `tests/regras/test_hibrido.py` | `:166` | idem |
| `tests/regras/test_H.py` | `:152` | idem |
| `tests/regras/test_F.py` | `:117` | idem |
| `tests/regras/test_bola_de_neve.py` | `:441` | idem |
| `tests/regras/test_avalanche.py` | `:271` | idem |
| `tests/regras/test_A.py` | `:111` | idem |
| `tests/invariantes/test_propriedades.py` | `:226` | idem |
| `tests/invariantes/test_gab05_troca.py` | `:104` | idem |

**Consumidores de `EstadoFinanceiro` (nove campos novos, `RF-36`–`RF-39`) —
todo ponto de construção:**

`persistencia/arquivo/repositorio_snapshots.py:331` ·
`tests/fixtures/carregar.py:174` (+ os três JSON de `tests/fixtures/`) ·
`tests/regras/test_troca.py` · `test_simular_cenario.py` · `test_hibrido.py` ·
`test_bola_de_neve.py` · `test_avalanche.py` · `test_R.py` · `test_M.py` ·
`test_H.py` · `test_F.py` · `test_A.py` · `test_diagnostico.py` ·
`tests/invariantes/test_propriedades.py` · `test_gab05_troca.py` ·
`test_gab03_rotativo.py` · `test_gab01_seguro.py` · `test_gab02_inventario.py` ·
`test_gab04_estabilizacao.py` · `tests/desempenho/test_orcamento_30_dividas.py` ·
`tests/app_aluno/test_plano_ec07_ec08_ec09.py` ·
`tests/app_aluno/test_conversao_decimal.py`.

**Fora deste slug, a sinalizar (não editar):** `app/montagem/estado.py:1326`
(`OQ-37`, slug `app-aluno`) e
`tests/app_aluno/estatica/hashes_congelados.json` (`AC-44` de `app-aluno`),
que desta vez cobre **cinco** arquivos alterados: `engine/tipos.py`,
`engine/estado.py`, `engine/diagnostico.py`, `engine/ataque_imediato.py`
(novo) e `persistencia/arquivo/repositorio_snapshots.py`.

**Mecanismo de rede.** `mypy --strict` (comando `build`, `sdd.config.md` §2)
roda **depois** do retipo e acusa todo consumidor que trate apenas o ramo
`Dinheiro` sem cobrir `Desconhecido` — mesma exaustividade já garantida para
`SALDO_DEVEDOR_ATUAL`/`VALOR_RELEVANTE_PARA_QUITACAO` (`engine/tipos.py:8-11`).
Procedimento: rodar `build`, listar os arquivos acusados, corrigir, e
**reportar a lista na tarefa** para que a revisão confirme que a varredura
se cumpriu (`AC-68`, mesmo procedimento de `T-86`/`T-92` na Rodada 2).

## R3.11. Traceability

| Requisito | Coberto por (seção do plano) |
| --- | --- |
| `RF-36` — quatro campos escalares de reserva, com desconhecido | R3.4.2 (enums de domínio) · R3.4.4 (campos em `EstadoFinanceiro`) · R3.2 (`DinheiroTalvez` reaproveitado) · R3.9.4 (`AC-62`) |
| `RF-37` — `DINHEIRO_DISPONIVEL: Dinheiro`, sem revalidação | R3.4.4 · R3.4.5 (`calcular_CAIXA_RECOMENDADO` como identidade) · R3.5 (dupla contagem prevenida na coleta) · R3.9.4 (`AC-63`) |
| `RF-38` — investimentos e ativos como coleção tipada por item | R3.4.3 (`ItemInvestimento`, `ItemAtivo`) · R3.4.4 (`tuple[...]`) · R3.2 (`frozen=True`) · R3.9.4 (`AC-64`) · R3.10 (trade-off do nome) |
| `RF-39` — recursos extraordinários por item, decidíveis | R3.4.2 (`JANELA_`/`CERTEZA_RECURSO_EXTRAORDINARIO`) · R3.4.3 (`RecursoExtraordinario`) · R3.4.5 (`calcular_EXTRAORDINARIOS_RECOMENDADOS`) · R3.9.4 (`AC-65`) |
| `RF-40` — enum de classificação, quatro valores, sem derivação | R3.4.1 · R3.2 (`Enum` vs. `Literal`) · R3.7 (classificação é dado) · R3.9.4 (`AC-66`) · R3.9.5 (`AC-67`, teste estático) · R3.10.1 (`OQ-26`) |
| `RF-41` — `Diagnostico.RESERVA_MOBILIZAVEL` → `DinheiroTalvez` | R3.4.6 (contrato) · R3.2 (`mypy --strict` como mecanismo) · R3.8 (falha visível no `build`) · **R3.10.2 (varredura completa de 14 consumidores)** · R3.9.6 (`AC-87`) |
| `RF-42` — rename do `VARIAVEL_GRAVADA` de `B4.03A` | R3.3 (uma linha, `bloco-04.yaml:156`) · R3.4.4 (o campo que passa a recebê-lo) · R3.9.4 (`AC-69`) |
| `RF-43` — `RESERVA_MOBILIZAVEL` por função pura, três regras na ordem | R3.4.5 (`derivar_RESERVA_MOBILIZAVEL`) · R3.5 (ordem das regras) · R3.8 (`EC-23`–`EC-26`) · R3.9.2 (`AC-70`–`AC-73`) |
| `RF-44` — `ATAQUE_IMEDIATO_POTENCIAL` | R3.4.5 (`calcular_ATAQUE_IMEDIATO_POTENCIAL`) · R3.9.3 (`AC-77`, `EC-27`, `EC-30`) |
| `RF-45` — os quatro componentes não protetivos | R3.4.5 (quatro funções) · R3.5 (ordem da §13.7) · R3.9.3 (`AC-78`, `AC-79`, `EC-30`) |
| `RF-46` — `NECESSIDADE_RESIDUAL` e `RESERVA_RECOMENDADA` | R3.4.5 (duas funções, trava `MODO_ESTABILIZACAO`) · R3.8 (`EC-26`, `EC-29`) · R3.9.2 (`AC-74`, `AC-75`) |
| `RF-47` — `ATAQUE_IMEDIATO_RECOMENDADO` | R3.4.5 (`calcular_ATAQUE_IMEDIATO_RECOMENDADO`) · R3.9.2 (`AC-75`, `AC-76`) · R3.9.3 (`EC-28`) |
| `RF-48` — elegível **por parâmetro**, nunca derivada | R3.4.5 (assinaturas, `*` obrigatório) · R3.1 (seta de entrada no diagrama) · R3.9.3 (`AC-80`) · R3.10 (trade-off) · **R3.10.1 (`AMB-R3-01`, aberta)** |
| `RF-49` — nenhuma das três fórmulas proibidas no código | R3.4.5 (docstring da trava) · R3.9.5 (`test_sem_percentual_automatico_de_reserva`, `AC-81`) |
| `RF-50` — hierarquia `POTENCIAL >= RECOMENDADO >= 0` | R3.4.5 (`verificar_hierarquia_ataque_imediato`) · R3.8 (`ErroInvariante`) · R3.9.3 (`AC-82`) · R3.10 (trade-off da função separada) |
| `RF-51` — substituir o placeholder `dinheiro(0)` e a docstring | R3.4.6 · R3.1 (ponto 4) · R3.9.6 (`AC-85`, `AC-86`, `AC-87`) · R3.10.1 (`AMB-R3-01` condiciona a parte de `ATAQUE_IMEDIATO_RECOMENDADO`) |
| `RF-52` — sem dupla contagem no verificável sem 3C | R3.4.3 (`ITEM_ID`, tipos distintos) · R3.5 (tabela dos quatro casos vedados) · R3.9.3 (`AC-83`) · R3.9.4 (`AC-84`) · R3.10.1 (`OQ-33`) |

**Cobertura desta rodada:** 17 de 17 requisitos (`RF-36`–`RF-52`). Nenhum
requisito das fatias 3A/3B ficou sem seção correspondente. Nenhum item deste
plano existe sem requisito que o peça — `ITEM_ID` e
`verificar_hierarquia_ataque_imediato`, os dois candidatos naturais a
over-engineering, estão ancorados em `RF-52`/`AC-83` e `RF-50`/`AC-82`
respectivamente, e nada além deles foi acrescentado.

**Uma ambiguidade nova (`AMB-R3-01`) permanece aberta** e precisa de decisão
humana antes de `/sdd:tasks` fechar a tarefa de `RF-51`. As sete questões de
metodologia (`OQ-26`, `OQ-27`, `OQ-29`, `OQ-30`, `OQ-31`, `OQ-32`, `OQ-35`)
continuam com o especialista e **nenhuma delas foi antecipada aqui**.

> Requisito sem cobertura é buraco no plano. Item de plano sem requisito é
> over-engineering.

---

# Rodada 4 — Classificação de Ativos/Investimentos e Valor Líquido Realizável, fatia 4A (2026-09-09)

> Escopo: `RF-53` a `RF-60` (spec §2, Rodada 4, fatia 4A). Fonte normativa
> congelada: `specs/motor-calculo.spec.md` §14 ("Fechamento Canônico —
> Necessidade Financeira Imediata e Classificação de Ativos"), em resposta a
> `OQ-29`/`OQ-26`/`OQ-27` (Rodada 3). Fora de escopo: `NECESSIDADE_FINANCEIRA_
> IMEDIATA_ELEGIVEL`/`NECESSIDADE_IMEDIATA_DIVIDA` (fatia 4B), ligação em
> `calcular_diagnostico` (fatia 4C), qualquer trabalho em `app-aluno` — spec
> §9, discovery `motor-calculo.discovery.md` (Rodada 4) §8.

## R4.1. Architecture Overview

Nenhuma camada nova, nenhum ponto de I/O novo. Diferente da Rodada 3, esta
fatia **não** é puramente aditiva: ela **inverte** um contrato que a própria
Rodada 3 desenhou deliberadamente na direção oposta (`ItemAtivo`/
`ItemInvestimento.CLASSIFICACAO_MOBILIZACAO` deixa de ser dado de entrada e
passa a ser derivado) e **retipa** os dois itens de patrimônio para carregar
os campos brutos que a derivação consome.

```text
 (fora de engine/ — app-aluno, OQ-37, inalterado nesta fatia)
  respostas Bloco 4  ──montador de estado──┐
                                            ▼
 [0] CONTRATO DE ENTRADA — engine/estado.py  (RF-59, RF-60)
     ItemInvestimento — ganha os campos BRUTOS da §14.3.1:
       LIQUIDEZ_INVESTIMENTOS, DISPOSICAO_USO_INVESTIMENTO,
       VALOR_ESTIMADO_ATIVO, CUSTO_DESMOBILIZACAO_INVESTIMENTOS_EXISTE,
       CUSTO_DESMOBILIZACAO_INVESTIMENTOS
     ItemAtivo — ganha os campos BRUTOS da §14.4–§14.9:
       TIPO_ATIVO_FISICO, POSSIBILIDADE_VENDA, ESSENCIALIDADE,
       VALOR_ESTIMADO_ATIVO, SALDO_PASSIVO_VINCULADO_EXISTE,
       SALDO_PASSIVO_VINCULADO, CUSTOS_ESTIMADOS_DESMOBILIZACAO_EXISTE,
       CUSTOS_ESTIMADOS_DESMOBILIZACAO, RENDA_RECORRENTE_ATIVO,
       CUSTO_RECORRENTE_ATIVO
     CLASSIFICACAO_MOBILIZACAO ← REMOVIDO do construtor (RF-59, decisão (a) — R4.1.1)
                                            │
                                            ▼
 [1] CÁLCULO PURO — engine/classificacao_ativos.py  (novo · RF-53..RF-58)
     ┌──────────────────────────────────────────────────────────────────┐
     │ derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(...)     §14.12.1 → RF-57 │
     │ derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(...)           │
     │                                                  §14.12.2 → RF-57 │
     │ classificar_investimento(...)     §14.3, §14.3.1  → RF-53        │
     │ classificar_ativo_fisico(...)     §14.4–§14.9     → RF-54..RF-56 │
     └──────────────────────────────────────────────────────────────────┘
       ↑ TODAS as entradas por parâmetro (NFR Pureza · Rodada 4)
                                            │
                                            ▼
 [2] CONSUMO — engine/ataque_imediato.py  (Rodada 3, RF-44/RF-45 adaptadas)
     calcular_ATAQUE_IMEDIATO_POTENCIAL / calcular_INVESTIMENTOS_RECOMENDADOS /
     calcular_ATIVOS_RECOMENDADOS chamam classificar_investimento(item)/
     classificar_ativo_fisico(item) em vez de ler item.CLASSIFICACAO_MOBILIZACAO
```

**Três pontos de mudança, e só três:**

1. **`engine/estado.py`** — `ItemInvestimento` e `ItemAtivo` perdem o campo
   `CLASSIFICACAO_MOBILIZACAO` do construtor e ganham os campos brutos que
   `classificar_investimento`/`classificar_ativo_fisico` exigem (`RF-59`).
2. **`engine/classificacao_ativos.py`** (arquivo **novo**) — as quatro
   funções puras da §14.3–§14.12 (`RF-53`–`RF-58`).
3. **`engine/ataque_imediato.py`** — as três funções da Rodada 3 que hoje
   leem `item.CLASSIFICACAO_MOBILIZACAO` (`calcular_ATAQUE_IMEDIATO_
   POTENCIAL`, `calcular_INVESTIMENTOS_RECOMENDADOS`, `calcular_ATIVOS_
   RECOMENDADOS`) passam a chamar a função de classificação sobre o item
   em vez de ler um campo que não existe mais.

Mais a varredura completa de consumidores fora de `engine/` (R4.1.2) e a
reescrita do teste estático (`RF-60`, R4.9.5).

**Nenhuma lei de arquitetura é violada.** `engine/` continua sem importar
`persistencia/`, `app/`, `collection/` ou `report/`; sem I/O; sem relógio;
sem parâmetro `P_*` embutido (nenhuma fórmula da §14 usa parâmetro
calibrável). `engine/classificacao_ativos.py` não importa de `engine/
ataque_imediato.py` nem de `engine/gates.py` — é a direção inversa
(`ataque_imediato.py` importa de `classificacao_ativos.py`), preservando o
grafo de import que a Rodada 3 já documentou como livre de ciclo novo.

### R4.1.1. A decisão mais importante desta fatia — mecanismo de `CLASSIFICACAO_MOBILIZACAO` (`OQ-40`)

Duas alternativas, ambas identificadas pelo discovery (Rodada 4, §2) e por
`RF-59`/`AC-98`, nenhuma delas decidida por nenhuma fonte normativa —
decisão técnica deste plano, no sentido de `sdd.config.md` §6.

**(a) — Campo removido do construtor; classificação nunca armazenada, sempre
recalculada por `classificar_ativo_fisico(item)`/`classificar_investimento(item)`.**

**(b) — Campo mantido na dataclass, populado por função de fábrica**
(`criar_item_ativo(..., CLASSIFICACAO_MOBILIZACAO=classificar_ativo_fisico(...))`),
com `object.__setattr__` ou construção via fábrica em vez de via construtor
posicional/nomeado direto.

**Decisão: (a).** Razões, uma a uma:

1. **`frozen=True, slots=True` não tem hoje, em nenhum lugar de
   `engine/estado.py`, o padrão `object.__setattr__` dentro de
   `__post_init__`.** As três dataclasses de item (`ItemInvestimento`,
   `ItemAtivo`, `RecursoExtraordinario`) e `Divida`/`EstadoFinanceiro` usam
   `__post_init__` **exclusivamente** para validar (`_recusar_float`), nunca
   para atribuir. Introduzir `object.__setattr__` seria o primeiro uso desse
   padrão no arquivo inteiro — um mecanismo novo para um problema que (a)
   resolve sem mecanismo novo nenhum.
2. **(b) preserva `item.CLASSIFICACAO_MOBILIZACAO` como leitura**, o que
   parece menor mudança de superfície — mas exige uma "fábrica oficial" cuja
   disciplina (nunca construir via `ItemAtivo(...)` direto, sempre via
   `criar_item_ativo(...)`) não é imposta pelo sistema de tipos: nada no
   `mypy --strict` impede alguém de voltar a chamar o construtor da dataclass
   diretamente com uma classificação inventada — exatamente o que a Rodada 3
   quis impedir com o campo obrigatório sem default. (b) reabriria, em forma
   mais sutil, o mesmo risco que motivou o teste estático original: a
   disciplina dependeria de convenção de equipe, não de erro de tipo.
3. **(a) torna "chamar o construtor com `CLASSIFICACAO_MOBILIZACAO`" um erro
   de tipo, não um erro de lint.** Como o parâmetro deixa de existir na
   assinatura da dataclass, qualquer código que ainda tente passá-lo falha em
   `mypy --strict` (comando `build`) com `unexpected keyword argument` —
   mecanismo de rede mais forte que uma varredura AST (que é o que (b)
   exigiria continuar mantendo, só que provando a disciplina da fábrica em
   vez da ausência do argumento).
4. **`EC-32` já aponta a direção (a).** A spec já mudou o erro de contrato
   de "item chega sem classificação" para "item chega sem os campos
   brutos" — isso só faz sentido se o item **nunca carrega** classificação
   como dado de construção; os campos brutos são o que falta quando o
   contrato é violado, não uma classificação alternativa inventada.
5. **`AC-97` pede que o teste estático "verifique positivamente" a regra de
   derivação — não que ele policie uma convenção de fábrica.** É mais direto
   provar "toda chamada de `classificar_ativo_fisico`/`classificar_
   investimento` implementa exatamente as regras de `RF-53`–`RF-56`" (o que
   (a) permite verificar por execução dos sete `GAB-NFI-06`–`GAB-NFI-12`)
   do que provar "toda fábrica usa o classificador oficial" (o que exigiria
   inventariar todo ponto de fábrica, um problema que (a) não tem porque não
   há fábrica).

**Custo aceito de (a).** Todo consumidor que hoje lê
`item.CLASSIFICACAO_MOBILIZACAO` (as três funções de `engine/ataque_
imediato.py` listadas em R4.1) passa a chamar `classificar_ativo_fisico(item)`/
`classificar_investimento(item)` **a cada leitura**, em vez de ler um campo
já resolvido — reclassificação recomputada, não cara (as regras são
comparações e um punhado de somas em `Decimal`, sem I/O), mas repetida por
chamada. Se o perfil de uso futuro exigir memoização, ela é acrescentada
como decisão isolada, sem mudar o contrato de novo. Ver R4.10 para o
registro formal deste trade-off.

**Consequência para `RF-60` (teste estático).** Como o parâmetro nem existe
mais na assinatura da dataclass, o teste antigo (que reprovava qualquer
função com `CLASSIFICACAO_MOBILIZACAO` na anotação de retorno) precisa de
reescrita completa da premissa — não relaxamento. O teste novo prova o
oposto: que `classificar_investimento` e `classificar_ativo_fisico`
implementam exatamente as regras de `RF-53`/`RF-54`/`RF-55`/`RF-56`, na
ordem de precedência estrita, verificado pelos gabaritos `GAB-NFI-06` a
`GAB-NFI-12` mais os casos de precedência forçada de `AC-95`/`AC-96`. Ver
R4.9.5.

### R4.1.2. Varredura de consumidores — todos os pontos que constroem `ItemAtivo(`/`ItemInvestimento(` no repositório

**Lição das Rodadas 2 e 3, aplicada de novo** (spec NFR "Compatibilidade de
contrato — Rodada 4"; risco nomeado na spec §8). `grep -rn "ItemAtivo(\|
ItemInvestimento("` no repositório inteiro, não só em `engine/`:

| Arquivo | Linha | Constrói | O que muda com a decisão (a) |
| --- | --- | --- | --- |
| `persistencia/arquivo/repositorio_snapshots.py` | `:316` (`_item_investimento`), `:328` (`_item_ativo`) | ambos | Remove `CLASSIFICACAO_MOBILIZACAO=CLASSIFICACAO_MOBILIZACAO(bruto[...])`; adiciona os campos brutos novos, lidos do dicionário serializado (que por sua vez precisa passar a gravá-los — `_serializar_canonico` grava campo a campo, sem lista de nomes fixa, então a mudança é automática desde que os novos campos existam na dataclass) |
| `tests/regras/test_estado.py` | `:229` (`ItemInvestimento`), `:245`, `:250` (`ItemAtivo`) | ambos | Remove o argumento; adiciona campos brutos suficientes para que `classificar_investimento`/`classificar_ativo_fisico` produzam a classificação que o teste espera implicitamente pela posição no cenário |
| `tests/regras/test_componentes_recomendados.py` | `:54` (`_ativo`), `:64` (`_investimento`) — funções auxiliares de fixture | ambos | As duas funções auxiliares recebem hoje `classe: CLASSIFICACAO_MOBILIZACAO` como parâmetro e o repassam ao construtor — passam a receber os campos brutos que produzem aquela classe (ou, mais simples: recebem a classe **desejada** e escolhem valores brutos canônicos que a produzem, documentados) |
| `tests/regras/test_ataque_imediato_potencial.py` | `:44` (`_ativo`), `:54` (`_investimento`) | ambos | Idem acima — mesmo padrão de fixture auxiliar repetido em três arquivos de teste |
| `tests/regras/test_ataque_imediato.py` | `:71` (`_ativo`), `:81` (`_investimento`) | ambos | Idem |
| `tests/fixtures/carregar.py` | `:177` (`_carregar_item_investimento`), `:187` (`_carregar_item_ativo`) | ambos | Mesmo padrão de `repositorio_snapshots.py`: lê os campos brutos do JSON de fixture em vez da classificação pronta; os três `tests/fixtures/*.json` (`gab_a`, `gab_b`, `gab_c`) precisam dos campos brutos com valores neutros nas coleções vazias (já vazias hoje — sem impacto de dado, só de schema se algum dia deixarem de ser vazias) |
| `tests/regras/test_repositorio_snapshots.py` | `:297`, `:303` (`ItemInvestimento`), `:311` (`ItemAtivo`) | ambos | Fixture de round-trip: adiciona campos brutos, remove a classificação do construtor, e o teste passa a confirmar round-trip da classificação **derivada** (chamando o classificador nos dois lados da serialização) em vez de round-trip de um campo armazenado |

**Não é consumidor real a corrigir:** `tests/app_aluno/estatica/
test_sem_patrimonio_derivado_em_app.py:568` constrói `ItemAtivo(...)` apenas
como **string de código-fonte** dentro de um teste do detector AST daquele
arquivo (prova de que o lint de `app-aluno` pegaria a construção se ela
existisse em `app/`) — não é uma chamada real ao construtor, é um literal de
teste que nunca é executado como Python real do projeto. Com a decisão (a),
esse literal continua sintaticamente representando uma violação (`app/`
tentando construir um item já classificado), então o teste daquele slug
continua correto sem edição. Fora de escopo desta fatia (pertence a
`app-aluno`) — citado aqui só para não ficar órfão da varredura.

**Mecanismo de rede.** `mypy --strict` (comando `build`) falha em **todos**
os pontos acima com `unexpected keyword argument "CLASSIFICACAO_
MOBILIZACAO"` assim que o campo for removido do construtor — antes mesmo de
rodar teste (`EC-38`). Procedimento: remover o campo, rodar `build`, corrigir
cada acusação da lista acima, `test` roda por último. Reportar a lista
resultante na tarefa (mesmo procedimento de `R3.10.2`/`T-92`).

## R4.2. Tech Stack

**Nenhuma dependência nova.** Mesma stdlib da Rodada 3 (`decimal`,
`dataclasses`, `enum`, `typing.Final`) — confirmado por leitura de
`engine/estado.py`, `engine/tipos.py`, `engine/ataque_imediato.py`.

| Escolha | Uso | Justificativa (ancorada em `RF-NN`) |
| --- | --- | --- |
| `Decimal` via `engine/precisao.dinheiro()` (já em uso) | `VALOR_ESTIMADO_ATIVO`, `SALDO_PASSIVO_VINCULADO`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO` e a subtração de `RF-57` | NFR "Tolerância zero" da classificação e do exemplo monetário `GAB-NFI-12` (§5, Rodada 4). `float` produziria erro de representação binária na subtração de `RF-57`, inaceitável sob tolerância zero. Alternativa descartada: `float`, já proibida pelo teste estático `test_sem_float_no_motor.py` |
| `DinheiroTalvez = Dinheiro \| Desconhecido` (já existente) | `SALDO_PASSIVO_VINCULADO`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO`, `VALOR_ESTIMADO_ATIVO` (quando desconhecidos) | `RF-58`, `AC-99`, NFR "Dados desconhecidos nunca viram zero silenciosamente (Rodada 4)". Reaproveita o sentinela já usado por `RESERVA_TOTAL`/`SALDO_DEVEDOR_ATUAL` — nenhum mecanismo novo. Alternativa descartada: `Optional[Decimal]` (`None` significa "não perguntado", `RF-16`) |
| `Enum` de domínio fechado (já em uso) | `LIQUIDEZ_INVESTIMENTOS` (6 valores), `DISPOSICAO_USO_INVESTIMENTO`, `POSSIBILIDADE_VENDA` (5 valores), `ESSENCIALIDADE` (4 valores — `RF-54` exige `PARCIAL` além dos 3 já coletados, ver R4.4.2), `TIPO_ATIVO_FISICO` | `RF-53`/`RF-54`: os domínios da §14.3.1/§14.4 são fechados e normativos. `Enum` torna um quinto valor inexprimível em runtime e em `mypy --strict`, mesmo argumento da Rodada 3 para `CLASSIFICACAO_MOBILIZACAO` |
| `@dataclass(frozen=True, slots=True)` (já em uso) | `ItemInvestimento`, `ItemAtivo` retipados | Mesmo motivo da Rodada 3: hasheável por valor (`RF-10`/`V-01`), compatível com `_serializar_canonico` sem alteração de mecanismo |
| Função pura, `*` obrigatório no parâmetro (já em uso, padrão de `engine/ataque_imediato.py`) | `classificar_investimento`, `classificar_ativo_fisico`, `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO`, `_DISPONIVEL` | NFR "Pureza (Rodada 4)": todas as entradas por parâmetro, nada lido de `EstadoFinanceiro`/`Diagnostico`/relógio/arquivo/global — é o que torna os doze `GAB-NFI` verificáveis como teste de função pura (discovery §7) |
| `mypy --strict` (comando `build`, já em uso) | varredura de consumidores de `RF-59` | Mecanismo de rede que torna a remoção do parâmetro do construtor verificável por máquina (`EC-38`), mesma técnica de `RF-31`/`RF-41` |
| `ast` (stdlib, já em uso por `tests/estatica/`) | reescrita de `RF-60` | Mesma técnica de detecção estrutural já usada em `test_sem_derivacao_de_classificacao_mobilizacao.py` original e em `test_sem_float_no_motor.py` — sem biblioteca de terceiros |

**Contagem de dependências novas desta fatia: 0.**

## R4.3. Project Structure

| Caminho | Mudança | Novo? |
| --- | --- | --- |
| `engine/estado.py` | `ItemInvestimento`/`ItemAtivo`: `CLASSIFICACAO_MOBILIZACAO` **removido** do construtor; ganham os campos brutos de R4.4.1/R4.4.2. Novos enums de domínio: `LIQUIDEZ_INVESTIMENTOS`, `DISPOSICAO_USO_INVESTIMENTO`, `POSSIBILIDADE_VENDA`, `ESSENCIALIDADE`, `TIPO_ATIVO_FISICO` | não |
| `engine/classificacao_ativos.py` | **arquivo novo** — `classificar_investimento`, `classificar_ativo_fisico`, `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO`, `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` + `REGRAS: Final[tuple[str, ...]]` (obrigatório, `tests/estatica/test_toda_regra_citada.py`) | **sim** |
| `engine/ataque_imediato.py` | `calcular_ATAQUE_IMEDIATO_POTENCIAL`, `calcular_INVESTIMENTOS_RECOMENDADOS`, `calcular_ATIVOS_RECOMENDADOS` passam a chamar `classificar_investimento(item)`/`classificar_ativo_fisico(item)` em vez de ler `item.CLASSIFICACAO_MOBILIZACAO`; import novo de `engine/classificacao_ativos.py` | não |
| `persistencia/arquivo/repositorio_snapshots.py` | `_item_investimento`/`_item_ativo` (R4.1.2): campos brutos em vez de classificação pronta | não |
| `tests/fixtures/carregar.py` | `_carregar_item_investimento`/`_carregar_item_ativo` (R4.1.2) | não |
| `tests/regras/test_estado.py`, `test_componentes_recomendados.py`, `test_ataque_imediato_potencial.py`, `test_ataque_imediato.py`, `test_repositorio_snapshots.py` | fixtures auxiliares de item retipadas (R4.1.2) | não |
| `tests/regras/test_classificacao_ativos.py` | **arquivo novo** — `AC-88`–`AC-96` (`GAB-NFI-06`–`GAB-NFI-12` + os dois casos de precedência forçada) | **sim** |
| `tests/regras/test_valor_liquido_realizavel.py` | **arquivo novo** — `AC-94`, `AC-99` (`GAB-NFI-12` e propagação de desconhecido) | **sim** |
| `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` | **reescrito por completo** — premissa invertida (`RF-60`, `AC-97`). Nome do arquivo mantido para preservar o histórico do teste (a própria docstring original já previa este momento); conteúdo, docstring e nome das funções internas trocam | não (mesmo caminho, conteúdo novo) |
| `tests/estatica/test_veiculo_nao_essencial_bloqueado.py` | **arquivo novo** — `AC-100`, `EC-39`: prova que o ramo de veículo não essencial com venda aceita não produz classificação e não inventa renda | **sim** |
| `pyproject.toml` | nenhuma mudança de marcador — os testes desta fatia entram em `tests/regras/` (padrão `regra`) e `tests/estatica/`, sem categoria nova | não |

**Nota de escopo.** Nenhum arquivo de `app/`, `collection/` ou `report/` é
tocado por esta fatia (spec §9). `app/montagem/estado.py` e
`tests/app_aluno/estatica/hashes_congelados.json` são sinalizados, não
editados — mesma disciplina de coordenação da Rodada 3 (R3.3).

## R4.4. Data Model

Contratos e assinaturas. Nomes de campo idênticos à §14, caractere por
caractere (`sdd.config.md` §7). Corpo de função é escopo de `/sdd:implement`.

### R4.4.1. Campos brutos novos de `ItemInvestimento` — `RF-53`, `RF-59`

```python
# engine/estado.py — RF-53 · §14.3.1 · RF-59 (retipagem)
class LIQUIDEZ_INVESTIMENTOS(Enum):
    """RF-53 · §14.3.1 — domínio FECHADO de seis valores, já citado pelo
    discovery da Rodada 3 (`bloco-04.yaml:239-245`). Substitui
    `ItemInvestimento.POSSUI_LIQUIDEZ: bool` (Rodada 3) — POSSUI_LIQUIDEZ
    continua existindo (§13.3 ainda o usa, ver nota abaixo), mas não basta
    mais para a Regra 1/Regra 4/Regra 5 de classificação."""

    D0 = "D0"
    D1 = "D1"
    D7 = "D7"
    D30 = "D30"
    MAIS_30 = "MAIS_30"
    BLOQUEADO = "BLOQUEADO"


class DISPOSICAO_USO_INVESTIMENTO(Enum):
    """RF-53 · §14.3.1 Regras 1, 3, 4, 5 — três valores."""

    NAO = "NAO"
    TALVEZ = "TALVEZ"
    SIM = "SIM"


@dataclass(frozen=True, slots=True)
class ItemInvestimento:
    """RF-38 (Rodada 3) · RF-53, RF-59 (Rodada 4) — UM investimento.

    `CLASSIFICACAO_MOBILIZACAO` NÃO é mais campo do construtor (RF-59,
    decisão (a) de R4.1.1): chega DERIVADA por `classificar_investimento
    (item)`, nunca armazenada. Os campos abaixo são os BRUTOS que a §14.3.1
    consome — item que chega sem eles é erro de contrato (EC-32), não mais
    "item sem classificação" (EC-31, revogado).
    """

    ITEM_ID: str
    VALOR_LIQUIDO_REALIZAVEL: Dinheiro  # já apurado (OQ-27 fechada só p/ ATIVO — ver nota)
    POSSUI_LIQUIDEZ: bool               # Rodada 3 · ainda usado por §13.3 (liquidez p/ recomendado)
    LIQUIDEZ_INVESTIMENTOS: LIQUIDEZ_INVESTIMENTOS          # §14.3.1 Regras 1, 4, 5
    DISPOSICAO_USO_INVESTIMENTO: DISPOSICAO_USO_INVESTIMENTO  # §14.3.1 Regras 1, 3, 4, 5
    VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL: Dinheiro      # §14.3.1 Regra 4 — nome literal §14
    TEM_CUSTO_CONHECIDO: bool           # §14.3.1 Regra 5 — "existe custo conhecido de saída"
    SEM_CUSTO_PERDA_RELEVANTE: bool     # §14.3.1 Regra 4 — "não existe custo/perda relevante conhecida"

    def __post_init__(self) -> None:
        _recusar_float(self)
```

> **Nota — `VALOR_LIQUIDO_REALIZAVEL` (Rodada 3) e `VALOR_LIQUIDO_
> REALIZAVEL_ATIVO_DISPONIVEL` (§14.3.1, Rodada 4) coexistem em
> `ItemInvestimento`.** A §14.12.6 fecha a fórmula de valor líquido
> realizável de investimento (`VALOR_ESTIMADO_ATIVO −
> CUSTO_DESMOBILIZACAO_INVESTIMENTOS`) separadamente da fórmula de ativo
> físico (§14.12.1). Para não duplicar a decisão de `OQ-27`/Rodada 3 (que já
> modelou `ItemInvestimento.VALOR_LIQUIDO_REALIZAVEL` como valor apurado de
> entrada), este plano mantém esse campo como está e adiciona o campo
> `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` **como entrada direta também**
> — não recalculado por `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`
> internamente, porque a §14.3.1 Regra 4 é textual sobre essa variável
> nomeada, e recalculá-la a partir de campos que `ItemInvestimento` não tem
> hoje (`SALDO_PASSIVO_VINCULADO` não se aplica a investimento, `CUSTO_
> DESMOBILIZACAO_INVESTIMENTOS` sim) ampliaria o escopo desta fatia para
> reconciliar dois valores já existentes sob nomes ligeiramente distintos —
> risco desnecessário sem requisito que o peça. Ver R4.10 para o registro
> formal deste trade-off.

### R4.4.2. Campos brutos novos de `ItemAtivo` — `RF-54`–`RF-58`, `RF-59`

```python
# engine/estado.py — RF-54..RF-58 · §14.4-§14.9, §14.12 · RF-59 (retipagem)
class TIPO_ATIVO_FISICO(Enum):
    """RF-54 · §14.4 — os três tipos que a §14 distingue por nome de
    variável de coleta (`IMOVEL_*`, `VEICULO_*`, `OUTRO_ATIVO_*`,
    discovery Rodada 4 §1.3). Necessário para que `classificar_ativo_fisico`
    saiba, no ramo NAO_ESSENCIAL + {SIM, JA_PRETENDE}, se está diante do
    ramo bloqueado por OQ-38 (RF-56)."""

    IMOVEL = "IMOVEL"
    VEICULO = "VEICULO"
    OUTRO_ATIVO = "OUTRO_ATIVO"


class POSSIBILIDADE_VENDA(Enum):
    """RF-54 · §14.4 — domínio FECHADO, idêntico entre os três tipos de
    ativo na coleta (discovery §1.3: `POSSIBILIDADE_VENDA_IMOVEL/_VEICULO/
    _OUTRO_ATIVO` já usam estes cinco valores, caractere por caractere)."""

    NAO = "NAO"
    EXTREMO = "EXTREMO"
    TALVEZ = "TALVEZ"
    SIM = "SIM"
    JA_PRETENDE = "JA_PRETENDE"


class ESSENCIALIDADE(Enum):
    """RF-54 · §14.5, §14.6 — QUATRO valores conforme a §14, embora a
    coleta hoje só produza três (imóvel/veículo, sem PARCIAL) ou dois
    (outro ativo, sem IMPORTANTE/PARCIAL). §14.6 trata IMPORTANTE e PARCIAL
    com a MESMA regra, então PARCIAL nunca exercitado por dado real não
    quebra `classificar_ativo_fisico` — só fica um valor do domínio sem
    caminho de coleta ainda (discovery §1.3, não bloqueante)."""

    ESSENCIAL = "ESSENCIAL"
    IMPORTANTE = "IMPORTANTE"
    PARCIAL = "PARCIAL"
    NAO_ESSENCIAL = "NAO_ESSENCIAL"


@dataclass(frozen=True, slots=True)
class ItemAtivo:
    """RF-38 (Rodada 3) · RF-54..RF-58, RF-59 (Rodada 4) — UM ativo físico.

    `CLASSIFICACAO_MOBILIZACAO` NÃO é mais campo do construtor (RF-59,
    decisão (a)): chega DERIVADA por `classificar_ativo_fisico(item)`.
    `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` (Rodada 3) TAMBÉM deixa de
    ser campo de entrada — a §14.12 fecha a fórmula (RF-57), então esta
    fatia deriva o valor em vez de recebê-lo pronto (quebra de contrato
    adicional, não coberta por RF-59 sozinho — ver nota abaixo).
    """

    ITEM_ID: str
    TIPO_ATIVO_FISICO: TIPO_ATIVO_FISICO                # §14.8, RF-56
    POSSIBILIDADE_VENDA: POSSIBILIDADE_VENDA            # §14.4.1, §14.5-14.9
    ESSENCIALIDADE: ESSENCIALIDADE                      # §14.5, §14.6, §14.7
    VALOR_ESTIMADO_ATIVO: DinheiroTalvez                # §14.12.1 — pode ser desconhecido (EC-36)
    POSSUI_PASSIVO_VINCULADO: bool                      # §14.12.4 — "não existe" → 0
    SALDO_PASSIVO_VINCULADO: DinheiroTalvez              # §14.12.4 — só relevante se acima=True
    POSSUI_CUSTO_DESMOBILIZACAO: bool                    # §14.12.5 — "não existe" → 0
    CUSTOS_ESTIMADOS_DESMOBILIZACAO: DinheiroTalvez       # §14.12.5 — valor OU percentual já resolvido (ver nota)
    RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None         # §14.8 — None = estruturalmente ausente (veículo, RF-56)
    CUSTO_RECORRENTE_ATIVO: DinheiroTalvez                # §14.8

    def __post_init__(self) -> None:
        _recusar_float(self)
```

> **Nota — `RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None`, não só
> `DinheiroTalvez` (`RF-56`, `EC-39`).** `None` aqui é ausência
> **estrutural** (a coleta não tem `RENDA_RECORRENTE_VEICULO`, `OQ-38`),
> distinta de `DESCONHECIDO` (resposta não dada a uma pergunta que existe) —
> mesmo padrão já usado por `SinaisComportamentais.JANELA_NOVA_DIVIDA:
> JANELA_NOVA_DIVIDA | None` na Rodada 1/2. É essa distinção de tipo que
> torna `RF-56` verificável sem inventar dado: `classificar_ativo_fisico`
> recebe `None` para veículo (nunca `DESCONHECIDO`, nunca `dinheiro(0)`) e o
> trata como sinalização de bloqueio, não como "efeito recorrente
> desconhecido" da §14.9 (ver R4.6.1 e R4.8 — decisão explícita de não
> adotar a leitura `OQ-42`).

> **Nota — `CUSTOS_ESTIMADOS_DESMOBILIZACAO` já resolvido antes de entrar no
> item.** A §14.12.5 distingue valor monetário direto de percentual
> (`VALOR_ESTIMADO_ATIVO × PERCENTUAL_CUSTO_DESMOBILIZACAO`). Este plano
> resolve a normalização de percentual **na fronteira de montagem do estado**
> (fora de `engine/`, mesmo padrão de `RF-37`/`CAIXA_RECOMENDADO`: o motor
> recebe o valor já resolvido em `Dinheiro`, e `derivar_VALOR_LIQUIDO_
> REALIZAVEL_ATIVO` só aplica a regra "existe/não existe/desconhecido" da
> §14.12.5, não a conversão percentual→monetário. Isso mantém a função de
> derivação simples e testável com os valores literais dos gabaritos
> (`GAB-NFI-12` já fornece os três componentes em `Dinheiro` puro, nunca
> como percentual) — ver R4.10 para o trade-off registrado.

### R4.4.3. `engine/classificacao_ativos.py` — as quatro funções puras — `RF-53`–`RF-58`

```python
# engine/classificacao_ativos.py — NOVO · RF-53..RF-58 · §14.3-§14.12
REGRAS: Final[tuple[str, ...]] = (
    "RF-53", "RF-54", "RF-55", "RF-56", "RF-57", "RF-58",
    "§14.3", "§14.3.1", "§14.4", "§14.5", "§14.6", "§14.7", "§14.8", "§14.9",
    "§14.12",
)


def derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO(
    *,
    VALOR_ESTIMADO_ATIVO: DinheiroTalvez,
    POSSUI_PASSIVO_VINCULADO: bool,
    SALDO_PASSIVO_VINCULADO: DinheiroTalvez,
    POSSUI_CUSTO_DESMOBILIZACAO: bool,
    CUSTOS_ESTIMADOS_DESMOBILIZACAO: DinheiroTalvez,
) -> DinheiroTalvez:
    """RF-57 · §14.12.1, §14.12.4, §14.12.5 · §14.14
    `deriveValorLiquidoRealizavelAtivo`.

    `VALOR_ESTIMADO_ATIVO − SALDO_PASSIVO_VINCULADO −
    CUSTOS_ESTIMADOS_DESMOBILIZACAO`. PODE ser negativo (§14.12.2, REGRA
    CANÔNICA) — nenhum MAX/MIN aqui. Propaga DESCONHECIDO (nunca 0) quando
    o próprio valor estimado, o passivo existente, ou o custo existente são
    desconhecidos (RF-58, EC-36, AC-99).
    """


def derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL(
    *, VALOR_LIQUIDO_REALIZAVEL_ATIVO: DinheiroTalvez
) -> DinheiroTalvez:
    """RF-57 · §14.12.2 · §14.14 `deriveValorLiquidoRealizavelAtivoDisponivel`
    — `MAX(0, VALOR_LIQUIDO_REALIZAVEL_ATIVO)`. NUNCA negativo (REGRA
    CANÔNICA). Propaga DESCONHECIDO sem aplicar MAX sobre um desconhecido
    (GAB-NFI-12, AC-94).

    Função SEPARADA da anterior — não uma composta que já aplica MAX
    internamente — porque a spec exige as DUAS variáveis expostas e
    testáveis independentemente (RF-57, restrição dura do pedido desta
    fatia; ver R4.10).
    """


def classificar_investimento(item: ItemInvestimento) -> CLASSIFICACAO_MOBILIZACAO:
    """RF-53 · §14.3, §14.3.1, §14.3.1.1 · §14.14 `classifyInvestment`.

    SEIS regras em CADEIA if/elif, ORDEM ESTRITA (RF-53, NFR "Ordem de
    precedência é normativa"; AC-95, EC-33): bloqueio → dado desconhecido →
    disposição condicional → líquido/disponível/sem custo → custo
    conhecido/D30 → liquidez longa/indeterminado. Cada ramo é `elif`, nunca
    condição paralela — um investimento que satisfaz duas regras cai
    sempre na primeira.

    Nenhum ramo verifica TIPO de investimento (§14.3.1.1): CDB/previdência/
    ação/poupança não aparecem nesta função.
    """


def classificar_ativo_fisico(item: ItemAtivo) -> CLASSIFICACAO_MOBILIZACAO | None:
    """RF-54, RF-55, RF-56 · §14.4-§14.9 · §14.14 `classifyPhysicalAsset`.

    Cadeia if/elif em ORDEM ESTRITA (AC-96, EC-34, EC-35):
      1. POSSIBILIDADE_VENDA=NAO → NAO_MOBILIZAR (§14.4.1)
      2. dado material desconhecido p/ valor líquido → MOBILIZACAO_COM_RESSALVAS (§14.4.2)
      3. valor líquido disponível = 0 mas venda ainda traz benefício → MOBILIZACAO_COM_RESSALVAS (§14.4.3)
      4. ESSENCIAL → NAO_MOBILIZAR (venda NAO) ou MOBILIZACAO_COM_RESSALVAS (demais) — NUNCA RECOMENDAVEL (§14.5, RF-54)
      5. IMPORTANTE/PARCIAL → MOBILIZACAO_COM_RESSALVAS (EXTREMO/TALVEZ) ou MOBILIZACAO_POSSIVEL (SIM/JA_PRETENDE) (§14.6)
      6. NAO_ESSENCIAL + EXTREMO → MOBILIZACAO_COM_RESSALVAS (§14.7)
      7. NAO_ESSENCIAL + TALVEZ → MOBILIZACAO_POSSIVEL (§14.7)
      8. NAO_ESSENCIAL + {SIM, JA_PRETENDE} → avalia FLUXO_LIQUIDO_RECORRENTE_ATIVO (§14.8, §14.9):
         - TIPO_ATIVO_FISICO=VEICULO e RENDA_RECORRENTE_ATIVO is None → retorna None (RF-56, bloqueio OQ-38, NÃO produz nenhum valor do domínio)
         - fluxo desconhecido (RENDA/CUSTO=DESCONHECIDO, tipo != VEICULO) → MOBILIZACAO_POSSIVEL (§14.9, RF-55)
         - fluxo <= 0 → MOBILIZACAO_RECOMENDAVEL (§14.9)
         - fluxo > 0 → MOBILIZACAO_POSSIVEL (§14.9)

    Assinatura de retorno `CLASSIFICACAO_MOBILIZACAO | None`: o `None` é o
    sentinela ESTRUTURAL de "bloqueado por OQ-38", nunca confundido com
    `Desconhecido` do domínio de dado (RF-56 exige que o resultado NÃO seja
    nenhum valor do domínio de CLASSIFICACAO_ATIVO — `None` satisfaz
    literalmente essa exigência, e é distinguível de DESCONHECIDO por tipo).
    Todo CONSUMIDOR desta função (as três funções de RF-44/RF-45 tocadas)
    precisa tratar o ramo `None` explicitamente — `mypy --strict` recusa
    ignorá-lo.
    """
```

> **Nota de ordem — `classifyPhysicalAsset` (§14.14, pseudocódigo) versus a
> prosa das §14.4–§14.9.** O pseudocódigo da §14.14 verifica "dado
> desconhecido"/"valor líquido = 0" (§14.4.2/§14.4.3) **antes** da
> ramificação por essencialidade; a prosa apresenta §14.4 (bloqueio e dados
> desconhecidos) e só depois §14.5–§14.9 (essencialidade). As duas fontes
> concordam entre si — a prosa também trata §14.4 como precedente às demais
> seções por numeração — e concordam com `EC-35` ("`POSSIBILIDADE_VENDA=NAO`
> é sempre `NAO_MOBILIZAR` por §14.4.1, avaliada antes da ramificação por
> essencialidade"). Este plano segue o pseudocódigo §14.14 como ordem de
> implementação de referência, por ser a forma mais operacional e a que a
> própria spec cita como a fonte de `classifyPhysicalAsset` em `RF-54`. Não
> há conflito normativo a reportar — apenas registro de que a ordem exata
> (guardas de §14.4 antes de §14.5) segue a única leitura que os dois
> formatos da fonte sustentam em conjunto.

## R4.5. Data Flow

1. **Entrada.** `EstadoFinanceiro.investimentos`/`.ativos` chegam com os
   campos brutos de R4.4.1/R4.4.2 (nunca com `CLASSIFICACAO_MOBILIZACAO`
   pronta — o construtor não aceita mais esse argumento). Item sem os
   campos brutos que a classificação exige é erro de construção (`EC-32`,
   `TypeError`/`mypy` por campo obrigatório ausente).
2. **Derivação de valor líquido (ativo físico).** `derivar_VALOR_LIQUIDO_
   REALIZAVEL_ATIVO(item)` roda antes da classificação sempre que
   `classificar_ativo_fisico` precisar do valor líquido disponível
   (Regra 4 do investimento; §14.4.2/§14.4.3 do ativo físico) — a função de
   classificação chama as duas funções de R4.4.3 internamente sobre os
   campos do próprio item, em vez de exigir que o chamador já tenha
   calculado e passado o valor líquido como argumento separado (mantém
   `classificar_investimento(item)`/`classificar_ativo_fisico(item)` como
   assinatura de um único argumento — o item — o que R4.9 explora no
   trade-off de assinatura).
3. **Classificação.** `classificar_investimento(item)`/`classificar_ativo_
   fisico(item)` são chamadas **sob demanda**, no ponto de consumo
   (`engine/ataque_imediato.py`), nunca armazenadas. Para investimento, o
   resultado é sempre um dos quatro valores do domínio. Para ativo físico,
   o resultado é um dos quatro valores **ou** `None` (bloqueio `OQ-38`,
   só possível para veículo no ramo `NAO_ESSENCIAL` + `{SIM, JA_PRETENDE}`).
4. **Consumo.** `calcular_ATAQUE_IMEDIATO_POTENCIAL`, `calcular_
   INVESTIMENTOS_RECOMENDADOS`, `calcular_ATIVOS_RECOMENDADOS` (Rodada 3,
   `engine/ataque_imediato.py`) chamam a função de classificação sobre cada
   item da coleção e tratam o `None` de ativo físico como "não soma, não
   erro" — mesma disciplina de filtro que já aplicam a `MOBILIZACAO_COM_
   RESSALVAS`/`NAO_MOBILIZAR` (itens que não entram em nenhuma soma não
   produzem erro, só ficam de fora).
5. **Saída.** Nada nesta fatia altera `Diagnostico` nem `calcular_
   diagnostico` (fora de escopo, fatia 4C). O efeito observável desta fatia
   é: `ATAQUE_IMEDIATO_POTENCIAL`/`_RECOMENDADO` (Rodada 3, já implementados)
   passam a poder computar valor não-zero para `INVESTIMENTOS_RECOMENDADOS`/
   `ATIVOS_RECOMENDADOS` quando o estado de entrada tiver itens que a nova
   classificação derive como `MOBILIZACAO_RECOMENDAVEL` — antes desta fatia,
   isso dependia de o chamador já ter classificado o item manualmente.

**Falha em cada etapa:** item sem campo bruto → erro de construção
(etapa 1, síncrono, antes de qualquer cálculo). Dado desconhecido em campo
que a classificação consome → `MOBILIZACAO_COM_RESSALVAS` (investimento
Regra 2; ativo físico §14.4.2) ou propagação de `DESCONHECIDO` no valor
líquido (nunca erro, nunca zero silencioso — `RF-58`). Veículo no ramo
bloqueado → `None`, tratado como ausência de classificação pelo consumidor,
nunca como exceção (não é erro de contrato, é resultado normativo
esperado — `RF-56`).

## R4.6. External Interfaces

Nenhuma interface externa nova. Mesma nota da Rodada 3: o motor não expõe
API de rede, arquivo ou banco — contrato é só assinatura Python.

### R4.6.1. O ramo bloqueado de `OQ-38` — como ele se manifesta em código (`RF-56`)

Decisão explícita pedida pelo escopo desta fatia: **sentinela `None` de
retorno**, não exceção nomeada, não `DESCONHECIDO`.

**Por que não exceção.** Levantar (`raise`) tornaria o bloqueio um caminho
de erro que o chamador precisa capturar — mas não é um erro de execução: é
um resultado normativo esperado e estável (o dado nunca vai existir para
veículo até a coleta mudar). Modelar como exceção obrigaria toda chamada de
`classificar_ativo_fisico` sobre veículo não essencial a viver dentro de
`try/except`, poluindo os três consumidores de `RF-44`/`RF-45` com
tratamento de exceção para um caso que não é excepcional — é, ao contrário,
o comportamento correto documentado.

**Por que não `DESCONHECIDO`.** É exatamente a leitura que `RF-56`/`EC-39`
proíbem (`OQ-42`, rejeitada pelo usuário para esta fatia): `DESCONHECIDO` é
o sentinela de "dado que existe conceitualmente mas não foi respondido" —
usá-lo para "a variável não existe estruturalmente na coleta" apagaria a
distinção entre as duas situações e, pior, faria a Regra "`fluxo desconhecido
→ MOBILIZACAO_POSSIVEL`" da §14.9 disparar **silenciosamente**, produzindo
uma classificação onde a norma exige nenhuma.

**Por que `None` e não um enum de bloqueio dedicado (ex.: `CLASSIFICACAO_
ATIVO_BLOQUEADA_POR_LACUNA_NORMATIVA`).** `None` já é o sentinela que este
mesmo plano usa para "ausência estrutural" em `RENDA_RECORRENTE_ATIVO:
DinheiroTalvez | None` (R4.4.2) — reaproveitar o mesmo tipo-soma para o
resultado da função de classificação mantém consistência dentro da própria
fatia, sem introduzir um terceiro conceito de ausência (depois de
`Desconhecido` e `None` estrutural, um enum novo seria um quarto jeito de
dizer "não tenho isso"). Um enum dedicado foi descartado por não agregar
nada que o tipo `| None` já não expresse, e por tornar `mypy --strict` menos
direto para forçar o chamador a tratar o caso (`Optional` é o padrão
idiomático que o `mypy` já verifica por exaustividade de `is None`).

**Consequência para o chamador.** Assinatura
`classificar_ativo_fisico(item: ItemAtivo) -> CLASSIFICACAO_MOBILIZACAO |
None`. `mypy --strict` recusa qualquer consumidor que trate o retorno como
`CLASSIFICACAO_MOBILIZACAO` puro sem checar `is None` primeiro — mesma
disciplina de exaustividade já usada para `DinheiroTalvez`/`TaxaTalvez`
(`engine/tipos.py`).

## R4.7. State Management

Nenhuma mudança de gestão de estado. `engine/classificacao_ativos.py`
segue a mesma disciplina de `engine/ataque_imediato.py`: funções puras,
sem estado próprio, sem cache, sem memoização (custo aceito em R4.1.1).
`ItemInvestimento`/`ItemAtivo` continuam imutáveis por valor
(`frozen=True, slots=True`), então recalcular a classificação a cada
chamada produz sempre o mesmo resultado para o mesmo item — determinismo
preservado sem nenhum mecanismo adicional de sincronização.

## R4.8. Error Handling Strategy

| Situação | Detecção | Resposta | Recuperação |
| --- | --- | --- | --- |
| Item chega sem campo bruto obrigatório (`EC-32`) | `TypeError` na construção (campo posicional/nomeado ausente) ou `mypy --strict` em tempo de checagem | Falha imediata e nomeada — nunca constrói o item com valor inventado | Corrigir o ponto de montagem para fornecer o campo; não há fallback |
| `VALOR_ESTIMADO_ATIVO` do próprio ativo desconhecido (`EC-36`) | `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO` retorna `DESCONHECIDO` na primeira guarda, sem avaliar passivo/custo | Propagação silenciosa **do estado desconhecido**, nunca de zero | Quem consome trata `DESCONHECIDO` como pendência (fora desta fatia — não há `Diagnostico` tocado aqui, mas a assinatura já admite o valor) |
| `SALDO_PASSIVO_VINCULADO`/`CUSTOS_ESTIMADOS_DESMOBILIZACAO` existem mas desconhecidos (`RF-58`, `AC-99`) | Guardas dedicadas em `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO` | Retorna `DESCONHECIDO` para `VALOR_LIQUIDO_REALIZAVEL_ATIVO` inteiro — nunca soma um zero silencioso | Mesma consequência acima |
| Investimento/ativo satisfaz mais de uma regra de classificação simultaneamente (`EC-33`, `EC-34`, `AC-95`, `AC-96`) | Cadeia `if`/`elif` estrita — não há detecção em runtime, é garantia estrutural do código | Primeira regra que casa vence; regras posteriores nunca são avaliadas | N/A — é o comportamento correto, não uma falha |
| Veículo não essencial, venda aceita, sem renda recorrente (`RF-56`, `EC-39`, bloqueio `OQ-38`) | `RENDA_RECORRENTE_ATIVO is None` dentro de `classificar_ativo_fisico`, checado antes de qualquer aritmética de fluxo | Retorna `None` — nenhum valor do domínio, nenhuma exceção | Nenhuma — fica bloqueado até `OQ-38` ser respondida pelo especialista; consumidor trata `None` como "não soma em nenhum componente" |
| Consumidor antigo tenta construir `ItemAtivo(...)`/`ItemInvestimento(...)` com `CLASSIFICACAO_MOBILIZACAO=...` (`EC-38`) | `mypy --strict` (comando `build`) — `unexpected keyword argument` | Falha antes de `test` rodar | Remover o argumento, fornecer os campos brutos (R4.1.2 lista todos os pontos) |
| Consumidor trata o retorno de `classificar_ativo_fisico` como não-`None` sem checar | `mypy --strict` — `Optional` não estreitado | Falha em tempo de checagem, antes de runtime | Adicionar `if resultado is None: ...` explícito |

## R4.9. Testing Strategy

- **Unitários (função pura, `tests/regras/`, marcador `regra`):**
  `classificar_investimento` — seis regras, uma função por regra mais os
  gabaritos (`AC-88`–`AC-90`, `GAB-NFI-06`–`GAB-NFI-08`) e o caso de
  precedência forçada (`AC-95`, `EC-33`). `classificar_ativo_fisico` — oito
  ramos de decisão, gabaritos (`AC-91`–`AC-93`, `GAB-NFI-09`–`GAB-NFI-11`),
  precedência forçada (`AC-96`, `EC-34`, `EC-35`), e o bloqueio de veículo
  (`AC-100`, `EC-39`). `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO`/`_
  DISPONIVEL` — os dois lados do exemplo de `GAB-NFI-12` (positivo e
  negativo, `AC-94`) e propagação de desconhecido (`AC-99`, `EC-36`).
- **Integração (`tests/regras/test_ataque_imediato_potencial.py`,
  `test_componentes_recomendados.py`, retipados):** confirma que
  `calcular_ATAQUE_IMEDIATO_POTENCIAL`/`calcular_INVESTIMENTOS_
  RECOMENDADOS`/`calcular_ATIVOS_RECOMENDADOS` (Rodada 3) continuam
  produzindo o mesmo resultado quando o item chega com campos brutos que
  produzem a classificação esperada, em vez de com a classificação pronta —
  é a prova de que a inversão de contrato (`RF-59`) não muda nenhum
  resultado numérico já coberto pela Rodada 3.
- **Estático (`tests/estatica/`):**
  `test_sem_derivacao_de_classificacao_mobilizacao.py` reescrito (`RF-60`,
  `AC-97`, R4.9.5) e `test_veiculo_nao_essencial_bloqueado.py` novo
  (`AC-100`).
- **Fora de teste automatizado:** nada desta fatia — os doze `GAB-NFI`
  relevantes (`06`–`12`) são todos executáveis como teste de função pura
  (discovery §7), sem dependência do especialista.

### R4.9.5. Reescrita de `RF-60` — o que o teste passa a provar

O teste antigo provava **ausência**: nenhuma função de `engine/` tem
`CLASSIFICACAO_MOBILIZACAO` na anotação de retorno. Isso está
estruturalmente invertido agora — `classificar_investimento` e
`classificar_ativo_fisico` **precisam** ter essa anotação (ou `| None`, no
segundo caso) para existir. O teste novo prova **regra**, não ausência:

1. **Documentação da liberação** (mesmo padrão exigido por `AC-97`):
   docstring do módulo de teste registra a data (2026-09-09) e a fonte
   (§14) em que a derivação passou a ser permitida, preservando o histórico
   que a docstring original já antecipava.
2. **Prova positiva por execução dos gabaritos.** Os sete `GAB-NFI-06`–
   `GAB-NFI-12` (ou testes equivalentes de `tests/regras/test_
   classificacao_ativos.py`, `test_valor_liquido_realizavel.py`) já
   verificam que a implementação corresponde à regra — o teste estático
   não duplica essa verificação numérica; ele verifica uma propriedade
   ESTRUTURAL complementar: que a função de classificação **só** existe
   em `engine/classificacao_ativos.py` (não duplicada em outro módulo com
   uma regra divergente) e que nenhum outro ponto de `engine/` define uma
   segunda função com anotação de retorno `CLASSIFICACAO_MOBILIZACAO`
   fora desse módulo — o mesmo espírito de "um lugar só decide a regra"
   que o teste original protegia, adaptado para "um lugar só **é
   autorizado** a decidir a regra".
3. **Prova negativa preservada.** Os testes de detector (`test_detector_
   pega_derivacao_proposital`, `test_detector_pega_cada_forma_de_
   anotacao_de_retorno`, etc. — a bateria de provas negativas do arquivo
   original) são mantidos como estão: a heurística de varredura AST não
   muda, só o veredito sobre o que ela encontra em `engine/`
   real (antes: zero ocorrências esperadas fora do módulo autorizado;
   agora: exatamente as ocorrências de `engine/classificacao_ativos.py`,
   nomeadas e esperadas).

## R4.10. Risks & Trade-offs

| Decisão | Alternativa descartada | Por quê | Risco assumido |
| --- | --- | --- | --- |
| `CLASSIFICACAO_MOBILIZACAO` removida do construtor; classificação sempre recomputada por função (decisão (a), R4.1.1) | (b) campo mantido, populado por fábrica com `object.__setattr__` | `object.__setattr__` seria mecanismo novo, nunca usado em `engine/estado.py`; (b) não impede reconstrução direta com classificação inventada — reabriria o risco que a Rodada 3 fechou com campo obrigatório sem default; (a) vira erro de tipo verificável por `mypy --strict`, não convenção de equipe | Reclassificação recomputada a cada chamada de consumo (não cara — sem I/O — mas repetida). Se o perfil de uso exigir memoização, é decisão isolada futura, sem novo contrato |
| `classificar_ativo_fisico` retorna `CLASSIFICACAO_MOBILIZACAO \| None`, com `None` como sentinela de bloqueio `OQ-38` | Exceção nomeada (`ClassificacaoBloqueadaPorLacunaNormativa`); `DESCONHECIDO` como retorno | Exceção obrigaria `try/except` em todo consumidor para um caso não excepcional (resultado normativo esperado, estável). `DESCONHECIDO` é exatamente a leitura rejeitada (`OQ-42`) — apagaria a distinção entre "variável não respondida" e "variável não existe na coleta" e disparia `MOBILIZACAO_POSSIVEL` da §14.9 por engano | Todo consumidor de `classificar_ativo_fisico` precisa tratar `None` explicitamente (`mypy --strict` obriga) — leve aumento de superfície de tratamento em `engine/ataque_imediato.py`, mitigado por já existir o padrão de filtro por classe não-recomendável |
| `RENDA_RECORRENTE_ATIVO: DinheiroTalvez \| None` (três estados: valor, desconhecido, estruturalmente ausente) | `DinheiroTalvez` só (dois estados) com convenção de "veículo sempre desconhecido" | Colapsar os dois of "ausência" apagaria a distinção normativa entre "usuário não respondeu" (Desconhecido) e "a pergunta nem existe" (None) — exatamente a distinção que `RF-56` exige preservar. Mesmo padrão já usado por `JANELA_NOVA_DIVIDA \| None` | Terceiro estado a mais para todo consumidor tratar — mitigado por só existir em UM campo (`RENDA_RECORRENTE_ATIVO`), não espalhado pelo modelo |
| `ItemInvestimento.VALOR_LIQUIDO_REALIZAVEL` (Rodada 3) e `.VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` (Rodada 4, §14.3.1) coexistem, sem reconciliação | Derivar um a partir do outro; remover o da Rodada 3 e usar só o novo | A §14.3.1 Regra 4 é textual sobre uma variável nomeada `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`; reconciliar exigiria decidir se o `VALOR_LIQUIDO_REALIZAVEL` da Rodada 3 é o mesmo conceito ou não — decisão de modelagem que nenhuma fonte pede nesta fatia e que ampliaria o escopo para "consolidar dois campos" sem requisito | Duas variáveis de nome parecido no mesmo item, risco de confusão para quem ler `engine/estado.py` sem o histórico — mitigado pelas docstrings cruzadas (R4.4.1) |
| Normalização de `CUSTOS_ESTIMADOS_DESMOBILIZACAO` (percentual → monetário, §14.12.5) feita **fora** de `engine/`, na montagem do estado | Fazer a conversão dentro de `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO` | Mantém a função de derivação simples (regras "existe/desconhecido", não aritmética de percentual) e consistente com o padrão já usado para `CAIXA_RECOMENDADO` (motor recebe valor já resolvido); os gabaritos da §14 já fornecem os três componentes em `Dinheiro` puro | Se a montagem de estado (fora deste slug) não aplicar a conversão corretamente, o motor não tem como detectar que um "monetário" já devia ter sido um percentual resolvido — mitigado por documentação explícita do contrato (R4.4.2) |
| `engine/classificacao_ativos.py` como módulo novo, separado de `engine/ataque_imediato.py` | Adicionar as quatro funções dentro de `engine/ataque_imediato.py` | `ataque_imediato.py` já declara seu próprio escopo fechado na docstring ("Escopo deste arquivo hoje: `T-102`..`T-107`..."); a classificação é conceito de §14, tematicamente distinto de §13 (composição do ataque), mesmo critério de separação que já levou `RESERVA_MOBILIZAVEL` e `CLASSIFICACAO_MOBILIZACAO` a viverem em arquivos diferentes na Rodada 3 (`estado.py` vs. `ataque_imediato.py`) | Um arquivo a mais para o leitor navegar; mitigado pelo import explícito e por `REGRAS` citando a seção normativa em cada módulo |

### R4.10.1. Questões que exigem o especialista — não se resolvem neste plano

| ID | O que fica bloqueado | O que este plano fez em vez de adivinhar |
| --- | --- | --- |
| `OQ-38` | variável de renda recorrente de veículo | `classificar_ativo_fisico` retorna `None` nesse ramo específico (`RF-56`, R4.6.1) — os outros cinco ramos de veículo permanecem classificáveis |
| `OQ-42` (discovery, não spec) | leitura alternativa de `OQ-38` como "desconhecido por construção" | **Explicitamente rejeitada** para esta fatia, por pedido do usuário — não implementada, não contornada. Ver R4.6.1 |

**Questões da Rodada 4 que esta fatia não decide, por serem de fatia
diferente (`OQ-39`, `OQ-41`, `OQ-43` — fatias 4B/4C):** nada aqui antecipa
onde vive `VALOR_ACAO_FINANCEIRA_IMEDIATA`, `NECESSIDADE_IMEDIATA_DIVIDA`,
nem a mudança de assinatura de `calcular_diagnostico`.

## R4.11. Traceability

| Requisito | Coberto por (seção do plano) |
| --- | --- |
| `RF-53` — `classificar_investimento`, seis regras, ordem estrita | R4.4.3 (assinatura, cadeia `if/elif`) · R4.9 (`AC-88`–`AC-90`, `AC-95`) · R4.10 (nenhum trade-off de regra — a regra é normativa, só o módulo é decisão) |
| `RF-54` — `classificar_ativo_fisico`, essencialidade nunca automática | R4.4.2 (`ESSENCIALIDADE`, `POSSIBILIDADE_VENDA`) · R4.4.3 (oito ramos) · R4.9 (`AC-91`, `AC-96`) |
| `RF-55` — não essencial + venda aceita + fluxo desconhecido → `MOBILIZACAO_POSSIVEL` (imóvel/outro ativo) | R4.4.3 (ramo 8 de `classificar_ativo_fisico`) · R4.9 (`AC-92`, `AC-93`) |
| `RF-56` — veículo no mesmo ramo não produz classificação | R4.4.2 (`RENDA_RECORRENTE_ATIVO: DinheiroTalvez \| None`) · R4.4.3 (ramo 8, checagem `TIPO_ATIVO_FISICO=VEICULO`) · R4.6.1 (decisão `None`, justificativa completa) · R4.9 (`AC-100`) · R4.10.1 (`OQ-38`, `OQ-42` rejeitada) |
| `RF-57` — `VALOR_LIQUIDO_REALIZAVEL_ATIVO` (pode negativo) e `_DISPONIVEL` (nunca negativo), duas funções | R4.4.3 (duas funções separadas) · R4.9 (`AC-94`, `GAB-NFI-12`) · R4.10 (restrição dura preservada — nenhum `MAX` embutido na primeira função) |
| `RF-58` — normalização de passivo/custo, desconhecido nunca vira zero | R4.4.2 (`POSSUI_PASSIVO_VINCULADO`/`POSSUI_CUSTO_DESMOBILIZACAO` + `DinheiroTalvez`) · R4.4.3 (guardas de `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO`) · R4.8 (tabela de erro) · R4.9 (`AC-99`) |
| `RF-59` — `CLASSIFICACAO_MOBILIZACAO` de entrada para derivada, varredura de consumidores | R4.1.1 (decisão (a), justificativa completa) · R4.1.2 (varredura real, 8 arquivos) · R4.3 (project structure) · R4.4.1/R4.4.2 (contrato novo) · R4.8 (`EC-38`, mecanismo `mypy`) |
| `RF-60` — reescrita do teste estático, não relaxamento | R4.9.5 (o que o teste passa a provar) · R4.3 (arquivo mantido, conteúdo reescrito) |

**Cobertura desta fatia:** 8 de 8 requisitos (`RF-53`–`RF-60`). Nenhum
requisito da fatia 4A ficou sem seção correspondente. Nenhum item deste
plano existe sem requisito que o peça: `TIPO_ATIVO_FISICO` está ancorado em
`RF-56` (é o único jeito de `classificar_ativo_fisico` saber que está diante
de veículo, sem o qual o bloqueio de `OQ-38` seria inexprimível), e o
sentinela `None` de retorno está ancorado no mesmo requisito.

**Duas questões desta rodada permanecem com o especialista** (`OQ-38`,
listada em R4.10.1) **e uma leitura alternativa foi explicitamente
rejeitada** (`OQ-42`, discovery, não confirmada e não adotada). Nenhuma das
duas foi antecipada por implementação — `sdd.config.md` §6.

> Requisito sem cobertura é buraco no plano. Item de plano sem requisito é
> over-engineering.

---

# Rodada 4 — Necessidade Financeira Imediata, fatia 4B (2026-09-09)

> Escopo: `RF-61` a `RF-65` (spec §2, Rodada 4, fatia 4B). Fonte normativa
> congelada: `specs/motor-calculo.spec.md` §14.0/§14.1 (necessidade por
> dívida) e §14.2 (tratamento monetário de `ORDEM_ACOES`, trava de dupla
> contagem). **Pré-requisito satisfeito:** fatia 4A (`RF-53`–`RF-60`)
> concluída e verificada — `15/15` tarefas. Esta fatia não reabre a fatia
> 4A; `classificar_investimento`/`classificar_ativo_fisico`/`derivar_
> VALOR_LIQUIDO_REALIZAVEL_ATIVO(_DISPONIVEL)` não são consumidas aqui — 4B
> só depende de gates e status estratégico de dívida, não de classificação
> de ativo. Fora de escopo: ligação em `calcular_diagnostico` (fatia 4C,
> substituição do placeholder de `ATAQUE_IMEDIATO_RECOMENDADO`), qualquer
> trabalho em `app-aluno`, `OQ-38` (renda de veículo, fatia 4A) — spec §9,
> discovery `motor-calculo.discovery.md` (Rodada 4) §8.

## R4B.1. Architecture Overview

Nenhuma camada nova, nenhum ponto de I/O novo. Como a fatia 4A, esta fatia
**não** é puramente aditiva num ponto: `AcaoRequerida` (Rodada 2) ganha um
campo monetário novo que nenhum consumidor hoje espera — quebra de
contrato, não adição (`RF-61`), no mesmo padrão de cuidado de `RF-31`,
`RF-41` e `RF-59`. O restante (`NECESSIDADE_IMEDIATA_DIVIDA`/
`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`) é função pura nova, sem tocar
dataclass existente além de `AcaoRequerida`.

```text
 [0] ENTRADA — engine/gates.py, engine/estado.py (RF-61)
     AcaoRequerida ganha VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez
     (RF-61/RF-62/RF-63) — campo OBRIGATÓRIO, sem default (mesmo padrão de
     rigor de CLASSIFICACAO_MOBILIZACAO na Rodada 3/4A: nenhum ponto de
     construção pode "esquecer" o valor por omissão silenciosa).
     Todo ponto de construção de AcaoRequerida(...) (5 em engine/gates.py,
     1 em engine/motor.py) passa a fornecer o valor explicitamente.
                                            │
                                            ▼
 [1] CÁLCULO PURO — engine/gates.py (novo, dentro do módulo existente · RF-64/RF-65)
     ┌──────────────────────────────────────────────────────────────────┐
     │ NECESSIDADE_IMEDIATA_DIVIDA(...)             §14.1.1 → RF-64/65  │
     │ NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(...) §14.1  → RF-64     │
     └──────────────────────────────────────────────────────────────────┘
       ↑ TODAS as entradas por parâmetro (NFR Pureza · Rodada 4 — fatia 4B)
                                            │
                                            ▼
 [2] CONSUMO — fora de escopo desta fatia (fatia 4C)
     calcular_diagnostico continua devolvendo ATAQUE_IMEDIATO_RECOMENDADO
     = dinheiro(0) (placeholder inalterado). NECESSIDADE_FINANCEIRA_
     IMEDIATA_ELEGIVEL desta fatia é verificável isoladamente, com
     GATE_PENDENTE/DIVIDA_STATUS_ESTRATEGICO/VALOR_ACAO_FINANCEIRA_IMEDIATA/
     VALOR_RELEVANTE_PARA_QUITACAO fornecidos por parâmetro nos gabaritos.
```

**Dois pontos de mudança, e só dois:**

1. **`engine/gates.py`** — `AcaoRequerida` ganha o campo `VALOR_ACAO_
   FINANCEIRA_IMEDIATA` (`RF-61`–`RF-63`); os cinco pontos de construção
   internos ao módulo passam a fornecê-lo; duas funções novas,
   `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_
   ELEGIVEL`, são adicionadas ao mesmo arquivo (`RF-64`/`RF-65`, decisão
   `OQ-41`, R4B.1.2).
2. **`engine/motor.py`** — o único ponto de construção de `AcaoRequerida`
   fora de `gates.py` (`_acao_economia_se_houver`, ação de economia)
   também passa a fornecer o campo novo.

Mais a varredura completa de consumidores de `AcaoRequerida(` fora de
`engine/` (R4B.1.3) e a sinalização a `app-aluno` (`AC-110`).

**Nenhuma lei de arquitetura é violada.** `engine/` continua sem importar
`persistencia/`, `app/`, `collection/` ou `report/`; sem I/O; sem relógio;
sem parâmetro `P_*` embutido (nenhuma fórmula da §14.1/§14.2 usa parâmetro
calibrável — confirmado por leitura: a fórmula é seleção condicional e
soma, sem `MIN`/`MAX`/percentual ajustável). `NECESSIDADE_IMEDIATA_DIVIDA`
não importa de `engine/ataque_imediato.py`; a direção de import
permanece a mesma da fatia 4A (consumidores importam de módulos de
domínio, nunca o inverso).

### R4B.1.1. A primeira decisão desta fatia — mecanismo do campo monetário em `AcaoRequerida` (`OQ-39`)

Duas alternativas, identificadas pelo discovery (Rodada 4, §1.2) e por
`RF-61`, nenhuma decidida por fonte normativa — decisão técnica deste
plano (`sdd.config.md` §3: "`OQ-39`/`OQ-41` são decisão deste plano").

**(a) — Campo novo em `AcaoRequerida`**, preenchido no mesmo ponto em que
a ação já é construída (dentro dos gates 1–3 e da ação de economia).

**(b) — Campo novo em `Divida`** (`VALOR_ACAO_FINANCEIRA_IMEDIATA:
DinheiroTalvez`, ao lado de `VALOR_QUITACAO_HOJE`), consultado pelos gates
e por `NECESSIDADE_IMEDIATA_DIVIDA` antes/junto da decisão de gate.

**Decisão: (a).** Razões, uma a uma:

1. **A dependência de ordem que o discovery temia (§1.2) não se
   concretiza.** `NECESSIDADE_IMEDIATA_DIVIDA` não precisa do valor **antes**
   de os gates rodarem — ela precisa dele **depois**, junto com
   `GATE_PENDENTE`/`DIVIDA_STATUS_ESTRATEGICO`, que também só existem
   depois de `determinar_status_estrategico`/`particionar_elegibilidade`
   terem rodado (confirmado por leitura de `engine/gates.py:677-815`: os
   três dados — status estratégico, gate pendente, ação — são produzidos
   juntos, no mesmo `ResultadoGates`). Não há "ovo e galinha": os gates
   decidem o bloqueio, constroem a `AcaoRequerida` com o valor, e o
   resultado inteiro (incluindo a ação com valor) já está pronto quando
   `NECESSIDADE_IMEDIATA_DIVIDA` é chamada sobre aquele `ResultadoGates`.
2. **(a) é o mesmo padrão de contrato já estabelecido para o resto de
   `AcaoRequerida`** (`ACAO_ID`, `TIPO_ACAO`, `descricao`, `CAMPO_PENDENTE`
   — todos derivados no ponto de construção dentro de `gates.py`/
   `motor.py`, nunca coletados de `Divida` como dado bruto). Um campo
   monetário em `Divida` quebraria essa uniformidade sem necessidade: a
   `AcaoRequerida` já É o lugar onde "o que fazer e quanto custa" vive
   junto — dividir os dois entre duas dataclasses obrigaria todo
   consumidor a re-juntar `Divida.VALOR_ACAO_FINANCEIRA_IMEDIATA` com a
   `AcaoRequerida` correspondente por `DIVIDA_ID`, um join que hoje não
   existe em lugar nenhum do motor.
3. **(b) duplicaria informação sem necessidade e correria risco de
   divergência.** O discovery já nomeou isso (§1.2): `Divida.VALOR_
   QUITACAO_HOJE` e `Oportunidade.beneficio` já cobrem, parcialmente, dois
   dos casos que `VALOR_ACAO_FINANCEIRA_IMEDIATA` precisa expressar (Gate
   3/quitação e Gate 4/oportunidade). Um terceiro campo em `Divida` com
   semântica parecida ("valor da ação atual sobre esta dívida") criaria
   três lugares candidatos a "a fonte da verdade" para valores parecidos,
   sem a spec definir qual prevalece quando divergem. (a) evita esse
   problema porque a `AcaoRequerida` é construída **a partir** desses
   campos (quando aplicável) no ponto de construção — ela é sempre a
   derivação final, nunca uma terceira entrada independente.
4. **(b) é dado de entrada para algo que a §14.2.1 descreve como
   derivado** ("variável interna derivada... de valor já conhecido na
   operação, proposta, acordo, oportunidade, regularização ou
   intervenção"). Um campo de `Divida` é, por convenção desta base,
   informação que o usuário declara ou que entra bruta — nenhum dos
   outros campos "derivados pelo motor" vive em `Divida` (`DIVIDA_
   STATUS_ESTRATEGICO`/`GATE_PENDENTE` são saída de `ResultadoGates`,
   não campos de `Divida`, achado já registrado pelo discovery §1.1). (a)
   preserva essa separação: `Divida` continua sendo só entrada do
   usuário; tudo que o motor deriva vive na saída dos gates.
5. **Mecanismo de rede idêntico ao já usado por `RF-59`.** Como campo
   obrigatório sem default em `AcaoRequerida` (dataclass `frozen=True,
   slots=True`), qualquer ponto de construção que esquecer o argumento
   falha em `mypy --strict` (`unexpected keyword argument` ausente vira
   `missing argument`) — mecanismo de tipo, não convenção de equipe,
   mesmo argumento que decidiu `OQ-40` na fatia 4A (R4.1.1, ponto 3).

**Nome do campo: `VALOR_ACAO_FINANCEIRA_IMEDIATA`.** É o nome literal da
variável na §14.2.1/§14.2.2 — nenhuma tradução, nenhuma abreviação
(`sdd.config.md` §7). Confere com o padrão de nomenclatura de
`AcaoRequerida`: os campos canônicos citados pela spec são todos em
maiúsculo (`ACAO_ID`, `DIVIDA_ID`, `TIPO_ACAO`, `CAMPO_PENDENTE`); os três
campos em minúsculo (`descricao`, `gate_origem`, `prioridade_
excepcional`) são os que a Rodada 1/2 **não** nomeou a partir de uma
variável textual da canônica — são nomes de implementação. `VALOR_ACAO_
FINANCEIRA_IMEDIATA` é variável nomeada da §14, então segue o padrão
maiúsculo dos campos canônicos, não o de implementação.

**Tipo: `DinheiroTalvez`.** A §14.2.2 exige explicitamente que o valor
possa ser `DESCONHECIDO` ("VALOR_ACAO_FINANCEIRA_IMEDIATA = DESCONHECIDO").
`DinheiroTalvez = Dinheiro | Desconhecido` já existe (`engine/tipos.py`,
usado por `SALDO_DEVEDOR_ATUAL`, `VALOR_QUITACAO_HOJE`, `RESERVA_
MOBILIZAVEL` e os campos brutos de `ItemAtivo`/`ItemInvestimento` da fatia
4A) — reaproveita o sentinela já estabelecido, nenhum tipo-soma novo.
`None` é rejeitado pelo mesmo motivo já documentado em `engine/tipos.py`
("`None` é proibido para dado de negócio: significaria 'não perguntado'")
— aqui o valor **sempre se aplica** a toda `AcaoRequerida` (mesmo quando é
`0`, por não exigir desembolso), então não há caso de ausência estrutural
a expressar com `None`, diferente do que a fatia 4A precisou para
`RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None` (ali `None` significava
"a variável nem existe para este tipo de ativo"; aqui a variável sempre
existe, só pode ser desconhecida).

**Default: nenhum — campo obrigatório, sem valor implícito.** A §14.2.1 dá
uma regra binária exaustiva: sem desembolso → `dinheiro(0)`; com
desembolso e valor conhecido → o valor; com desembolso e valor
desconhecido → `DESCONHECIDO`. Não sobra nenhum quarto caso em que "não
informar" seria correto — logo um default (`dinheiro(0)` ou `None`)
disfarçaria a decisão de qual dos três ramos se aplica, em vez de forçar
quem constrói a `AcaoRequerida` a decidir. Isso vale também para
`TIPO_ACAO="INFORMACAO"` (Gate 1) e `TIPO_ACAO="RENEGOCIACAO"` sem
desembolso (parte do Gate 2/3): a lista de exemplos "sem desembolso" da
§14.2.1 já cita "solicitar documento, consultar proposta, renegociar,
conferir saldo" — exatamente os `TIPO_ACAO` que os Gates 1/2/3 emitem
hoje sem oferta de quitação vigente — então esses pontos de construção
fornecem `dinheiro(0)` explicitamente, não por omissão de default.

### R4B.1.2. A segunda decisão desta fatia — módulo de `NECESSIDADE_IMEDIATA_DIVIDA` (`OQ-41`)

Duas alternativas, identificadas pelo discovery (Rodada 4, §3) e por
`RF-64`, nenhuma decidida por fonte normativa.

**(a) — `engine/gates.py`**, perto de `ResultadoGates`/`ParticaoElegibilidade`.

**(b) — `engine/ataque_imediato.py`**, perto das outras funções da §13/§14.

**Decisão: (a).** Razões, uma a uma:

1. **`NECESSIDADE_IMEDIATA_DIVIDA` não é uma função de `Divida` isolada —
   é uma função de `ResultadoGates`** (confirmado pelo discovery §1.1 e
   por leitura de `engine/gates.py`: `GATE_PENDENTE` e `DIVIDA_STATUS_
   ESTRATEGICO` são campos de `ResultadoGates`, não de `Divida`). Colocar
   a função em `gates.py` significa que ela lê tipos que já são locais ao
   módulo — nenhum import novo de tipo é necessário para a função em si,
   só para os testes que a exercitam. Colocá-la em `ataque_imediato.py`
   exigiria importar `GATE_PENDENTE`, `DIVIDA_STATUS_ESTRATEGICO` (de
   `engine/tipos.py`, já importados por `ataque_imediato.py` hoje — sem
   custo adicional) e, mais relevante, o **conceito** de `ResultadoGates`
   (de `engine/gates.py`), que `ataque_imediato.py` não importa hoje.
2. **Análise do ciclo de import — confirmado por leitura direta, não
   suposição.** `engine/gates.py` importa apenas `engine/estado.py`,
   `engine/tipos.py` e `engine/valor_quitacao.py` — nenhuma ocorrência de
   `ataque_imediato`, `ciclo_mensal` ou `diagnostico` (`grep` no arquivo
   inteiro). O ciclo real documentado como `DT-01` (Rodada 3,
   `engine/diagnostico.py:792-803`) é `diagnostico.py` → import local de
   `ErroInvariante` (`engine/ciclo_mensal.py`) ← `ciclo_mensal.py` importa
   `Diagnostico` de `diagnostico.py` no topo do arquivo (`engine/
   ciclo_mensal.py:156`) — um ciclo fechado entre exatamente esses dois
   módulos, mais `ataque_imediato.py` como terceiro elo (`ataque_
   imediato.py` importa `ErroInvariante` de `ciclo_mensal.py` dentro de
   `verificar_hierarquia_ataque_imediato`, também import local, mesmo
   padrão de contorno). `gates.py` está **fora** desse grafo — não importa
   nenhum dos três, e nenhum dos três importa `gates.py`. Colocar
   `NECESSIDADE_IMEDIATA_DIVIDA` em `gates.py` **não cria e não agrava**
   `DT-01`: o módulo já é uma folha nesse grafo de import específico.
3. **(b) criaria uma dependência nova e assimétrica.** Hoje `ataque_
   imediato.py` importa de `engine/classificacao_ativos.py` (fatia 4A,
   direção nova mas documentada) e de `engine/ciclo_mensal.py` (import
   local, `DT-01`) — nunca de `engine/gates.py`. Se (b) fosse escolhida,
   seria a **primeira vez** que `ataque_imediato.py` importa de
   `gates.py` (confirmado: nenhuma ocorrência de `from engine.gates` ou
   `import engine.gates` em `engine/ataque_imediato.py` hoje). Isso não
   fecha ciclo (gates.py não precisaria importar de volta), mas contraria
   a docstring atual do módulo, que declara explicitamente "não recebe
   `Parametros` em nenhuma assinatura" e o padrão de "tudo por parâmetro,
   nunca de outro módulo de domínio" (discovery §3, citando `engine/
   ataque_imediato.py:1-45`). (a) preserva essa docstring intacta —
   `ataque_imediato.py` não muda nesta fatia.
4. **Unidade temática com a §14.1/§14.1.1.** A fórmula de `NECESSIDADE_
   IMEDIATA_DIVIDA` é, na prática, "o que os gates decidiram sobre esta
   dívida, resumido em um valor". Isso é semanticamente mais próximo de
   "o que os gates produzem" (`gates.py`) do que de "o que fazer com o
   dinheiro disponível" (`ataque_imediato.py`, §13). O mesmo critério de
   separação temática que a fatia 4A usou para justificar `engine/
   classificacao_ativos.py` como módulo à parte de `ataque_imediato.py`
   (R4.10, última linha da tabela) se aplica aqui na direção oposta: a
   função pertence ao módulo que já é dono do conceito que ela resume.
5. **Custo aceito.** `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (a soma
   sobre o inventário) também vive em `gates.py`, ao lado de
   `particionar_elegibilidade` — que já é o ponto natural de agregação
   sobre o inventário inteiro (`ParticaoElegibilidade` já agrega
   `elegiveis`/`ORDEM_ACOES`/`bloqueadas`; a soma de necessidade é mais um
   agregado do mesmo tipo). Isso divide a lógica normativa da §14 entre
   `gates.py` (§14.1/§14.1.1/§14.2) e `engine/classificacao_ativos.py`
   (§14.3–§14.12, fatia 4A) — aceito como trade-off explícito em R4B.10,
   pelo mesmo motivo que a fatia 4A já aceitou dividir §14 entre módulos.

### R4B.1.3. Varredura de consumidores de `AcaoRequerida(` — todos os pontos reais no repositório

`grep -rn "AcaoRequerida("` no repositório inteiro (não confiando em
números de linha de rodadas passadas):

| Arquivo | Linha | Constrói/consome | O que muda com `RF-61` |
| --- | --- | --- | --- |
| `engine/gates.py` | `:329` (Gate 1, `STATUS_DIVIDA=QUITADA_A_CONFIRMAR`) | constrói | `VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0)` — `TIPO_ACAO="INFORMACAO"` nunca exige desembolso (§14.2.1, lista de exemplos "sem desembolso" inclui "conferir saldo"/"solicitar documento") |
| `engine/gates.py` | `:364` (Gate 1, `VALOR_RELEVANTE_PARA_QUITACAO=DESCONHECIDO`) | constrói | `VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0)` — mesmo motivo acima |
| `engine/gates.py` | `:440` (Gate 2, risco com prioridade excepcional) | constrói | `VALOR_ACAO_FINANCEIRA_IMEDIATA` conforme §14.2.1: se a contenção do risco tiver valor monetário conhecido associado (ex.: quitação que é a própria contenção, `EC-15`), o valor; senão `dinheiro(0)` (ação de "renegociar"/"conferir" sem desembolso) — este módulo não tem hoje um valor de contenção pronto para ler, então o ponto de construção usa `dinheiro(0)` nesta fatia (nenhuma oferta de valor de contenção é modelada em `Divida`/`ResultadoGates` — não inventar um valor que a spec não pede aqui) |
| `engine/gates.py` | `:457` (Gate 2, risco sem prioridade excepcional) | constrói | `VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0)` — mesmo raciocínio acima, ação é "renegociar"/"desviar para ação", sem oferta de valor conhecida neste ponto |
| `engine/gates.py` | `:553` (Gate 3, transformação — renegociação/troca) | constrói | `VALOR_ACAO_FINANCEIRA_IMEDIATA`: se `TIPO_ACAO="TROCA"` ou `"RENEGOCIACAO"` e existir valor de proposta/oferta vigente conhecido (`Divida.VALOR_QUITACAO_HOJE` quando `STATUS_VALIDADE_PROPOSTA=VIGENTE`), usar esse valor; senão `dinheiro(0)` (sem oferta vigente, a ação é só negociar/formalizar, sem desembolso) — este é o único dos cinco pontos de `gates.py` em que a §14.2.1 ("derivado de valor já conhecido na... proposta") tem, hoje, um candidato real em `Divida` para consultar |
| `engine/motor.py` | `:200` (`_acao_economia_se_houver`) | constrói | `VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0)` — `TIPO_ACAO="ECONOMIA"` não é ação de dívida, não exige desembolso (a economia é comportamental, não uma compra) |
| `persistencia/arquivo/repositorio_snapshots.py` | `:621` (`_acao_requerida`, desserialização) | constrói (a partir de JSON) | `VALOR_ACAO_FINANCEIRA_IMEDIATA=_dinheiro_talvez(bruto["VALOR_ACAO_FINANCEIRA_IMEDIATA"])` — novo campo lido do dict serializado; `_serializar_canonico` (`engine/snapshot.py`) já serializa por nome de campo genericamente (confirmado pelo comentário existente em `_acao_requerida`: "nenhuma mudança necessária do lado da serialização"), então só a leitura de volta precisa do campo novo, mesmo padrão de `T-92` |
| `tests/regras/test_repositorio_snapshots.py` | `:230`, `:239` (`acao_gate_1`, `acao_economia`) | constrói (fixture) | Ambas as fixtures ganham `VALOR_ACAO_FINANCEIRA_IMEDIATA` explícito, exercitando o round-trip de serialização do campo novo |
| `tests/regras/test_ordem.py` | `:206` (`acao`) | constrói (fixture) | Ganha o argumento — `mypy --strict` acusa se esquecido (`EC-47`) |
| `tests/estatica/test_tipo_acao_apenas_quatro_valores.py` | `:122` (`acao_com_quinto_literal`) | constrói (fixture de teste negativo) | Ganha o argumento; o teste continua provando domínio fechado de `TIPO_ACAO`, não afetado pelo campo novo |
| `report/plano.py` | `:406` (`ContextoAcaoRequerida(...)`) | **lê**, não constrói `AcaoRequerida` diretamente | Lê só `DIVIDA_ID`, `descricao`, `prioridade_excepcional` de `acao` — não lê o campo novo. Não quebra (`mypy --strict` não acusa leitura parcial de dataclass), mas fica **sem exibir** o valor da ação financeira imediata; fora de escopo desta fatia acrescentar esse campo a `ContextoAcaoRequerida` (a spec não pede mudança em `report/` — nenhum `RF-61`–`RF-65` menciona `report/`). Citado aqui só para a varredura ficar completa, não como item a corrigir |
| `app-aluno` (slug externo) | — | **consome** `AcaoRequerida` desde a Rodada 2 (`RF-28`–`RF-35`) | **Não é corrigido por este slug** (fora do repositório deste plano). Sinalização formal: qualquer ponto de `app-aluno` que desserializa/espelha o shape de `AcaoRequerida` (hash congelado citado pela spec §5, "Compatibilidade de contrato — Rodada 4 — fatia 4B") precisa de atualização coordenada quando esta fatia for implementada — mesmo procedimento de coordenação já usado para `RF-31`/`RF-41`/`RF-59` (`AC-110`) |

**Não é consumidor a corrigir:** `tests/regras/test_motor.py:410` menciona
`AcaoRequerida(TIPO_ACAO='INFORMACAO')` apenas em comentário explicativo,
não como código executado — citado aqui pela mesma disciplina de não
deixar órfão da varredura que a fatia 4A já seguiu (R4.1.2) para
`tests/app_aluno/estatica/test_sem_patrimonio_derivado_em_app.py`.

**Mecanismo de rede.** `mypy --strict` (comando `build`) falha em
**todos** os pontos de construção acima com `missing argument
"VALOR_ACAO_FINANCEIRA_IMEDIATA"` assim que o campo for adicionado sem
default — antes mesmo de rodar teste (`EC-47`). Procedimento idêntico ao
já usado em `R3.10.2`/`R4.1.2`: adicionar o campo, rodar `build`, corrigir
cada acusação da lista acima, `test` roda por último.

## R4B.2. Tech Stack

**Nenhuma dependência nova.** Mesma stdlib das rodadas anteriores
(`decimal`, `dataclasses`, `enum`) — confirmado por leitura de
`engine/gates.py`, `engine/tipos.py`, `engine/motor.py`.

| Escolha | Uso | Justificativa (ancorada em `RF-NN`) |
| --- | --- | --- |
| `DinheiroTalvez = Dinheiro \| Desconhecido` (já existente) | `VALOR_ACAO_FINANCEIRA_IMEDIATA`, retorno de `NECESSIDADE_IMEDIATA_DIVIDA` | `RF-62`/`RF-63`, NFR "Dados desconhecidos nunca viram zero silenciosamente (Rodada 4 — fatia 4B)". Reaproveita o sentinela já usado por `RESERVA_MOBILIZAVEL`/`SALDO_DEVEDOR_ATUAL`/campos brutos da fatia 4A — nenhum mecanismo novo. Alternativa descartada: `Optional[Decimal]` (`None` proibido para dado de negócio sempre-aplicável, `RF-16`, R4B.1.1) |
| `Decimal` via `engine/precisao.dinheiro()` (já em uso) | `VALOR_ACAO_FINANCEIRA_IMEDIATA` conhecido, soma de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` | NFR "Tolerância zero" desta fatia (spec §4, nota da Rodada 4 — fatia 4B: "seleção condicional e soma exatas"). `float` produziria erro de representação binária, inaceitável sob tolerância zero. Alternativa descartada: `float`, já proibida pelo teste estático `test_sem_float_no_motor.py` |
| `STATUS_METODO.PROVISORIO` (já existente, `engine/tipos.py`) | Sinalização de `RF-63`/`AC-109` (§14.2.2, "STATUS_ATAQUE_IMEDIATO = PROVISORIO ou equivalente já existente no modelo de status") | `RF-63` pede investigar um equivalente existente antes de propor campo novo (§14.2.2 é explícita: "ou equivalente já existente"). `STATUS_METODO` já modela exatamente esse par `DEFINITIVO_NA_DATA`/`PROVISORIO` (`engine/tipos.py:143-147`, usado por `S-01`–`S-05`). Nenhum novo enum `STATUS_ATAQUE_IMEDIATO` é criado nesta fatia — ver R4B.6.1 para o mecanismo completo de propagação. Alternativa descartada: enum novo dedicado, rejeitado por criar um terceiro conceito de "provisório" no motor quando um já existe e serve |
| Função pura, tipo `ResultadoGates`/`Divida` por parâmetro (já em uso, padrão de `engine/ataque_imediato.py` e de `engine/gates.py`) | `NECESSIDADE_IMEDIATA_DIVIDA`, `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` | NFR "Pureza (Rodada 4 — fatia 4B)": entradas por parâmetro (`GATE_PENDENTE`, `DIVIDA_STATUS_ESTRATEGICO`, `VALOR_ACAO_FINANCEIRA_IMEDIATA`, `VALOR_RELEVANTE_PARA_QUITACAO`), nada lido de `EstadoFinanceiro`/`Diagnostico`/relógio/arquivo/global — é o que torna `GAB-NFI-01` a `GAB-NFI-05` verificáveis sem `OQ-43` (fatia 4C) |
| `mypy --strict` (comando `build`, já em uso) | varredura de consumidores de `RF-61` | Mecanismo de rede que torna o campo obrigatório sem default verificável por máquina (`EC-47`), mesma técnica de `RF-31`/`RF-41`/`RF-59` |

**Contagem de dependências novas desta fatia: 0.**

## R4B.3. Project Structure

| Caminho | Mudança | Novo? |
| --- | --- | --- |
| `engine/gates.py` | `AcaoRequerida` ganha `VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez` (sem default); os cinco pontos de construção internos fornecem o valor (R4B.1.3); duas funções novas — `NECESSIDADE_IMEDIATA_DIVIDA`, `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (§14.1/§14.1.1, `RF-64`/`RF-65`); `REGRAS: Final[tuple[str, ...]]` do módulo ganha `"§14.1"`, `"§14.1.1"`, `"§14.2.1"`, `"§14.2.2"`, `"§14.2.3"` | não |
| `engine/motor.py` | `_acao_economia_se_houver` fornece `VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0)` (R4B.1.3) | não |
| `engine/tipos.py` | Nenhuma mudança — `DinheiroTalvez`, `STATUS_METODO.PROVISORIO` já existem | não |
| `persistencia/arquivo/repositorio_snapshots.py` | `_acao_requerida` (R4B.1.3): lê o campo novo do dict serializado | não |
| `tests/regras/test_repositorio_snapshots.py`, `test_ordem.py` | fixtures de `AcaoRequerida` retipadas (R4B.1.3) | não |
| `tests/estatica/test_tipo_acao_apenas_quatro_valores.py` | fixture de teste negativo retipada (R4B.1.3) | não |
| `tests/regras/test_necessidade_imediata.py` | **arquivo novo** — `AC-101`–`AC-109`, `AC-111` (`GAB-NFI-01` a `GAB-NFI-05`, precedência forçada `AC-106`, trava de dupla contagem `AC-111`, incompletude `AC-108`, sinalização provisória `AC-109`) | **sim** |
| `tests/estatica/test_acao_requerida_tem_valor_financeiro.py` | **arquivo novo** — `AC-110`: audita por AST que toda construção de `AcaoRequerida(...)` em `engine/` fornece `VALOR_ACAO_FINANCEIRA_IMEDIATA` (mecanismo de rede complementar ao `mypy --strict`, mesmo espírito de `test_sem_float_no_motor.py` — prova estrutural, não só o comando `build`) | **sim** |
| `pyproject.toml` | nenhuma mudança de marcador — testes entram em `tests/regras/` e `tests/estatica/`, sem categoria nova | não |

**Nota de escopo.** Nenhum arquivo de `app/`, `collection/` ou `report/` é
tocado por esta fatia. `report/plano.py` é sinalizado (R4B.1.3), não
editado — a spec não pede exibição do valor no relatório nesta fatia.
`app/montagem/estado.py` (se existir em `app-aluno`) e o hash congelado
daquele slug são sinalizados, não editados — mesma disciplina de
coordenação das Rodadas 2, 3 e 4A.

## R4B.4. Data Model

Contratos e assinaturas. Nomes de campo idênticos à §14, caractere por
caractere (`sdd.config.md` §7). Corpo de função é escopo de
`/sdd:implement`.

### R4B.4.1. `AcaoRequerida` — campo monetário novo (`RF-61`)

```python
# engine/gates.py — RF-61, RF-62, RF-63 · §14.2.1, §14.2.2
@dataclass(frozen=True, slots=True)
class AcaoRequerida:
    """... (docstring existente preservada; nota da Rodada 4 — fatia 4B
    acrescentada abaixo, mesmo padrão das notas de Rodada 2/3 já presentes)

    Rodada 4 — fatia 4B (`RF-61`, §14.2.1/§14.2.2, `OQ-39` — decisão R4B.1.1):
    ganha `VALOR_ACAO_FINANCEIRA_IMEDIATA`, campo OBRIGATÓRIO sem default —
    quebra de contrato, não adição (mesmo padrão de `RF-31`/`RF-41`/`RF-59`).
    Representa o valor monetário necessário à execução desta ação: `0`
    quando não há desembolso; o valor conhecido quando há desembolso e o
    valor é conhecido; `DESCONHECIDO` quando há desembolso e o valor não é
    conhecido. Nunca `None` — a variável sempre se aplica a toda ação,
    mesmo quando o valor é `0`.
    """

    ACAO_ID: str
    DIVIDA_ID: str | None
    TIPO_ACAO: str
    descricao: str
    gate_origem: Literal[1, 2, 3] | None
    VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez  # RF-61/RF-62/RF-63 · §14.2.1/§14.2.2
    prioridade_excepcional: bool = False
    CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"] | None = None
```

> **Posicionamento do campo novo.** `VALOR_ACAO_FINANCEIRA_IMEDIATA` entra
> **antes** dos dois campos que já têm default (`prioridade_excepcional`,
> `CAMPO_PENDENTE`) — uma dataclass Python não aceita campo sem default
> depois de campo com default. Isso significa que esta mudança, embora
> aditiva na intenção, é **posicional** para qualquer chamador que use
> argumento posicional em vez de nomeado. Varredura de R4B.1.3 confirma:
> todo ponto de construção real do repositório já usa argumento **nomeado**
> (`ACAO_ID=...`, `DIVIDA_ID=...` etc.) — nenhuma chamada posicional pura
> de `AcaoRequerida(...)` foi encontrada em `engine/`, `persistencia/` nem
> `tests/`. O risco posicional é, portanto, teórico para este repositório,
> mas é registrado explicitamente porque `app-aluno` (fora deste
> repositório) pode não seguir a mesma convenção — reforça a necessidade
> da sinalização de `AC-110`.

### R4B.4.2. `NECESSIDADE_IMEDIATA_DIVIDA` / `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (`RF-64`, `RF-65`)

```python
# engine/gates.py — RF-64, RF-65 · §14.1, §14.1.1, §14.2.3
def NECESSIDADE_IMEDIATA_DIVIDA(
    *,
    GATE_PENDENTE: GATE_PENDENTE,
    DIVIDA_STATUS_ESTRATEGICO: DIVIDA_STATUS_ESTRATEGICO,
    acao_financeira_imediata_executavel: AcaoRequerida | None,
    VALOR_RELEVANTE_PARA_QUITACAO: DinheiroTalvez,
) -> DinheiroTalvez: ...
    # §14.1.1 · RF-64/RF-65 · AC-101–AC-107, AC-111
    # Cadeia if/elif ESTRITA, cinco ramos, nesta ordem exata:
    #   1. GATE_PENDENTE is GATE_PENDENTE.INFORMACAO        -> dinheiro(0)
    #   2. GATE_PENDENTE is GATE_PENDENTE.TRANSFORMACAO      -> dinheiro(0)
    #   3. acao_financeira_imediata_executavel is not None
    #      and seu VALOR_ACAO_FINANCEIRA_IMEDIATA is not DESCONHECIDO
    #                                                        -> esse valor
    #      (inclui o ramo DESCONHECIDO — RF-63/AC-109: se a ação existe,
    #      é executável agora e o valor é DESCONHECIDO, o retorno desta
    #      função também é DESCONHECIDO, propagado até a soma)
    #   4. DIVIDA_STATUS_ESTRATEGICO in
    #      {PRONTA_PARA_ORDENACAO, EM_ATAQUE}                -> VALOR_RELEVANTE_
    #                                                           PARA_QUITACAO
    #                                                           INTEGRAL (AC-107)
    #   5. senão                                              -> dinheiro(0)
    # RF-65/AC-111 (trava de dupla contagem): ramos 3 e 4 são MUTUAMENTE
    # EXCLUSIVOS por construção da cadeia if/elif — nunca ambos avaliados
    # para a mesma chamada. Ver R4B.6.1 para a prova de que isso não é
    # verificação extra, é consequência estrutural da ordem.


def NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(
    *, particao: ParticaoElegibilidade, acoes_por_divida: Mapping[str, AcaoRequerida],
) -> DinheiroTalvez: ...
    # §14.1 · RF-64 · AC-108
    # Σ NECESSIDADE_IMEDIATA_DIVIDA(d) sobre TODAS as dívidas do inventário
    # (elegíveis E bloqueadas — RF-64 não restringe a soma às elegíveis;
    # dívidas com Gate 1/3 pendente contribuem 0 pela própria fórmula do
    # ramo 1/2, então a soma sobre o inventário inteiro e a soma só sobre
    # bloqueadas+elegíveis produzem o mesmo resultado numérico).
    # AC-108: se QUALQUER NECESSIDADE_IMEDIATA_DIVIDA(d) is DESCONHECIDO,
    # o resultado desta função é DESCONHECIDO — NUNCA soma parcial
    # apresentada como total definitivo. Propagação, não fallback.
```

> **Assinatura exata de `NECESSIDADE_IMEDIATA_DIVIDA` — nota de leitura.**
> A §14.1.1 fala em "existe ação financeira imediata, decorrente de Gate 2
> ou Gate 4, executável agora". `ResultadoGates.acao` (produzido pelos
> Gates 1–3) e `Oportunidade`/Gate 4 (avaliado por `aplicar_gate_4_
> oportunidade`, que nunca bloqueia — EC-16) são as duas fontes possíveis
> de "ação financeira imediata executável agora". Esta fatia não modela
> Gate 4 como produtor de `AcaoRequerida` (fora do escopo lido em
> `engine/gates.py`: `aplicar_gate_4_oportunidade` sempre devolve `None`
> hoje, e nenhum `RF-61`–`RF-65` pede que ele passe a emitir ação) — o
> parâmetro `acao_financeira_imediata_executavel` desta fatia é
> alimentado apenas pelas ações de Gate 2/3 que `ResultadoGates.acao` já
> produz quando `gate_origem in {2, 3}`. Isso é suficiente para os cinco
> gabaritos `GAB-NFI-01`–`GAB-NFI-05` (nenhum deles exercita Gate 4 com
> ação own). Se uma rodada futura fizer o Gate 4 emitir `AcaoRequerida`,
> o mesmo parâmetro já a aceita sem mudança de assinatura.

## R4B.5. Data Flow

1. `particionar_elegibilidade(dividas)` roda como já roda hoje (Rodada 1),
   produzindo `ParticaoElegibilidade` com `elegiveis`, `ORDEM_ACOES`
   (cada item já com `VALOR_ACAO_FINANCEIRA_IMEDIATA` preenchido, R4B.1.3)
   e `bloqueadas` (cada `ResultadoGates` com `GATE_PENDENTE`/`DIVIDA_
   STATUS_ESTRATEGICO`/`acao` já resolvidos).
2. Para cada dívida do inventário completo, `NECESSIDADE_IMEDIATA_DIVIDA`
   é chamada com o `GATE_PENDENTE`/`DIVIDA_STATUS_ESTRATEGICO` daquela
   dívida (lidos do `ResultadoGates` correspondente, elegível ou
   bloqueada), a `AcaoRequerida` associada quando existir, e `VALOR_
   RELEVANTE_PARA_QUITACAO` (já composto por `compor_VALOR_RELEVANTE_
   PARA_QUITACAO`, reaproveitado do cálculo de gate — nenhuma recomposição
   nesta fatia).
3. `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` soma o passo 2 sobre o
   inventário inteiro, propagando `DESCONHECIDO` se qualquer parcela for
   desconhecida (`AC-108`).
4. **Esta fatia para aqui.** O resultado do passo 3 não é consumido por
   `calcular_diagnostico` nem por `engine/motor.py` nesta fatia — é
   verificável isoladamente por teste de função pura (`GAB-NFI-01`–
   `GAB-NFI-05`), com os passos 1–2 fornecidos como dado de entrada
   construído no próprio teste, não como pipeline real executado.
   `ATAQUE_IMEDIATO_RECOMENDADO` continua `dinheiro(0)` até a fatia 4C.

**Falha em cada etapa:**

- Passo 1 falhando (gate mal aplicado): fora de escopo desta fatia —
  comportamento de `particionar_elegibilidade` é responsabilidade da
  Rodada 1, já coberta por gabaritos existentes.
- Passo 2: se `GATE_PENDENTE`/`DIVIDA_STATUS_ESTRATEGICO` forem
  inconsistentes entre si (ex.: `GATE_PENDENTE=NENHUM` mas `DIVIDA_
  STATUS_ESTRATEGICO=INTERVENCAO_PENDENTE`), a função não valida essa
  consistência — ela confia no contrato que `determinar_status_
  estrategico` já garante (os dois campos são produzidos juntos, no
  mesmo `ResultadoGates`, pela mesma função). Não há caminho para os dois
  divergirem sem um bug em código já existente e já testado.
- Passo 3: `DESCONHECIDO` se propaga; nenhuma exceção é levantada —
  consistente com o padrão de toda a base (`DESCONHECIDO` é valor, não
  erro).

## R4B.6. External Interfaces

Nenhuma interface externa nova. Esta fatia não introduz endpoint, banco
nem arquivo novo — estende contratos internos do motor.

### R4B.6.1. `STATUS_ATAQUE_IMEDIATO = PROVISORIO` — o mecanismo concreto (`RF-63`, `AC-109`)

A §14.2.2 pede investigar "equivalente já existente no modelo de status"
antes de propor campo novo. Achado: `STATUS_METODO` (`engine/tipos.py:
143-147`, já usado por `S-01`–`S-05`, Rodada 1) já modela exatamente o par
`DEFINITIVO_NA_DATA`/`PROVISORIO` que a §14.2.2 pede — é o "status de
plano provisório por dado ausente" que a base já usa para o método
recomendado inteiro.

**Decisão: reaproveitar `STATUS_METODO.PROVISORIO`, sem criar
`STATUS_ATAQUE_IMEDIATO` como enum novo.** Mecanismo: quando `NECESSIDADE_
IMEDIATA_DIVIDA(d)` retorna `DESCONHECIDO` (ramo 3 da cadeia, ação
financeira imediata com valor desconhecido) **e** essa ação tem
precedência material sobre o uso do caixa (a própria condição "valor
desconhecido" já implica isso: se o motor não sabe quanto reservar, não
pode saber quanto sobra para outra dívida sem reservar demais ou de
menos), `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` do inventário inteiro
vira `DESCONHECIDO` (`AC-108`, propagação já decidida em R4B.4.2). Como
`ATAQUE_IMEDIATO_RECOMENDADO = MIN(NECESSIDADE_FINANCEIRA_IMEDIATA_
ELEGIVEL, RECURSOS_ESTRATEGICAMENTE_RECOMENDADOS)` (§14.2.4, fórmula da
Rodada 3, preservada), um `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`
desconhecido torna `ATAQUE_IMEDIATO_RECOMENDADO` não calculável com
certeza — que é, por definição da base já estabelecida (Rodada 1, `S-01`–
`S-05`), o critério que rebaixa `STATUS_METODO` para `PROVISORIO`.

**Esta fatia não liga esse mecanismo em `STATUS_METODO` de verdade** — a
ligação depende de `calcular_diagnostico`/o ponto que monta `SnapshotOrdem`
(fatia 4C, `OQ-43`). O que esta fatia garante é que o **dado** existe e se
propaga corretamente (`DESCONHECIDO` sobe até `NECESSIDADE_FINANCEIRA_
IMEDIATA_ELEGIVEL`, `AC-108`/`AC-109`) — a consequência de status é
consumida, não produzida, por esta fatia. `AC-109` é verificado nesta
fatia apenas até o ponto de "o resultado é o estado desconhecido" — a
segunda metade de `AC-109` ("e o status... é sinalizado como provisório")
é verificada quando a fatia 4C ligar o mecanismo, não antes. Isso é
coerente com a nota de escopo da spec §7: "esta fatia não liga o
resultado a `calcular_diagnostico`".

## R4B.7. State Management

Sem estado próprio, sem cache, sem memoização — mesmo padrão de
`engine/gates.py` e `engine/ataque_imediato.py` hoje. `NECESSIDADE_
IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` são funções
puras chamadas a cada recálculo do motor (quando a fatia 4C as ligar).

## R4B.8. Error Handling Strategy

| Situação | Detecção | Resposta | Recuperação |
| --- | --- | --- | --- |
| Consumidor antigo tenta construir `AcaoRequerida(...)` sem `VALOR_ACAO_FINANCEIRA_IMEDIATA` (`EC-47`) | `mypy --strict` (comando `build`) — `missing argument` | Falha antes de `test` rodar | Fornecer o valor conforme R4B.1.3 (tabela lista todos os pontos) |
| `VALOR_ACAO_FINANCEIRA_IMEDIATA is DESCONHECIDO` em ação executável agora com precedência material | `NECESSIDADE_IMEDIATA_DIVIDA` retorna `DESCONHECIDO` para aquela dívida (ramo 3) | `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` do inventário vira `DESCONHECIDO` (`AC-108`) — nunca soma parcial apresentada como total | Ligação com `STATUS_METODO=PROVISORIO` fica para a fatia 4C (R4B.6.1) |
| Dívida satisfaz mais de um ramo de `NECESSIDADE_IMEDIATA_DIVIDA` simultaneamente (`EC-40`, `AC-106`) | Cadeia `if`/`elif` estrita — o primeiro ramo que casar decide, os demais nunca são avaliados | Resultado determinístico, sem ambiguidade | Não aplicável — não é erro, é o comportamento normativo |
| `AcaoRequerida` de Gate 2/3 sem oferta de valor conhecida no ponto de construção (a maioria dos 5 pontos de `gates.py`, R4B.1.3) | — | `VALOR_ACAO_FINANCEIRA_IMEDIATA=dinheiro(0)` explícito (ação sem desembolso) | Não é erro — é o ramo "sem desembolso" da §14.2.1, aplicado corretamente |

## R4B.9. Testing Strategy

- **Unitários (`tests/regras/test_necessidade_imediata.py`):**
  - `GAB-NFI-01`–`GAB-NFI-05` (`AC-101`–`AC-105`), um teste por gabarito,
    valores literais do documento canônico.
  - `AC-106` — precedência forçada: dívida construída para satisfazer
    simultaneamente Gate 1 pendente **e** `DIVIDA_STATUS_ESTRATEGICO`
    elegível; verifica que o resultado é `0` (ramo 1 vence), não o valor
    do ramo 4. Mesmo padrão de teste de precedência forçada que `AC-95`/
    `AC-96` já exigiram na fatia 4A.
  - `AC-107` — `VALOR_RELEVANTE_PARA_QUITACAO` entra integral: teste que
    fornece um valor alto e confirma que nenhuma fração é aplicada.
  - `AC-108` — incompletude material: inventário com uma dívida
    `DESCONHECIDO`, verifica que a soma total também é `DESCONHECIDO`,
    não a soma das conhecidas.
  - `AC-109` — metade verificável nesta fatia: `VALOR_ACAO_FINANCEIRA_
    IMEDIATA=DESCONHECIDO` produz `NECESSIDADE_IMEDIATA_DIVIDA=
    DESCONHECIDO` (a parte de sinalização de status fica para a fatia 4C,
    R4B.6.1 — o teste desta fatia não afirma nada sobre `STATUS_METODO`).
  - `AC-111` — auditoria: teste que constrói uma dívida com `VALOR_ACAO_
    FINANCEIRA_IMEDIATA` e `VALOR_RELEVANTE_PARA_QUITACAO` ambos
    positivos e diferentes, e confirma que o resultado é exatamente um
    dos dois, nunca a soma (mesmo caso de `AC-104`, adicionado aqui como
    prova de auditoria de código, não só caso feliz).
- **Estático (`tests/estatica/test_acao_requerida_tem_valor_financeiro.py`,
  `AC-110`):** varredura AST de `engine/` confirmando que toda chamada a
  `AcaoRequerida(...)` fornece `VALOR_ACAO_FINANCEIRA_IMEDIATA` — prova
  estrutural complementar ao `mypy --strict`, mesmo espírito de `test_
  sem_float_no_motor.py`/`test_sem_derivacao_de_classificacao_
  mobilizacao.py` (fatia 4A).
- **Não-regressão (mesmo procedimento de `AC-56`–`AC-59`/`AC-87`):**
  reexecutar `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes depois da
  mudança de `AcaoRequerida` — o campo novo entra em `hash_inputs` de todo
  snapshot que contenha `ORDEM_ACOES` não vazia, então qualquer gabarito
  que exercite Gate 1/2/3 precisa reexecutar para confirmar que só o hash
  muda, não o resultado numérico/de ordem/de status.
- **Integração:** fora de escopo — a integração com `calcular_diagnostico`
  é fatia 4C.
- **Fora de teste automatizado:** a segunda metade de `AC-109`
  (sinalização real de `STATUS_METODO=PROVISORIO` no snapshot) — depende
  da fatia 4C existir para ter algo a testar ponta a ponta.

## R4B.10. Risks & Trade-offs

| Decisão | Alternativa descartada | Por quê | Risco assumido |
| --- | --- | --- | --- |
| `VALOR_ACAO_FINANCEIRA_IMEDIATA` como campo novo em `AcaoRequerida`, sem default (decisão (a), R4B.1.1) | (b) campo novo em `Divida`, consultado pelos gates | (b) duplicaria semântica já parcialmente coberta por `VALOR_QUITACAO_HOJE`/`Oportunidade.beneficio`, sem a spec definir qual prevalece se divergirem; (a) mantém `AcaoRequerida` como o único lugar onde "o que fazer e quanto custa" vive junto, mesmo padrão já usado pelos demais campos derivados da dataclass | Mudança **posicional** de contrato (o campo sem default precisa entrar antes dos campos com default) — mitigado porque toda construção real no repositório já usa argumento nomeado (R4B.4.1); risco permanece teórico para `app-aluno`, coberto pela sinalização de `AC-110` |
| `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` em `engine/gates.py` (decisão (a), R4B.1.2) | (b) em `engine/ataque_imediato.py` | `gates.py` já é dono dos tipos que a função lê (`GATE_PENDENTE`, `DIVIDA_STATUS_ESTRATEGICO`, `ResultadoGates`) — zero import novo; (b) seria a primeira vez que `ataque_imediato.py` importa de `gates.py`, contrariando a docstring atual do módulo ("não depende de outro módulo de domínio") | Lógica normativa da §14 fica dividida entre `gates.py` (§14.1/§14.2) e `classificacao_ativos.py` (§14.3–§14.12, fatia 4A) — mesmo trade-off que a fatia 4A já aceitou ao separar `classificacao_ativos.py` de `ataque_imediato.py`; mitigado por `REGRAS` citando a subseção normativa em cada módulo |
| Trava de dupla contagem (`RF-65`) implementada como **consequência estrutural** da cadeia `if`/`elif` de `NECESSIDADE_IMEDIATA_DIVIDA`, não como verificação extra separada | Função que calcula os dois valores (`VALOR_ACAO_FINANCEIRA_IMEDIATA` e `VALOR_RELEVANTE_PARA_QUITACAO`) e depois escolhe um por `if` externo, ou uma trava explícita ("assert não soma os dois") rodando depois do cálculo | A cadeia `if`/`elif` já torna os ramos 3 e 4 mutuamente exclusivos por construção — nenhuma chamada passa pelos dois ramos na mesma execução. Uma trava separada seria redundante (checaria algo que a estrutura já impede) e adicionaria superfície de código sem reduzir risco real — o risco de dupla contagem só existiria se alguém reescrevesse a função fora da cadeia estrita, caso que `AC-111` (auditoria de código) já cobre sem precisar de trava em runtime | Nenhuma verificação em runtime além do teste (`AC-111`) — aceito porque a auditoria estática (leitura de código + teste que força os dois ramos com valores diferentes) é suficiente para provar a propriedade estrutural, mesmo padrão que `AC-106` já usa para provar precedência |
| `STATUS_METODO.PROVISORIO` reaproveitado para `RF-63`/`AC-109`, sem enum `STATUS_ATAQUE_IMEDIATO` novo | Enum novo dedicado a status de ataque imediato | A §14.2.2 pede explicitamente investigar equivalente existente antes de propor novo; `STATUS_METODO` já modela o mesmo par `DEFINITIVO_NA_DATA`/`PROVISORIO` com o mesmo significado ("resultado não calculável com certeza por dado ausente") | Esta fatia só garante a propagação do dado (`DESCONHECIDO` sobe até `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`); a ligação real com `STATUS_METODO` no snapshot fica para a fatia 4C — mitigado por R4B.6.1 documentar exatamente onde a costura acontece |
| `NECESSIDADE_IMEDIATA_DIVIDA` não modela Gate 4/`Oportunidade` como fonte de ação executável (só Gate 2/3) | Estender `aplicar_gate_4_oportunidade` para emitir `AcaoRequerida` nesta fatia | `aplicar_gate_4_oportunidade` hoje sempre devolve `None` (EC-16, Rodada 1) e nenhum `RF-61`–`RF-65` pede que isso mude; os cinco gabaritos desta fatia não exercitam Gate 4 com ação própria | Se uma rodada futura decidir que Gate 4 deve emitir `AcaoRequerida`, a assinatura de `NECESSIDADE_IMEDIATA_DIVIDA` (parâmetro `acao_financeira_imediata_executavel: AcaoRequerida \| None`) já aceita isso sem mudança — risco assumido é documentação, não código a refazer |
| `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` soma sobre o inventário inteiro (elegíveis + bloqueadas), não só sobre `elegiveis` | Somar só sobre `ParticaoElegibilidade.elegiveis` | Dívidas bloqueadas por Gate 1/3 contribuem `0` pela própria fórmula (ramos 1/2) — somar sobre o inventário inteiro ou só sobre elegíveis dá o mesmo resultado numérico, mas somar sobre o inventário inteiro é mais direto (não exige reconciliar `elegiveis` com `bloqueadas` para achar toda dívida) e bate literalmente com "para todas as dívidas do inventário" (§14.1) | Nenhum — as duas abordagens são matematicamente equivalentes; a escolha é só question de qual fonte de dados é mais direta de iterar |

### R4B.10.1. Ambiguidade de negócio registrada, não decidida

| Achado | Por que não é decisão deste plano | Impacto |
| --- | --- | --- |
| Nos pontos de construção do Gate 2 (`engine/gates.py:440`, `:457`), a §14.2.1 permite que uma ação de contenção de risco tenha valor monetário conhecido (ex.: quitação que é a própria contenção, `EC-15`), mas `Divida`/`ResultadoGates` não modelam hoje nenhum campo de "valor de contenção" para o motor consultar nesse ponto específico — só `VALOR_QUITACAO_HOJE` (que é o valor de quitação ordinária, não necessariamente o mesmo conceito de "valor da ação de contenção") | Decidir se `VALOR_QUITACAO_HOJE` deve ser reaproveitado como o valor da ação de contenção do Gate 2 quando `prioridade_excepcional=True` é uma leitura de negócio sobre o que "a própria quitação é a ação que contém o risco" (`EC-15`) significa numericamente — nenhuma fonte normativa (`§14`, `EC-15`) confirma essa equivalência explicitamente | Nesta fatia, os dois pontos de construção do Gate 2 usam `dinheiro(0)` (R4B.1.3) — subestima o valor de ações de contenção que, na prática, podem ter desembolso conhecido. Não bloqueia nenhum `GAB-NFI-01`–`05` (nenhum exercita Gate 2 com valor de contenção). Registrado para decisão do especialista ou de uma rodada futura, não resolvido por suposição aqui |

## R4B.11. Traceability

| Requisito | Coberto por (seção do plano) |
| --- | --- |
| `RF-61` — campo monetário novo em `AcaoRequerida`, quebra de contrato, varredura de consumidores, sinalização a `app-aluno` | R4B.1.1 (decisão `OQ-39`, nome/tipo/default) · R4B.1.3 (varredura real, 12 pontos) · R4B.3 (project structure) · R4B.4.1 (contrato novo) · R4B.8 (`EC-47`, mecanismo `mypy`) · R4B.9 (`AC-110`, teste estático) |
| `RF-62` — derivar `VALOR_ACAO_FINANCEIRA_IMEDIATA`: `0` sem desembolso, valor conhecido com desembolso conhecido | R4B.1.1 (regra §14.2.1) · R4B.1.3 (aplicação nos 6 pontos de construção) · R4B.9 (`AC-105`) |
| `RF-63` — `VALOR_ACAO_FINANCEIRA_IMEDIATA = DESCONHECIDO` quando desembolso exigido e valor desconhecido; sinalização de status provisório via mecanismo já existente | R4B.4.1 (tipo `DinheiroTalvez`) · R4B.6.1 (`STATUS_METODO.PROVISORIO` reaproveitado, mecanismo completo) · R4B.9 (`AC-109`, metade verificável nesta fatia) · R4B.10 (trade-off registrado) |
| `RF-64` — `NECESSIDADE_IMEDIATA_DIVIDA` por função pura, cinco ramos em ordem estrita; `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` como soma com sinalização de incompletude; módulo é decisão do plano | R4B.1.2 (decisão `OQ-41`, análise de ciclo de import) · R4B.4.2 (assinatura, cadeia `if/elif`) · R4B.5 (data flow) · R4B.9 (`AC-101`–`AC-103`, `AC-106`, `AC-107`, `AC-108`) |
| `RF-65` — trava de dupla contagem entre `VALOR_ACAO_FINANCEIRA_IMEDIATA` e `VALOR_RELEVANTE_PARA_QUITACAO` da mesma dívida | R4B.4.2 (ramos 3/4 mutuamente exclusivos) · R4B.10 (trave como consequência estrutural, não verificação extra) · R4B.9 (`AC-104`, `AC-111`) |

**Cobertura desta fatia:** 5 de 5 requisitos (`RF-61`–`RF-65`). Nenhum
requisito da fatia 4B ficou sem seção correspondente. Nenhum item deste
plano existe sem requisito que o peça: o parâmetro `acao_financeira_
imediata_executavel: AcaoRequerida | None` está ancorado em `RF-64`
(único jeito de `NECESSIDADE_IMEDIATA_DIVIDA` avaliar o terceiro ramo), e
`STATUS_METODO.PROVISORIO` (reaproveitado, não criado) está ancorado em
`RF-63`.

**Uma ambiguidade de negócio nova foi registrada, não decidida**
(R4B.10.1 — valor de ação de contenção do Gate 2 sem fonte normativa
explícita). Não foi antecipada por implementação (`sdd.config.md` §3).

> Requisito sem cobertura é buraco no plano. Item de plano sem requisito é
> over-engineering.

---

# Rodada 4 — Ligação em `calcular_diagnostico`, fatia 4C (2026-09-10)

> Escopo: `RF-66` a `RF-69` (spec §2, Rodada 4, fatia 4C — **última fatia do
> documento do especialista**). Fonte normativa congelada: `specs/motor-
> calculo.spec.md` §14.2.4 ("Relação com `ATAQUE_IMEDIATO_RECOMENDADO`" —
> "fórmula do documento anterior (Rodada 3) é integralmente preservada").
> Fatias 4A (`RF-53`–`RF-60`) e 4B (`RF-61`–`RF-65`) concluídas e
> verificadas (build limpo em 298 arquivos, 594 testes, 47 gabaritos) —
> esta fatia não reabre nenhuma delas, apenas as compõe. Resolve
> formalmente `AMB-R3-01` (R3.10.1, decisão original "opção (b)",
> condicionada a "enquanto a fórmula não existisse" — condição que deixou
> de valer em 2026-09-09) e `OQ-44` (spec §10, Rodada 4 — fatia 4C,
> delegada a este plano).

## R4C.1. Architecture Overview

Nenhuma camada nova, nenhum módulo novo, nenhum tipo novo. Esta fatia
muda **um único ponto de composição** dentro de `engine/motor.py::
calcular_plano` — o momento em que `Diagnostico.ATAQUE_IMEDIATO_
RECOMENDADO` deixa de ser `dinheiro(0)` e passa a ser o valor real,
composto pelas funções puras já existentes de `engine/ataque_imediato.py`
(Rodada 3) e `engine/gates.py` (fatia 4B).

```text
 engine/motor.py::calcular_plano — ordem ATUAL (confirmada por leitura,
 linhas 245/250):

   [245] diagnostico = calcular_diagnostico(estado, parametros)  ← placeholder
   [247] dividas = _inventario(estado)
   [250] particao = particionar_elegibilidade(estado.dividas)
   [258] acao_economia = _acao_economia_se_houver(estado)
   [260] particao = dataclasses.replace(particao, ORDEM_ACOES=(...))
   [269-293] simular_cenario(..., diagnostico, ...) × 3 (Avalanche/Bola de
             Neve/Híbrido) — CONSOME diagnostico (com o placeholder) ANTES
             de qualquer uso de particao/NECESSIDADE_FINANCEIRA_IMEDIATA_
             ELEGIVEL
   [304-311] comparar_cenarios / derivar_METODO_RECOMENDADO_PIQ — também
             não leem ATAQUE_IMEDIATO_RECOMENDADO (confirmado por grep,
             R4C.1.2)
   [316-328] publicar_ORDEM_QUITACAO / consolidar_ORDEM_STATUS
   [335]     montar_SnapshotOrdem(..., diagnostico=diagnostico, ...)  ←
             ÚNICO ponto onde o Diagnostico final é gravado no snapshot

 engine/motor.py::calcular_plano — ordem NOVA desta fatia (R4C.1.1):

   [245] diagnostico_pre = calcular_diagnostico(estado, parametros)  ←
         placeholder, MANTIDO para os passos 7-10 (RF-67: nenhuma fórmula
         nova; RF-66 exige só que o Diagnostico PUBLICADO carregue o valor
         real — nada exige recalcular tudo com o valor real desde o passo 3)
   [250] particao = particionar_elegibilidade(estado.dividas)
   ...
   [NOVO, entre a montagem final de particao/ORDEM_ACOES e o passo 11]
         acoes_por_divida = {a.DIVIDA_ID: a for a in particao.ORDEM_ACOES
                              if a.DIVIDA_ID is not None}          (RF-68)
         elegivel = NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(
             particao=particao, acoes_por_divida=acoes_por_divida)  (gates.py,
                                                                      4B)
         ataque_imediato_recomendado = _compor_ATAQUE_IMEDIATO_RECOMENDADO(
             estado=estado, elegivel=elegivel)                    (RF-66/67,
                                                                     R4C.4.1 —
                                                                     nova
                                                                     função,
                                                                     só
                                                                     COMPÕE
                                                                     as de
                                                                     ataque_imediato.py)
         diagnostico = dataclasses.replace(
             diagnostico_pre,
             ATAQUE_IMEDIATO_RECOMENDADO=ataque_imediato_recomendado)
                                                                    (RF-66,
                                                                     mecanismo
                                                                     OQ-44)
   [335] montar_SnapshotOrdem(..., diagnostico=diagnostico, ...)  ← agora
         carrega o valor REAL
```

**Uma mudança de código, e só uma:** `engine/motor.py::calcular_plano`
ganha uma segunda passada de `Diagnostico`, entre `particionar_
elegibilidade`/a montagem final de `particao.ORDEM_ACOES` e a chamada a
`montar_SnapshotOrdem`. **Nenhuma outra função muda de assinatura.**
`calcular_diagnostico(estado, parametros)` continua exatamente como é —
mesma assinatura pública, mesmo corpo, mesmo placeholder interno — porque
o `Diagnostico` que os passos 7–10 (`simular_cenario`, `comparar_
cenarios`, `derivar_METODO_RECOMENDADO_PIQ`) consomem **não precisa** do
valor real (R4C.1.2 prova que nenhum deles lê `ATAQUE_IMEDIATO_
RECOMENDADO`), e é exatamente essa ausência de leitura que torna `AC-116`
(nenhum outro valor pode mudar) satisfazível sem reordenar o pipeline.

**Nenhuma lei de arquitetura é violada.** `engine/` continua sem importar
`persistencia/`, `app/`, `collection/` ou `report/`; sem I/O; sem
relógio; sem parâmetro `P_*` novo (a fórmula da §14.2.4/§13.3 já não usa
nenhum, herdado da Rodada 3). O import de `engine.ataque_imediato` a
partir de `engine.motor` já existe hoje (indireto, via `engine.
diagnostico`) — não é import novo.

### R4C.1.1. A decisão mais importante desta fatia — mecanismo de `OQ-44`/`RF-68`

Os três desenhos identificados pelo discovery (Rodada 4 §5) e pela spec
(§10, `OQ-44`), nenhum decidido por fonte normativa — decisão técnica
deste plano (`sdd.config.md` §3: mesmo padrão de `OQ-39`/`OQ-40`/`OQ-41`).

**(1) — Nova assinatura pública de `calcular_diagnostico`.** A função
passa a exigir `ParticaoElegibilidade`/`Mapping[str, AcaoRequerida]` (ou
os calcula internamente, rodando os gates ela mesma).

**(2) — Segunda passada com `dataclasses.replace`, fora de
`calcular_diagnostico`.** A função mantém a assinatura `(estado,
parametros)`; `engine/motor.py::calcular_plano` — que já tem
`ParticaoElegibilidade` depois de `particionar_elegibilidade` — calcula
`ATAQUE_IMEDIATO_RECOMENDADO` separadamente e substitui o campo no
`Diagnostico` já construído via `dataclasses.replace`, produzindo a
versão final antes de `montar_SnapshotOrdem`.

**(3) — Desnormalizar `DIVIDA_STATUS_ESTRATEGICO`/`GATE_PENDENTE` para
dentro de `Divida`.** Eliminaria a dependência de `ParticaoElegibilidade`
inteira, tornando o dado disponível antes de `calcular_diagnostico` sem
segunda passada.

**Decisão: (2).** Razões, uma a uma — e por que as outras duas foram
descartadas:

1. **(2) preserva a assinatura pública mais consumida do motor, sem
   contrapartida de risco.** Investigação de todo chamador real de
   `calcular_diagnostico(` (`grep -rn`, R4C.1.3) mostra **22 pontos de
   chamada** — 1 de produção (`engine/motor.py:245`) e 21 em testes
   (gabaritos, regras, estático, `app_aluno`). (1) obrigaria os 22 a
   fornecer o argumento novo, a maioria sem ter `ParticaoElegibilidade` à
   mão no ponto de teste — replicando exatamente o "risco alto por
   benefício nenhum hoje" que a Rodada 3 já registrou em `AMB-R3-01`
   original para a mesma pergunta (`plans/motor-calculo.plan.md`
   R3.10.1). A diferença desta vez é que a fórmula **existe** — mas isso
   não muda o cálculo de custo/benefício da mudança de assinatura: o
   valor de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` está disponível
   **de qualquer forma** em `engine/motor.py`, sem precisar entrar em
   `calcular_diagnostico` para isso.
2. **`calcular_diagnostico` continuar pura em `(estado, parametros)`
   preserva a garantia de composição que a Rodada 1 já estabeleceu** — a
   função é chamada isoladamente por 21 testes hoje (gabaritos `GAB-A`/
   `GAB-B`/`GAB-C`, `test_comparacao.py`, `test_RF22.py`, `test_
   parametro_externo_muda_resultado.py`, `tests/app_aluno/*`) exatamente
   **porque** ela não depende de gates — testar o diagnóstico financeiro/
   comportamental sem montar uma `ParticaoElegibilidade` completa é uma
   capacidade real que esses testes usam hoje. (1) removeria essa
   capacidade de todos eles.
3. **(2) usa mecanismo já em produção no mesmo arquivo.**
   `engine/motor.py::calcular_plano` já usa `dataclasses.replace` duas
   vezes (linha 260, para `particao.ORDEM_ACOES`; linhas 270-292, para
   `Cenario.metodo` × 3) — não é técnica nova, é o padrão estabelecido do
   próprio módulo para "construí um objeto cedo, preciso ajustar um campo
   dele mais tarde com um dado que só existe depois".
4. **(3) contradiz uma decisão de design já tomada e não revisitável por
   este plano.** `DIVIDA_STATUS_ESTRATEGICO`/`GATE_PENDENTE` são **saída**
   calculada pelo motor (`ResultadoGates`, produzido por `determinar_
   status_estrategico`/`gates.py`), nunca campo de entrada declarado pelo
   usuário em `Divida` — decisão da Rodada 1, reafirmada explicitamente
   pela nota de (3) na spec §10 (`OQ-44`: "contradiz a decisão de design
   da Rodada 1"). Desnormalizar para `Divida` obrigaria ou (a) o usuário
   informar um campo que é resultado de regra de negócio — errado por
   construção —, ou (b) rodar os gates **antes** de montar `Divida`, que
   não é uma mudança de `calcular_diagnostico`/`calcular_plano`: seria
   reestruturar `engine/estado.py` e todo o pipeline de coleta
   (`app-aluno`), muito além do escopo de `RF-66`–`RF-69`. Descartada sem
   segunda análise — o próprio texto de `OQ-44` já a enterra.
5. **O "reabre `OQ-30`" citado pela spec para (2) não se concretiza como
   risco novo.** A spec (`OQ-44`) alerta que (2) "reabre a pergunta 'onde
   vive a segunda passada', já registrada para `ATAQUE_IMEDIATO_APROVADO`
   em `OQ-30`, agora também para o *recomendado*". Investigado: `OQ-30`
   trata de **onde armazenar/confirmar** `ATAQUE_IMEDIATO_APROVADO` (fatia
   3C, fora de escopo, nunca implementada). O "onde" desta fatia é
   diferente e já está decidido pela arquitetura existente: a única
   função que tem tanto `Diagnostico` quanto `ParticaoElegibilidade`
   simultaneamente é `calcular_plano` — não há um segundo candidato
   plausível a "dono da segunda passada" para disputar. Não é a mesma
   pergunta em aberto, é uma pergunta já respondida pelo formato do
   código existente.
6. **Confirmação de que a mudança é local e não se propaga.** `Diagnostico`
   é `@dataclass(frozen=True, slots=True)` (confirmado por leitura,
   `engine/diagnostico.py:573`) — `dataclasses.replace` é o único
   mecanismo de substituição de campo pós-construção já usado neste
   projeto para esse tipo de dataclass (mesmo padrão de `particao`/
   `Cenario` em `calcular_plano`, ponto 3 acima), e produz um objeto novo
   sem mutar o original — nenhum outro código que já segura uma
   referência ao `diagnostico_pre` intermediário (nenhum existe fora de
   `calcular_plano`: a variável não escapa da função) é afetado.

**Nome da nova função de composição:** `_compor_ATAQUE_IMEDIATO_
RECOMENDADO` (prefixo `_`, privada de `engine/motor.py` — R4C.4.1). Não é
uma décima função pura na §13/§14: é o ponto único que junta o `estado`
(para os campos brutos: `DINHEIRO_DISPONIVEL`, `investimentos`, `ativos`,
`recursos_extraordinarios`, os quatro campos de reserva) com o `elegivel`
(fatia 4B) e invoca, na ordem certa, as nove funções já existentes de
`engine/ataque_imediato.py`. Vive em `engine/motor.py`, não em `engine/
ataque_imediato.py`, porque é a única função de composição desta fatia
que precisa ler `EstadoFinanceiro` diretamente — e `ataque_imediato.py`
documenta explicitamente (linha 1-45) que nenhuma de suas funções recebe
`EstadoFinanceiro`/`Diagnostico`, mantendo a NFR de Pureza "por
parâmetro" da Rodada 3. Colocar a nova função ali quebraria essa
propriedade documentada do módulo; colocá-la em `engine/motor.py`
(o único módulo que já lê `estado` E já tem `elegivel` disponível) não
introduz import novo nem depende de nada que `motor.py` não importe hoje
(`engine.ataque_imediato` já é importado indiretamente via `engine.
diagnostico`; esta fatia torna o import direto e explícito).

### R4C.1.2. Confirmação — nenhum consumidor interno lê `ATAQUE_IMEDIATO_RECOMENDADO` hoje

`grep -rn "ATAQUE_IMEDIATO_RECOMENDADO" engine/` (R4C.1, achado que
sustenta a decisão acima): as únicas ocorrências fora de `engine/
diagnostico.py` (declaração/placeholder) e `engine/ataque_imediato.py`
(as próprias funções que o calculam e o verificam) são a assinatura e o
corpo de `calcular_ATAQUE_IMEDIATO_RECOMENDADO`/`verificar_hierarquia_
ataque_imediato` — e **nenhuma delas é chamada dentro de `calcular_
diagnostico`** (a docstring atual do campo já afirma isso: "nenhuma
decisão do motor o lê", `engine/diagnostico.py:723`). `engine/ciclo_
mensal.py`, `engine/metodos/*`, `engine/comparacao.py`, `engine/status_
metodo.py`, `engine/ordem.py` — nenhum importa nem lê o campo. Isso é o
que garante que substituir o campo **depois** de todos esses módulos já
terem consumido o `Diagnostico` intermediário não altera nenhum dos
valores que eles produzem — condição necessária para `AC-116`.

### R4C.1.3. Varredura de todo chamador real de `calcular_diagnostico(`

`grep -rn "calcular_diagnostico("` no repositório inteiro (não confiando
em contagens de rodadas passadas):

| Arquivo | Linha | Papel | Afetado por esta fatia? |
| --- | --- | --- | --- |
| `engine/motor.py` | `:245` | **único chamador de produção** | Sim — ganha a segunda passada (R4C.1.1); a chamada em si não muda de assinatura |
| `tests/regras/test_comparacao.py` | `:153` | teste, `Diagnostico` isolado | Não — continua chamando com `(estado, parametros)`, recebe o placeholder (comportamento inalterado para este teste, que não exercita `ATAQUE_IMEDIATO_RECOMENDADO`) |
| `tests/regras/test_snapshot.py` | `:63`, `:237` | teste, `Diagnostico` isolado para montar `SnapshotOrdem` de teste | Não — mesma observação acima |
| `tests/regras/test_RF22.py` | `:62`, `:63`, `:113`, `:114` | teste, `Diagnostico` isolado | Não |
| `tests/gabaritos_ataque_imediato/test_gab_ai_05_modo_estabilizacao_zera_reserva.py` | `:57` | teste, `Diagnostico` isolado sobre `GAB-A` | Não — testa `RESERVA_MOBILIZAVEL`/`MODO_ESTABILIZACAO`, não `ATAQUE_IMEDIATO_RECOMENDADO` |
| `tests/app_aluno/test_opcoes_do_motor.py` | `:66` | teste, `Diagnostico` isolado | Não |
| `tests/app_aluno/test_interpolacao.py` | `:60` | teste, `Diagnostico` isolado | Não |
| `tests/gabaritos/test_gabarito_c_recomendacao.py` | `:92` | teste, `Diagnostico` isolado, cenário `GAB-C` | Não — `GAB-C` não fornece dados de ataque imediato (Bloco 4/9/10), então `elegivel`/`ATAQUE_IMEDIATO_RECOMENDADO` para este cenário são `0`/`0` em ambos os caminhos; teste não afirma nada sobre o campo |
| `tests/gabaritos/test_gabarito_c_hibrido.py` | `:126` | idem | Não |
| `tests/gabaritos/test_gabarito_c_bola_de_neve.py` | `:92` | idem | Não |
| `tests/gabaritos/test_gabarito_c_avalanche.py` | `:85` | idem | Não |
| `tests/gabaritos/test_gabarito_b_equilibrio_fragil.py` | `:59`, `:97` | idem, `GAB-B` | Não |
| `tests/gabaritos/test_gabarito_a_deficit.py` | `:58` | idem, `GAB-A` | Não |
| `tests/estatica/test_parametro_externo_muda_resultado.py` | `:143`, `:179` | teste estático, `Diagnostico` isolado | Não |

**Conclusão da varredura:** `calcular_diagnostico` continua sendo chamada
com **exatamente a mesma assinatura** em todos os 22 pontos — nenhum
teste precisa ser reescrito por causa de `RF-68`/`OQ-44` (decisão (2)).
Os testes que exercitam `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` como
placeholder (se algum existir, buscado em `tests/regras/test_
diagnostico.py`/gabaritos) continuam corretos — `calcular_diagnostico`
isolada **continua devolvendo o placeholder**; é `calcular_plano`, não
`calcular_diagnostico`, que passa a devolver o valor real no `Diagnostico`
do `SnapshotOrdem`. Isso é uma distinção importante que a tarefa de
implementação deve preservar: `AC-112` fala em "qualquer `Diagnostico`
emitido pelo motor" — interpretado como **o `Diagnostico` dentro de um
`SnapshotOrdem` publicado por `calcular_plano`**, não como toda chamada
isolada possível de `calcular_diagnostico` (a função de baixo nível, que
sempre foi documentada como "compõe sub-funções", nunca como o ponto de
entrada do motor — esse é `calcular_plano`, `engine/motor.py:1`). Ver
R4C.9 para o teste que prova essa leitura de `AC-112`/`AC-116`.

## R4C.2. Tech Stack

**Nenhuma dependência nova.** Mesma stdlib das rodadas anteriores
(`dataclasses`, `decimal`) — confirmado por leitura de `engine/motor.py`,
`engine/diagnostico.py`, `engine/ataque_imediato.py`, `engine/gates.py`.

| Escolha | Uso | Justificativa (ancorada em `RF-NN`) |
| --- | --- | --- |
| `dataclasses.replace` (já em uso em `calcular_plano`) | Substituir `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` depois de `particionar_elegibilidade` rodar | `RF-66`/`RF-68` (decisão `OQ-44`, R4C.1.1). Mesmo mecanismo já usado neste arquivo para `particao`/`Cenario` — nenhuma técnica nova introduzida. Alternativa descartada: mudar a assinatura pública de `calcular_diagnostico` (opção (1), R4C.1.1) |
| Composição direta das nove funções de `engine/ataque_imediato.py` + `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`/`NECESSIDADE_IMEDIATA_DIVIDA` de `engine/gates.py` (todas já existentes) | `RF-66`/`RF-67` — produzir `ATAQUE_IMEDIATO_RECOMENDADO` real | `RF-67` é explícito: "nenhuma fórmula nova é escrita nesta fatia; a integração apenas compõe funções já homologadas". Nenhuma alternativa cogitada — reimplementar a fórmula em paralelo violaria `RF-67`/`AC-115` diretamente |
| `Dinheiro` (não retipar `ATAQUE_IMEDIATO_RECOMENDADO` para `DinheiroTalvez`) | Tratamento de `EC-48` (elegível `DESCONHECIDO`) | Decisão já tomada e justificada na Rodada 3 (`plans/motor-calculo.plan.md`, tabela R3.10, linha "`Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` continua `Dinheiro`") e reafirmada aqui: nenhum `RF-66`–`RF-69` pede retipagem, e retipar agora seria uma SEGUNDA quebra de contrato não pedida por nenhuma fonte normativa desta fatia. Tratamento de `EC-48` cai para `0` conservador documentado (R4C.4.1/R4C.8), mesmo padrão já usado por `derivar_RESERVA_RECOMENDADA`/`derivar_RESERVA_MOBILIZAVEL` para "decisão adiada ⇒ 0 documentado, nunca solicitação silenciosa". Alternativa descartada: retipar para `DinheiroTalvez` "por completude" — rejeitada pelo mesmo motivo que a Rodada 3 já rejeitou |
| Função privada `_compor_ATAQUE_IMEDIATO_RECOMENDADO` em `engine/motor.py` (nova, mas sem lógica normativa própria) | Ponto único que junta `estado` (campos brutos) + `elegivel` (fatia 4B) e invoca as funções de `ataque_imediato.py` na ordem da §13.7 | `RF-66`/`RF-67`, R4C.1.1 (por que não vive em `ataque_imediato.py`: preservaria a NFR de Pureza "só por parâmetro" daquele módulo, que hoje não lê `EstadoFinanceiro`) |

**Contagem de dependências novas desta fatia: 0.**

## R4C.3. Project Structure

| Caminho | Mudança | Novo? |
| --- | --- | --- |
| `engine/motor.py` | Import direto de `engine.ataque_imediato` (as nove funções, R4C.4.1); nova função privada `_compor_ATAQUE_IMEDIATO_RECOMENDADO`; `calcular_plano` ganha a segunda passada de `Diagnostico` via `dataclasses.replace`, entre `particao`/`ORDEM_ACOES` finais e `montar_SnapshotOrdem` (R4C.1); `REGRAS` do módulo ganha `"RF-66"`, `"RF-67"`, `"RF-68"`, `"§14.2.4"` | não |
| `engine/diagnostico.py` | Docstring de `calcular_diagnostico` (bloco "T-114/RF-51") reescrita — remove as três afirmações desatualizadas (`RF-69`, R4C.4.2); comentário do campo `ATAQUE_IMEDIATO_RECOMENDADO` na declaração de `Diagnostico` (linha ~637-655) reescrito; comentário de construção do placeholder (linha ~845-850) reescrito para documentar que `calcular_diagnostico`, isoladamente, **continua** devolvendo o placeholder por design (R4C.1.3), e que o valor real é responsabilidade de `calcular_plano` | não |
| `tests/regras/test_ataque_imediato_recomendado_diagnostico.py` | **arquivo novo** — `AC-112`–`AC-115`, `AC-117`: testes de integração ponta a ponta via `calcular_plano`, equivalentes a `GAB-AI-06`/`GAB-AI-07` (R4C.9) | **sim** |
| `tests/gabaritos/test_gabarito_a_deficit.py`, `test_gabarito_b_equilibrio_fragil.py`, `test_gabarito_c_*.py` (4 arquivos) | Reexecutados sem alteração de asserção existente — `AC-116` exige que só `ATAQUE_IMEDIATO_RECOMENDADO` mude; adicionar, não substituir, uma asserção nova por arquivo confirmando o valor esperado do campo (R4C.9) | não (asserção adicionada, arquivo já existe) |
| `tests/invariantes/*` (os cinco invariantes) | Reexecutados sem alteração — `AC-116` (R4C.9) | não |
| `pyproject.toml` | Nenhuma mudança de marcador — o teste novo entra em `tests/regras/`, sem categoria nova | não |

**Nota de escopo.** Nenhum arquivo de `app/`, `collection/` ou `report/`
é tocado por esta fatia (spec §9: "esta fatia não altera `app-aluno`").
`engine/ataque_imediato.py` e `engine/gates.py` **não são tocados** —
`RF-67`/`AC-115` exigem composição pura das funções já existentes, sem
nenhuma edição nelas.

## R4C.4. Data Model

Contratos e assinaturas. Nomes de campo idênticos à §14/§13, caractere
por caractere (`sdd.config.md` §7). Corpo de função é escopo de
`/sdd:implement` — o pseudocódigo abaixo é o mesmo nível de detalhe já
usado em R4B.4.2 (comentários de ramo, não implementação linha a linha).

### R4C.4.1. `_compor_ATAQUE_IMEDIATO_RECOMENDADO` — nova função privada (`RF-66`, `RF-67`)

```python
# engine/motor.py — RF-66, RF-67, RF-68 · §14.2.4 · §13.3, §13.9
def _compor_ATAQUE_IMEDIATO_RECOMENDADO(
    *,
    estado: EstadoFinanceiro,
    RESERVA_MOBILIZAVEL: DinheiroTalvez,        # já calculada por
                                                  # calcular_diagnostico
                                                  # (RF-43) — não recalcula
    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL: DinheiroTalvez,  # fatia 4B —
                                                  # pode ser DESCONHECIDO
                                                  # (EC-48/AC-108)
    RESULTADO_MENSAL_ATUAL: Dinheiro,           # já calculado por
                                                  # calcular_diagnostico
) -> Dinheiro: ...
    # RF-66/RF-67 · §14.2.4 — composição, NENHUMA fórmula nova:
    #
    # 1. EC-48 — trava de propagação, avaliada PRIMEIRO: se
    #    NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL is DESCONHECIDO,
    #    devolve dinheiro(0) — mesmo padrão já usado por
    #    derivar_RESERVA_RECOMENDADA/derivar_RESERVA_MOBILIZAVEL para
    #    "decisão/dado adiado ⇒ 0 documentado, nunca fabricado como
    #    certeza" (R4C.1, R4C.8). NÃO é EC-49 (elegível=0 real, soma
    #    vazia) — a distinção entre "sei que é zero" (EC-49, Dinheiro)
    #    e "não sei quanto é" (EC-48, DESCONHECIDO) é preservada até
    #    aqui; só a partir deste ramo ela colapsa em 0, e só porque o
    #    tipo de saída (Dinheiro, decisão já tomada na Rodada 3, R3.10)
    #    não admite propagar o desconhecido adiante.
    # 2. CAIXA_RECOMENDADO = calcular_CAIXA_RECOMENDADO(
    #        DINHEIRO_DISPONIVEL=estado.DINHEIRO_DISPONIVEL)
    # 3. INVESTIMENTOS_RECOMENDADOS = calcular_INVESTIMENTOS_RECOMENDADOS(
    #        investimentos=estado.investimentos)
    # 4. EXTRAORDINARIOS_RECOMENDADOS = calcular_EXTRAORDINARIOS_RECOMENDADOS(
    #        recursos_extraordinarios=estado.recursos_extraordinarios)
    # 5. ATIVOS_RECOMENDADOS = calcular_ATIVOS_RECOMENDADOS(ativos=estado.ativos)
    # 6. NECESSIDADE_RESIDUAL = calcular_NECESSIDADE_RESIDUAL(
    #        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel,  # já Dinheiro
    #                                                              neste ponto
    #                                                              (ramo 1
    #                                                              já filtrou
    #                                                              DESCONHECIDO)
    #        CAIXA_RECOMENDADO=..., INVESTIMENTOS_RECOMENDADOS=...,
    #        EXTRAORDINARIOS_RECOMENDADOS=..., ATIVOS_RECOMENDADOS=...)
    # 7. RESERVA_RECOMENDADA = derivar_RESERVA_RECOMENDADA(
    #        RESERVA_MOBILIZAVEL=RESERVA_MOBILIZAVEL,  # parâmetro, já
    #                                                     calculado por
    #                                                     calcular_diagnostico
    #        NECESSIDADE_RESIDUAL=..., RESULTADO_MENSAL_ATUAL=...)
    # 8. return calcular_ATAQUE_IMEDIATO_RECOMENDADO(
    #        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel,
    #        CAIXA_RECOMENDADO=..., INVESTIMENTOS_RECOMENDADOS=...,
    #        EXTRAORDINARIOS_RECOMENDADOS=..., ATIVOS_RECOMENDADOS=...,
    #        RESERVA_RECOMENDADA=...)
    #
    # verificar_hierarquia_ataque_imediato NÃO é chamada aqui — mesma
    # razão já documentada em calcular_diagnostico (T-114): exige
    # ATAQUE_IMEDIATO_POTENCIAL, que não é campo de Diagnostico nesta
    # rodada (RF-44 calcula a função, mas nenhum RF-66–RF-69 pede que
    # o resultado vire campo público). Fora de escopo desta fatia
    # (nenhum AC-112–AC-117 menciona ATAQUE_IMEDIATO_POTENCIAL).
```

> **Por que `RESERVA_MOBILIZAVEL` e `RESULTADO_MENSAL_ATUAL` entram por
> parâmetro em vez de esta função reconsultar `calcular_diagnostico`.**
> `calcular_diagnostico(estado, parametros)` já foi chamada uma vez em
> `calcular_plano` (`diagnostico_pre`, R4C.1) e já produziu os dois
> valores. Chamá-la de novo dentro de `_compor_ATAQUE_IMEDIATO_
> RECOMENDADO` duplicaria trabalho puro sem necessidade (a função é
> determinística — mesmo `estado`/`parametros` sempre produz o mesmo
> resultado, mas recomputar é desperdício sem benefício) e criaria uma
> segunda fonte de verdade para `RESERVA_MOBILIZAVEL`/`RESULTADO_MENSAL_
> ATUAL` dentro da mesma execução de `calcular_plano`. Os dois chegam por
> parâmetro, lidos de `diagnostico_pre` no ponto de chamada em
> `calcular_plano` (R4C.5).

### R4C.4.2. `calcular_diagnostico` — docstring reescrita (`RF-69`)

```python
# engine/diagnostico.py — RF-69 · §14.2.4
def calcular_diagnostico(estado: EstadoFinanceiro, parametros: Parametros) -> Diagnostico:
    """... (corpo e demais parágrafos da docstring PRESERVADOS — RF-69 só
    pede reescrever o bloco "T-114/RF-51" sobre RESERVA_MOBILIZAVEL/
    ATAQUE_IMEDIATO_RECOMENDADO, não a função inteira)

    T-114/RF-51/RF-69 — RESERVA_MOBILIZAVEL e ATAQUE_IMEDIATO_RECOMENDADO.
    [Parágrafo sobre RESERVA_MOBILIZAVEL PRESERVADO sem mudança — RF-69
    não o menciona, e ele já está correto.]

    ATAQUE_IMEDIATO_RECOMENDADO, chamada ISOLADA desta função, CONTINUA
    dinheiro(0) — por design, não por pendência. `calcular_diagnostico`
    não recebe (e não deve receber, decisão OQ-44/R4C.1.1) `ParticaoElegibilidade`
    nem NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL — a fórmula da §13.3/§14.2.4
    exige o elegível, que só existe depois dos gates rodarem
    (`particionar_elegibilidade`), e esta função roda ANTES disso em
    `calcular_plano` (`engine/motor.py`, RF-68). O valor REAL só existe no
    `Diagnostico` que `calcular_plano` publica no `SnapshotOrdem` — lá,
    uma segunda passada (`dataclasses.replace`, `engine/motor.py::
    _compor_ATAQUE_IMEDIATO_RECOMENDADO`) substitui este placeholder pelo
    valor real, composto pelas mesmas nove funções de `engine/ataque_
    imediato.py` mais `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`/
    `NECESSIDADE_IMEDIATA_DIVIDA` (`engine/gates.py`, fatia 4B). Isto NÃO é
    mais placeholder por pendência de `OQ-29` (RESPONDIDA em 2026-09-09,
    §14) — é a consequência inevitável de `calcular_diagnostico` não ter,
    e não precisar ter, acesso aos gates: quem quer o valor real de
    `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` deve ler o `Diagnostico`
    dentro de um `SnapshotOrdem` publicado por `calcular_plano`, nunca o
    resultado de uma chamada isolada a esta função. `RF-66`/`RF-67`/
    §14.2.4 documentam a fórmula real e onde ela é aplicada.
    """
```

## R4C.5. Data Flow

1. `diagnostico_pre = calcular_diagnostico(estado, parametros)` roda
   exatamente como hoje (posição inalterada, passo 3-5 do fluxo de
   `calcular_plano`) — `RESERVA_MOBILIZAVEL` real (`RF-43`), `RESULTADO_
   MENSAL_ATUAL` real, `ATAQUE_IMEDIATO_RECOMENDADO = dinheiro(0)`
   (placeholder, inalterado nesta função).
2. `dividas = _inventario(estado)`, `particao = particionar_elegibilidade(
   estado.dividas)`, `acao_economia`/`dataclasses.replace(particao, ...)`
   — passo 6, posição inalterada.
3. Os três cenários (`simular_cenario` × 3, passo 7) consomem `diagnostico_
   pre` — **não** o `Diagnostico` final. Nenhuma mudança de valor aqui
   (R4C.1.2: nenhum deles lê `ATAQUE_IMEDIATO_RECOMENDADO`).
4. Comparação/status do método (passo 9) — inalterado, consome os
   `Cenario` do passo 3, não `Diagnostico` diretamente para `ATAQUE_
   IMEDIATO_RECOMENDADO`.
5. Ordem publicada/`ORDEM_STATUS` (passo 10) — inalterado.
6. **NOVO — entre o passo 10 e o passo 11 (snapshot):**
   `acoes_por_divida` é montado a partir de `particao.ORDEM_ACOES`
   (filtrando `DIVIDA_ID is not None` — `RF-68`); `elegivel =
   NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL(particao=particao,
   acoes_por_divida=acoes_por_divida)` (`engine/gates.py`, fatia 4B);
   `ataque_imediato_recomendado = _compor_ATAQUE_IMEDIATO_RECOMENDADO(
   estado=estado, RESERVA_MOBILIZAVEL=diagnostico_pre.RESERVA_MOBILIZAVEL,
   NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL=elegivel, RESULTADO_MENSAL_
   ATUAL=diagnostico_pre.RESULTADO_MENSAL_ATUAL)` (R4C.4.1); `diagnostico =
   dataclasses.replace(diagnostico_pre, ATAQUE_IMEDIATO_RECOMENDADO=
   ataque_imediato_recomendado)`.
7. Passo 11 — `montar_SnapshotOrdem(..., diagnostico=diagnostico, ...)`
   recebe o `Diagnostico` **final**, com o valor real — não mais
   `diagnostico_pre`.

**Falha em cada etapa:**

- Passo 1: inalterado — se `estado`/`parametros` forem inválidos,
  `calcular_diagnostico` falha exatamente como hoje (fora de escopo desta
  fatia).
- Passo 6 (novo): `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` pode devolver
  `DESCONHECIDO` (`AC-108`, fatia 4B) — `_compor_ATAQUE_IMEDIATO_
  RECOMENDADO` trata isso no primeiro ramo (R4C.4.1), devolvendo
  `dinheiro(0)` documentado, nunca uma exceção nem um número fabricado a
  partir do desconhecido (`EC-48`). Nenhum `try/except` é necessário —
  `DinheiroTalvez` já modela o caso como valor, não como erro (mesmo
  padrão de toda a base).
- Passo 7: `dataclasses.replace` sobre uma dataclass `frozen=True` nunca
  falha por mutação (produz objeto novo) — a única falha possível é
  `TypeError` se o nome do campo estiver errado, pego por `mypy --strict`
  antes de rodar (mesmo padrão dos dois `dataclasses.replace` já
  existentes no arquivo).

## R4C.6. External Interfaces

Nenhuma interface externa nova. Esta fatia não introduz endpoint, banco
nem arquivo novo — estende a composição interna do motor.

### R4C.6.1. `EC-48` — por que `STATUS_METODO=PROVISORIO` NÃO é acionado nesta fatia, e por que isso não descumpre `RF-68`

R4B.6.1 (fatia 4B) deixou explícito que a **segunda metade** de `AC-109`
("e o status... é sinalizado como provisório") "é verificada quando a
fatia 4C ligar o mecanismo" — uma expectativa que esta fatia precisa
resolver explicitamente, não deixar cair silenciosamente.

**Achado, por leitura de `engine/motor.py`/`engine/status_metodo.py`:**
`STATUS_METODO` (o campo publicado em `SnapshotOrdem`) é decidido por
`derivar_METODO_RECOMENDADO_PIQ` (passo 9), que roda **antes** do ponto
em que `elegivel`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` fica
disponível nesta fatia (passo 6 do fluxo novo, R4C.5, que foi
deliberadamente posicionado **depois** de `publicar_ORDEM_QUITACAO`/
`consolidar_ORDEM_STATUS`, para não perturbar nenhum valor existente).
Ligar `EC-48`/`AC-109` (segunda metade) exigiria mover o cálculo do
elegível para **antes** de `derivar_METODO_RECOMENDADO_PIQ` e fazer esse
resultado alimentar `STATUS_METODO` — uma mudança de **ordem do
pipeline**, com efeito potencial sobre `STATUS_METODO` de qualquer
cenário que hoje não é `PROVISORIO` mas passaria a ser. Isso é
exatamente o tipo de mudança de valor observável que `AC-116` proíbe
("nenhum outro valor pode mudar" além de `ATAQUE_IMEDIATO_RECOMENDADO`).

**Decisão: `EC-48` é satisfeita apenas pela metade que não exige mudar
`STATUS_METODO`** — a proibição central de `EC-48` ("não pode ser
produzido como `Dinheiro` certo tratando o desconhecido como `0`
silenciosamente") é cumprida por `_compor_ATAQUE_IMEDIATO_RECOMENDADO`
devolver `0` **documentado e citado em código e em teste** (R4C.4.1,
R4C.9), não silencioso — o mesmo padrão já aceito pela base para
`derivar_RESERVA_RECOMENDADA`/`derivar_RESERVA_MOBILIZAVEL` (Rodada 3).
A segunda metade de `AC-109`/`EC-48` (sinalizar `STATUS_METODO=
PROVISORIO`) **permanece não implementada nesta fatia** — registrada como
ambiguidade/lacuna explícita em R4C.10.1, não decidida por conveniência.
Isso não é a mesma coisa que ignorar `EC-48`: a spec pede "o requisito de
não fabricar um número certo a partir de um insumo incerto vale já nesta
spec" (EC-48, texto literal) — e é exatamente esse requisito, não o
mecanismo de sinalização de status, que `RF-66`–`RF-69`/`AC-112`–`AC-117`
cobram como critério de aceite desta fatia.

## R4C.7. State Management

Sem estado próprio, sem cache, sem memoização — mesmo padrão de `engine/
motor.py` hoje. `_compor_ATAQUE_IMEDIATO_RECOMENDADO` é função pura
chamada uma vez por execução de `calcular_plano`, dentro do mesmo bloco
`localcontext(CONTEXTO_MOTOR)` que já envolve toda a função (nenhum
`localcontext` novo é aberto — a fronteira de precisão já existente
cobre também esta composição nova, R4C.1).

## R4C.8. Error Handling Strategy

| Situação | Detecção | Resposta | Recuperação |
| --- | --- | --- | --- |
| `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL is DESCONHECIDO` (`EC-48`, ao menos uma dívida com ação prioritária de valor desconhecido) | Primeiro ramo de `_compor_ATAQUE_IMEDIATO_RECOMENDADO` (R4C.4.1) | `ATAQUE_IMEDIATO_RECOMENDADO = dinheiro(0)`, documentado como incompletude — nunca fabricado como certeza a partir do desconhecido | Sinalização de `STATUS_METODO=PROVISORIO` fica registrada como lacuna explícita (R4C.6.1, R4C.10.1) — não implementada nesta fatia |
| Todas as dívidas com `NECESSIDADE_IMEDIATA_DIVIDA = 0` (`EC-45`/`EC-49`, elegível real `= 0`) | `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` devolve `dinheiro(0)` (não `DESCONHECIDO`) | `ATAQUE_IMEDIATO_RECOMENDADO = 0` pelo `MIN` normal da fórmula (§14.2.4) — mesmo resultado numérico de `EC-48`, mas por caminho lógico diferente (elegível **conhecido e zero**, não desconhecido) | Não é erro — comportamento normativo (`EC-49`) |
| `dataclasses.replace(diagnostico_pre, ATAQUE_IMEDIATO_RECOMENDADO=...)` com nome de campo incorreto (erro de implementação) | `mypy --strict` (comando `build`) — `Diagnostico` não tem esse campo / tipo incompatível | Falha antes de `test` rodar | Corrigir o nome do campo — mesmo mecanismo de rede já usado em `RF-61`/`RF-59` |
| `GAB-A`/`GAB-B`/`GAB-C`/invariantes reexecutados divergem em campo diferente de `ATAQUE_IMEDIATO_RECOMENDADO` (`AC-116` violado) | Reexecução dos gabaritos existentes com asserção nova (R4C.3, R4C.9) | Teste falha, sinaliza regressão | Investigar se a segunda passada vazou para algum outro campo do `Diagnostico`/`SnapshotOrdem` — não deveria ser possível dado que `dataclasses.replace` só substitui o campo nomeado |

## R4C.9. Testing Strategy

- **Integração (`tests/regras/test_ataque_imediato_recomendado_diagnostico.py`,
  novo):**
  - `AC-112` — teste genérico: qualquer `SnapshotOrdem` produzido por
    `calcular_plano` tem `diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`
    calculado pela fórmula real, nunca `dinheiro(0)` fixo quando os
    insumos não são todos vazios/zero (prova negativa: constrói um
    `EstadoFinanceiro` com `DINHEIRO_DISPONIVEL > 0` e uma dívida
    elegível com `VALOR_RELEVANTE_PARA_QUITACAO > 0`, confirma que o
    resultado não é mais `0`).
  - `AC-113` — cenário equivalente a `GAB-AI-06`: `EstadoFinanceiro`
    construído para que `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`
    (calculada pela fatia 4B, não mais por parâmetro de teste) resulte em
    `20.000`, com `CAIXA_RECOMENDADO=5.000`, `INVESTIMENTOS_
    RECOMENDADOS=7.000`, `EXTRAORDINARIOS_RECOMENDADOS=0`, `ATIVOS_
    RECOMENDADOS=0`, `RESERVA_MOBILIZAVEL=10.000` — `calcular_plano`
    ponta a ponta produz `ATAQUE_IMEDIATO_RECOMENDADO=20.000`.
  - `AC-114` — cenário equivalente a `GAB-AI-07`: elegível real `10.000`,
    recursos somando `25.000` — `calcular_plano` produz `10.000`, nunca
    `25.000`.
  - `AC-115` — auditoria por leitura de código (não teste automatizado
    isolado, mesmo padrão de `test_sem_percentual_automatico_de_reserva`):
    confirma que `_compor_ATAQUE_IMEDIATO_RECOMENDADO` só chama funções
    já existentes de `engine.ataque_imediato`/`engine.gates`, sem
    reimplementar nenhuma fórmula — registrado como verificação de
    revisão de código na tarefa, reforçado por `AC-113`/`AC-114`
    reproduzirem os valores exatos dos `GAB-AI` já homologados como
    função pura isolada (se a composição divergisse da fórmula original,
    esses dois testes já pegariam).
  - `EC-48` — elegível `DESCONHECIDO`: `EstadoFinanceiro` com uma dívida
    cuja ação financeira imediata (Gate 2/4) tem `VALOR_ACAO_FINANCEIRA_
    IMEDIATA=DESCONHECIDO` — `calcular_plano` ponta a ponta produz
    `ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(0)`, nunca uma exceção nem um
    valor fabricado.
  - `EC-49` — todas as dívidas com `NECESSIDADE_IMEDIATA_DIVIDA=0` e
    recursos recomendados positivos — `ATAQUE_IMEDIATO_RECOMENDADO=0`
    (distinção de caminho lógico contra `EC-48`, R4C.8).
- **Não-regressão (`AC-116`, mesmo procedimento de `AC-56`–`AC-59`/
  `AC-87`/fatia 4B):** reexecutar `GAB-A`/`GAB-B`/`GAB-C` e os cinco
  invariantes; para cada um, **adicionar** (não substituir) uma asserção
  confirmando o novo valor de `ATAQUE_IMEDIATO_RECOMENDADO` (calculado à
  mão a partir dos dados de cada gabarito, já que nenhum deles fornece
  Bloco 4/9/10 de ataque imediato — o valor esperado nos três é `0`,
  porque nenhum dos três cenários `GAB-A`/`GAB-B`/`GAB-C` popula
  `investimentos`/`ativos`/`recursos_extraordinarios`/reserva com valor
  positivo) — e confirmar que **nenhuma outra asserção pré-existente**
  precisou mudar de valor esperado. Isso é o teste que prova `AC-116`
  como propriedade, não como afirmação não verificada.
- **Docstring (`AC-117`, verificação de revisão, não teste automatizado):**
  confirma por leitura que `engine/diagnostico.py` não contém mais as
  três afirmações desatualizadas ("placeholder", "`OQ-29` está aberta",
  "nenhuma decisão do motor o lê" sem qualificação) — reforçável por
  `grep -n "OQ-29" engine/diagnostico.py` devolvendo vazio ou só
  ocorrências históricas claramente marcadas como tal.
- **Fora de teste automatizado:** a segunda metade de `AC-109`/`EC-48`
  (sinalização de `STATUS_METODO=PROVISORIO`) — não implementada nesta
  fatia (R4C.6.1, R4C.10.1); nenhum teste afirma esse comportamento.

## R4C.10. Risks & Trade-offs

| Decisão | Alternativa descartada | Por quê | Risco assumido |
| --- | --- | --- | --- |
| Segunda passada com `dataclasses.replace` em `engine/motor.py::calcular_plano`, depois de `particionar_elegibilidade` (decisão (2), `OQ-44`, R4C.1.1) | (1) nova assinatura pública de `calcular_diagnostico`; (3) desnormalizar status estratégico para `Divida` | (1) obrigaria 22 chamadores (1 produção + 21 teste) a fornecer um argumento que a maioria não tem à mão isoladamente, repetindo o cálculo de risco já feito em `AMB-R3-01` original; (3) contradiz a decisão de design da Rodada 1 de que status estratégico é saída, não entrada | `calcular_diagnostico`, chamada isoladamente, continua devolvendo o placeholder — quem quiser o valor real precisa passar por `calcular_plano`. Mitigado: documentado explicitamente na docstring reescrita (`RF-69`, R4C.4.2) e na varredura de chamadores (R4C.1.3), para que nenhum consumidor futuro presuma erroneamente que a chamada isolada já traz o valor real |
| `_compor_ATAQUE_IMEDIATO_RECOMENDADO` como função privada nova em `engine/motor.py`, não em `engine/ataque_imediato.py` | Colocar a composição dentro de `engine/ataque_imediato.py`, como uma décima função pública do módulo | `ataque_imediato.py` documenta explicitamente (linha 1-45) que nenhuma de suas funções lê `EstadoFinanceiro`/`Diagnostico` — só parâmetros primitivos/coleções. A nova função precisa ler `estado.investimentos`/`estado.ativos`/`estado.DINHEIRO_DISPONIVEL`/etc. diretamente, o que quebraria essa propriedade documentada do módulo se movida para lá | Uma função de composição "espalhada" em `motor.py` em vez de concentrada com as demais funções de ataque imediato — mitigado porque ela não introduz lógica normativa própria (só orquestra chamadas, R4C.4.1), e `engine/motor.py` já é o módulo de orquestração de todo o resto do pipeline (mesmo papel que já cumpre para os 11 passos) |
| `EC-48` resolvida com `dinheiro(0)` documentado, sem acionar `STATUS_METODO=PROVISORIO` nesta fatia | Reordenar o pipeline para calcular `elegivel` antes de `derivar_METODO_RECOMENDADO_PIQ`, ligando a segunda metade de `AC-109` | Reordenar o pipeline é mudança de valor observável (`STATUS_METODO` de cenários que hoje não são `PROVISORIO` poderia mudar), o que `AC-116` proíbe explicitamente ("nenhum outro valor pode mudar" além de `ATAQUE_IMEDIATO_RECOMENDADO`). A proibição central de `EC-48` (não fabricar número certo a partir de desconhecido) é satisfeita sem essa reordenação | A segunda metade de `AC-109`/a citação de `EC-48` sobre `STATUS_METODO` fica sem mecanismo de sinalização nesta fatia — registrado como lacuna explícita, não decidida por conveniência (R4C.10.1) |
| `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` continua `Dinheiro`, não retipado para `DinheiroTalvez` | Retipar para `DinheiroTalvez`, "por simetria" com `RESERVA_MOBILIZAVEL`/com o `EC-48` desta fatia | Decisão já tomada e justificada na Rodada 3 (R3.10); nenhum `RF-66`–`RF-69` pede retipagem; retipar seria uma quebra de contrato adicional não solicitada por nenhuma fonte normativa desta fatia especificamente | Se uma rodada futura decidir que `STATUS_METODO=PROVISORIO` deve refletir `EC-48` de verdade, a solução mais provável (reordenar o pipeline, não retipar o campo) já está identificada aqui, evitando surpresa futura |

### R4C.10.1. Lacuna registrada, não decidida por conveniência

| Achado | Por que não é decisão deste plano | Impacto |
| --- | --- | --- |
| A segunda metade de `AC-109` (fatia 4B) — "se a ação [com valor desconhecido] tiver precedência material sobre o uso do caixa, sinalizar o status de ataque imediato correspondente como provisório" — continua sem mecanismo de ligação a `STATUS_METODO` depois desta fatia, apesar de esta ser a fatia que R4B.6.1 apontava como "quando a ligação acontece" | Ligar exigiria reordenar o pipeline de `calcular_plano` (calcular `elegivel` antes de `derivar_METODO_RECOMENDADO_PIQ`), o que arrisca mudar `STATUS_METODO` de cenários hoje não-`PROVISORIO` — violação direta de `AC-116` desta própria fatia. Não há fonte normativa (`§14.2.2`, `RF-63`) que resolva esse conflito entre "sinalizar provisório" e "não mudar nenhum outro valor"; é tensão real entre dois critérios de aceite de fatias diferentes, não ambiguidade de leitura | `EC-48`/segunda metade de `AC-109` permanecem parcialmente satisfeitos (a parte "não fabricar número certo" é cumprida; a parte "sinalizar status provisório" não). Uma rodada futura precisa decidir explicitamente se vale a pena aceitar o risco de reordenar o pipeline para fechar essa lacuna, ou se `STATUS_ATAQUE_IMEDIATO` (fora de escopo desde a Rodada 3, `OQ-30`) é o lugar certo para essa sinalização quando a fatia 3C for retomada — não decidido aqui, registrado para decisão humana/do especialista |

## R4C.11. Traceability

| Requisito | Coberto por (seção do plano) |
| --- | --- |
| `RF-66` — `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` carrega o valor real de `MIN(elegível, recursos estrategicamente recomendados)`, para todo `Diagnostico` emitido pelo motor, sem exceção de caminho | R4C.1 (arquitetura, diagrama antes/depois) · R4C.1.1 (decisão `OQ-44`) · R4C.4.1 (`_compor_ATAQUE_IMEDIATO_RECOMENDADO`) · R4C.5 (data flow, passo 6) · R4C.9 (`AC-112`–`AC-114`) |
| `RF-67` — produzido exclusivamente por funções puras já existentes, nenhuma fórmula nova | R4C.1.1 (ponto 3, mecanismo `dataclasses.replace`) · R4C.2 (Tech Stack, "nenhuma alternativa cogitada") · R4C.4.1 (pseudocódigo cita as nove funções + as duas de `gates.py`, nenhuma reimplementada) · R4C.3 (`engine/ataque_imediato.py`/`engine/gates.py` não tocados) · R4C.9 (`AC-115`) |
| `RF-68` — resolver formalmente `AMB-R3-01`/`OQ-44`: onde e como `calcular_diagnostico`/`calcular_plano` obtêm `ParticaoElegibilidade`/`Mapping[str, AcaoRequerida]` | R4C.1.1 (decisão completa, três alternativas avaliadas, duas descartadas com justificativa) · R4C.1.3 (varredura de 22 chamadores) · R4C.5 (passo 6, mecânica exata) |
| `RF-69` — docstring de `calcular_diagnostico` e declaração de `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` reescritas, sem as três afirmações desatualizadas | R4C.3 (`engine/diagnostico.py`, mudança listada) · R4C.4.2 (docstring nova, texto completo) · R4C.9 (`AC-117`) |

**Cobertura desta fatia:** 4 de 4 requisitos (`RF-66`–`RF-69`). Nenhum
requisito da fatia 4C ficou sem seção correspondente. Nenhum item deste
plano existe sem requisito que o peça: `_compor_ATAQUE_IMEDIATO_
RECOMENDADO` está ancorado em `RF-66`/`RF-67` (única forma de compor o
valor real sem mudar assinatura pública nem reimplementar fórmula), e o
tratamento de `EC-48` dentro dela está ancorado no próprio `EC-48` da
spec, não inventado por este plano.

**Duas decisões técnicas foram tomadas** (`OQ-44`/`RF-68`, opção (2); e
o alcance de `EC-48` sem tocar `STATUS_METODO`) e **uma lacuna foi
registrada, não decidida por conveniência** (R4C.10.1 — a segunda metade
de `AC-109`, ligação de `STATUS_METODO=PROVISORIO`, fica para rodada
futura). Nenhuma ambiguidade de negócio nova foi antecipada por
implementação (`sdd.config.md` §3).

**Esta é a última fatia do documento do especialista.** Com `RF-66`–
`RF-69` implementados, `OQ-29` está fechada por completo (fórmula
definida na Rodada 3, dados de entrada definidos na fatia 4B, ligação
definida aqui) e `AMB-R3-01` está resolvida formalmente, substituindo a
resolução condicional original de R3.10.1.

> Requisito sem cobertura é buraco no plano. Item de plano sem requisito é
> over-engineering.
