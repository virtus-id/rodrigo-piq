# PIQ v1.0.1 — Fechamento das Definições Remanescentes da Engine

**Documento normativo · Uso restrito à equipe de desenvolvimento do PIQ**

> Transcrição fiel do PDF entregue pelo especialista. Registra e **congela** as
> oito decisões finais da engine. Nenhuma definição aqui fica a critério de
> interpretação na implementação.

## Regra de precedência

Para os assuntos aqui tratados, estas definições **prevalecem** sobre qualquer
redação anterior conflitante ou incompleta da Matriz Canônica, do Questionário
Canônico, de erratas, notas intermediárias ou respostas técnicas anteriores.

A Matriz Canônica permanece soberana para todos os temas não modificados aqui.
Este documento **não** a substitui — complementa apenas as regras específicas
que trata.

## As oito decisões congeladas

1. `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`
2. Horizonte de `DESEMBOLSO_FUTURO`
3. Composição do `FATOR_SEGURANCA`
4. Fórmulas de `NIVEL_CONTROLE` e `CONFIABILIDADE_DADOS`
5. Elegibilidade de `EM_ACORDO` e `COBRANCA_SEM_PAGAMENTO`
6. Estado estratégico da dívida desviada pelo Gate 2
7. Valores de `STATUS_FINANCEIRO` e função do `PISO_CAPACIDADE`
8. Modo canônico de arredondamento

---

## 1. `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`

```
INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE =
    NECESSIDADE_VITORIA >= P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA
    E
    (
        HISTORICO_ABANDONO = SIM
        OU RISCO_RECAIDA = ALTO
        OU NIVEL_CONTROLE = FRAGIL
    )
```

`P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA = 7` na v1.0.1.

**Condições isoladas não bastam.** `NECESSIDADE_VITORIA >= 7` sozinho não basta.
Abandono, recaída alta ou controle frágil sozinhos não bastam se
`NECESSIDADE_VITORIA < 7`. O operador entre os dois grupos é **E**; entre
abandono, recaída e controle é **OU**.

> **TRAVA DE IMPLEMENTAÇÃO.** O valor 7 não pode ser escrito no código. A engine
> consulta `P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA`.

**Exemplo — `GAB-C`:** `NECESSIDADE_VITORIA = 8`, `HISTORICO_ABANDONO = SIM`
→ `8 >= 7` verdadeiro E abandono verdadeiro → **SIM**.

## 2. Horizonte de `DESEMBOLSO_FUTURO`

`DESEMBOLSO_FUTURO` é a soma de todos os desembolsos futuros necessários, a
partir do snapshot atual, **até a extinção integral da dívida** na trajetória
simulada.

```
TRAJETORIA_A = trajetória da dívida SEM o DELTA extraordinário
TRAJETORIA_B = trajetória da mesma dívida COM o DELTA aplicado imediatamente

DESEMBOLSO_FUTURO = Σ pagamentos futuros, do snapshot atual até SALDO = 0
```

- `DESEMBOLSO_FUTURO_A` é apurado até a quitação **na trajetória A**.
- `DESEMBOLSO_FUTURO_B` é apurado até a quitação **na trajetória B**.

As duas trajetórias podem ter prazos diferentes. **Isso é esperado.**

**Proibido:** truncar ambas no menor prazo; usar horizonte arbitrário (60 meses,
120 meses, número fixo de períodos, prazo da trajetória mais curta).

**Permitido tecnicamente:** horizonte comum igual ao **maior** prazo entre as
duas, desde que `DESEMBOLSO_MENSAL = 0` nos períodos após a quitação de cada
uma. O resultado deve ser matematicamente equivalente à soma individual.

```
BENEFICIO_MARGINAL_AMORTIZACAO =
    (DESEMBOLSO_FUTURO_SEM_DELTA − DESEMBOLSO_FUTURO_COM_DELTA)
    ÷ DELTA_REALMENTE_APLICADO
```

### 2.1. Quando o benefício marginal não pode ser calculado

Se uma trajetória não puder chegar deterministicamente à extinção porque faltam
dados essenciais, o saldo é desconhecido, a taxa necessária é desconhecida, o
fluxo contratual é indeterminado, o pagamento não é suficiente para amortizar e
a trajetória não tem solução determinística, ou há outra insuficiência material:

```
BENEFICIO_MARGINAL_AMORTIZACAO = NAO_CALCULAVEL
```

Aplicar o fallback canônico da Avalanche: 1º `TAXA_EFETIVA_MENSAL_NORMALIZADA`;
2º `CET` comparável. Se a ordem depender de fallback, o `STATUS` da ordem
financeira é `PROVISORIA`. **Não criar benefício marginal artificial.**

## 3. `FATOR_SEGURANCA` — composição subtrativa

```
REDUCAO_SEGURANCA_TOTAL = REDUCAO_RENDA_VARIAVEL
                        + REDUCAO_CONFIABILIDADE
                        + REDUCAO_RISCO_COMPORTAMENTAL
                        + REDUCAO_RECAIDA

FATOR_SEGURANCA_BRUTO = 1 − REDUCAO_SEGURANCA_TOTAL

FATOR_SEGURANCA = MAX(P_FATOR_SEGURANCA_MINIMO, FATOR_SEGURANCA_BRUTO)
```

**Não utilizar** `(1−r1) × (1−r2) × (1−r3) × ...`

**Exemplo:** `0,20 + 0,15 + 0 + 0,10 = 0,45` → bruto `1 − 0,45 = 0,55` → com piso
`0,60` → `FATOR_SEGURANCA = 0,60`.

> **TRAVA.** As reduções são aditivas. O piso é aplicado **somente depois** da
> soma das reduções.

## 4. `NIVEL_CONTROLE`

Domínio: `FORTE` · `PARCIAL` · `FRAGIL`. Sem score oculto, sem média ponderada,
sem pesos para calibração.

**`FRAGIL`** — se **qualquer** condição ocorrer:

```
REGISTRO_GASTOS ∈ {RARAMENTE, NAO_REGISTRA}
OU CONHECIMENTO_GASTO = NAO_SEI
OU GASTOS_NAO_IDENTIFICADOS ∈ {FREQUENTE, NAO_CONFERE}
OU REVISAO_SEMANAL = NUNCA
```

**`FORTE`** — se **todas** forem satisfeitas:

```
REGISTRO_GASTOS ∈ {TUDO, MAIORIA}
E FREQUENCIA_REGISTRO ∈ {DIARIA, VARIAS_SEMANA, SEMANAL}
E CONHECIMENTO_GASTO ∈ {BOA_APROXIMACAO, RAZOAVEL}
E REVISAO_SEMANAL ∈ {SEMPRE, MAIORIA}
E GASTOS_NAO_IDENTIFICADOS ∉ {FREQUENTE, NAO_CONFERE}
```

**`PARCIAL`** — todos os demais casos.

**Ordem de avaliação obrigatória:** testar `FRAGIL` primeiro; se nenhuma ocorrer,
testar `FORTE`; se `FORTE` não for satisfeito integralmente, classificar
`PARCIAL`.

## 5. `CONFIABILIDADE_DADOS`

Domínio: `ALTA` · `MEDIA` · `BAIXA`. Refere-se à confiabilidade da fotografia
financeira construída por comportamento e rotina de registro. **Não** substitui
qualidade documental específica de uma dívida.

**`BAIXA`** — se **qualquer** condição ocorrer:

```
NIVEL_CONTROLE = FRAGIL
OU DEFASAGEM_REGISTRO ∈ {FIM_MES, SEM_PADRAO}
OU COBERTURA_PEQUENOS_GASTOS ∈ {QUASE_NENHUM, NAO_ENTRAM}
OU COBERTURA_MEIOS_PAGAMENTO ∈ {PARCIAL, NAO_SEI}
```

**`ALTA`** — se **todas** forem satisfeitas:

```
NIVEL_CONTROLE = FORTE
E DEFASAGEM_REGISTRO ∈ {NA_HORA, MESMO_DIA}
E COBERTURA_PEQUENOS_GASTOS ∈ {TODOS, MAIORIA}
E COBERTURA_MEIOS_PAGAMENTO ∈ {TOTAL, QUASE_TOTAL}
```

**`MEDIA`** — todos os demais casos.

**Ordem de avaliação obrigatória:** `BAIXA` → `ALTA` → `MEDIA`.

### 5.1. Domínios internos do Bloco 2

Não criar novos valores internos.

| Variável | Valores internos |
| --- | --- |
| `REGISTRO_GASTOS` | `TUDO` · `MAIORIA` · `PARTE` · `RARAMENTE` · `NAO_REGISTRA` |
| `FREQUENCIA_REGISTRO` | `DIARIA` · `VARIAS_SEMANA` · `SEMANAL` · `VARIAS_MES` · `SOB_DEMANDA` · `INDEFINIDA` |
| `DEFASAGEM_REGISTRO` | `NA_HORA` · `MESMO_DIA` · `DIAS_DEPOIS` · `FIM_SEMANA` · `FIM_MES` · `SEM_PADRAO` |
| `COBERTURA_PEQUENOS_GASTOS` | `TODOS` · `MAIORIA` · `ALGUNS` · `QUASE_NENHUM` · `NAO_ENTRAM` |
| `COBERTURA_MEIOS_PAGAMENTO` | `TOTAL` · `QUASE_TOTAL` · `PARCIAL` · `NAO_SEI` |
| `CONHECIMENTO_GASTO` | `BOA_APROXIMACAO` · `RAZOAVEL` · `NOCAO_GERAL` · `NAO_SEI` |
| `GASTOS_NAO_IDENTIFICADOS` | `NUNCA` · `RARAMENTE` · `ALGUMAS_MES` · `FREQUENTE` · `NAO_CONFERE` |
| `REVISAO_SEMANAL` | `SEMPRE` · `MAIORIA` · `ALGUMAS` · `RARAMENTE` · `NUNCA` |

## 6. `STATUS_DIVIDA` não determina sozinho a elegibilidade

`STATUS_DIVIDA` é o estado operacional declarado no cadastro. Domínio:
`ATIVA` · `EM_ACORDO` · `COBRANCA_SEM_PAGAMENTO` · `QUITADA_A_CONFIRMAR` ·
`OUTRA`.

`DIVIDA_STATUS_ESTRATEGICO` é o estado usado pelo motor para decidir. **A
elegibilidade é determinada pelos gates, não pelo `STATUS_DIVIDA`.**

| `STATUS_DIVIDA` | Tratamento |
| --- | --- |
| `ATIVA` | Não é automaticamente elegível. Passa pelos Gates 1–4. Resolvidos → `PRONTA_PARA_ORDENACAO`, ou `EM_ATAQUE` se já for o alvo |
| `EM_ACORDO` **Caso A** — acordo já contratado, dívida vigente é a resultante, saldo/parcela/prazo conhecidos, nenhuma transformação pendente | Não bloqueia. Passa pelos gates e pode chegar a `PRONTA_PARA_ORDENACAO` |
| `EM_ACORDO` **Caso B** — negociação aberta, proposta não executada, ou saldo/parcela/taxa/prazo/custo podem mudar materialmente | `DIVIDA_STATUS_ESTRATEGICO = INTERVENCAO_PENDENTE` · `GATE_PENDENTE = TRANSFORMACAO`. Não ordenar definitivamente até a resolução |
| `COBRANCA_SEM_PAGAMENTO` | Não é automaticamente inelegível. Pode receber ataque se a existência estiver confirmada, houver `VALOR_RELEVANTE_PARA_QUITACAO` conhecido e os Gates 1–4 estiverem resolvidos → `PRONTA_PARA_ORDENACAO`. **Não inventar parcela mensal nem `PAGAMENTO_MENSAL_DEVIDO_VIGENTE`** quando não existir obrigação mensal vigente conhecida |
| `QUITADA_A_CONFIRMAR` | **Inelegível.** Não ordenar, não atacar, não tratar como ativa. `INFORMACAO_PENDENTE` · `GATE_PENDENTE = INFORMACAO`. Após confirmação: se quitada, status correspondente a `QUITADA`; se não, normalizar e repassar pelos gates |
| `OUTRA` | Entra como `DIVIDA_STATUS_ESTRATEGICO = EM_ANALISE`. Não recebe ataque enquanto a situação não for normalizada o suficiente para aplicar os gates |

## 7. Estado estratégico da dívida desviada pelo Gate 2

```
DIVIDA_STATUS_ESTRATEGICO = INTERVENCAO_PENDENTE
GATE_PENDENTE            = CONTENCAO_RISCO
```

**Não criar um novo status estratégico apenas para o Gate 2.** A diferença entre
Gate 2 e Gate 3 é representada pelo motivo do gate.

| Gate | `DIVIDA_STATUS_ESTRATEGICO` | `GATE_PENDENTE` |
| --- | --- | --- |
| Gate 2 — Contenção de Risco | `INTERVENCAO_PENDENTE` | `CONTENCAO_RISCO` |
| Gate 3 — Transformação | `INTERVENCAO_PENDENTE` | `TRANSFORMACAO` |

Concluída a ação e sem outro gate pendente →
`DIVIDA_STATUS_ESTRATEGICO = PRONTA_PARA_ORDENACAO`.

### 7.1. Atributo interno `GATE_PENDENTE`

```
GATE_PENDENTE ∈ {INFORMACAO, CONTENCAO_RISCO, TRANSFORMACAO,
                 OPORTUNIDADE, NENHUM}
```

`NENHUM` quando nenhum gate estiver pendente. Campo **interno ao motor** — não é
pergunta ao usuário.

## 8. `STATUS_FINANCEIRO`

Domínio canônico: `DEFICIT` · `EQUILIBRIO_FRAGIL` · `CAPACIDADE_POSITIVA`.

| Status | Condição | Semáforo |
| --- | --- | --- |
| `DEFICIT` | `RESULTADO_MENSAL_ATUAL < 0` | vermelho |
| `EQUILIBRIO_FRAGIL` | `0 <= RESULTADO_MENSAL_ATUAL < PISO_CAPACIDADE` | amarelo |
| `CAPACIDADE_POSITIVA` | `RESULTADO_MENSAL_ATUAL >= PISO_CAPACIDADE` | verde |

### 8.1. `PISO_CAPACIDADE` classifica; não altera a capacidade

```
PISO_CAPACIDADE = MAX(P_PISO_CAPACIDADE_ABSOLUTO,
                      RENDA_TOTAL_RECORRENTE × P_PISO_CAPACIDADE_PERCENTUAL)
```

Valores iniciais: `P_PISO_CAPACIDADE_ABSOLUTO` = R$ 100,00 ·
`P_PISO_CAPACIDADE_PERCENTUAL` = 3%.

O piso **não** trunca, **não** aumenta, **não** reduz a capacidade; **não**
transforma R$ 200 em R$ 300 nem em R$ 0; **não** é capacidade mínima obrigatória
nem valor mínimo de ataque. Sua função é **classificar**.

```
CAPACIDADE_ATAQUE_ATUAL = MAX(0, RESULTADO_MENSAL_ATUAL)
```

**Exemplo:** `RESULTADO_MENSAL_ATUAL` = 200, `PISO_CAPACIDADE` = 300 →
`EQUILIBRIO_FRAGIL` e `CAPACIDADE_ATAQUE_ATUAL` = **200**. Não 0. Não 300.

### 8.2. Relação com o Modo Estabilização

```
SE RESULTADO_MENSAL_ATUAL < 0:
    STATUS_FINANCEIRO       = DEFICIT
    CAPACIDADE_ATAQUE_ATUAL = 0
    DEFICIT_MENSAL          = ABS(RESULTADO_MENSAL_ATUAL)
    MODO_ESTABILIZACAO      = SIM
```

O piso **não** é usado para fabricar capacidade durante déficit.

## 9. Arredondamento

```
ROUNDING_MODE = ROUND_HALF_UP
```

Modo oficial da v1.0.1 — deixa de ser provisório.

- **Monetário exibido:** 2 casas decimais. `10,124 → 10,12` · `10,125 → 10,13` ·
  `10,126 → 10,13`.
- **Percentuais, taxas, indicadores:** mesmo modo, casas conforme o campo.

> **TRAVA DE PRECISÃO.** A engine deve usar aritmética decimal; evitar float
> binário em cálculo financeiro; preservar a precisão interna durante os
> cálculos; **não** arredondar cada etapa intermediária só para coincidir com a
> apresentação; aplicar `ROUND_HALF_UP` nos pontos de exibição; e arredondar
> intermediariamente apenas quando a realidade contratual exigir valor
> efetivamente liquidado em centavos.

## 10. Testes unitários mínimos

| # | Entradas | Resultado esperado |
| --- | --- | --- |
| 1 | `NECESSIDADE_VITORIA`=8 · `HISTORICO_ABANDONO`=SIM · `RISCO_RECAIDA`=BAIXO · `NIVEL_CONTROLE`=FORTE | `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` = SIM |
| 2 | `NECESSIDADE_VITORIA`=6 · `HISTORICO_ABANDONO`=SIM | `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` = NAO |
| 3 | reduções 0,20 + 0,15 + 0,10 · piso 0,60 | `FATOR_SEGURANCA` = 0,60 |
| 4 | `RESULTADO_MENSAL_ATUAL` = −500 | `DEFICIT` · `CAPACIDADE_ATAQUE_ATUAL` = 0 |
| 5 | `RESULTADO_MENSAL_ATUAL` = 200 · `PISO_CAPACIDADE` = 300 | `EQUILIBRIO_FRAGIL` · `CAPACIDADE_ATAQUE_ATUAL` = 200 |
| 6 | `RESULTADO_MENSAL_ATUAL` = 500 · `PISO_CAPACIDADE` = 300 | `CAPACIDADE_POSITIVA` · `CAPACIDADE_ATAQUE_ATUAL` = 500 |
| 7 | `10,125` | `10,13` |
| 8 | `EM_ACORDO` · acordo executado · estrutura conhecida · gates resolvidos | pode atingir `PRONTA_PARA_ORDENACAO` |
| 9 | `COBRANCA_SEM_PAGAMENTO` · saldo conhecido · sem parcela conhecida · gates resolvidos | pode atingir `PRONTA_PARA_ORDENACAO`; `PAGAMENTO_MENSAL_DEVIDO_VIGENTE` não pode ser inventado |
| 10 | dívida desviada para contenção de risco | `INTERVENCAO_PENDENTE` · `GATE_PENDENTE` = `CONTENCAO_RISCO` |

---

> **Declaração final.** Nenhuma dessas decisões fica a critério do
> desenvolvedor. Qualquer alteração futura deverá ocorrer exclusivamente
> mediante nova versão formal da especificação do PIQ.
