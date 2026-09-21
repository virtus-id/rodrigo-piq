# PIQ v1.0.1 — Especificação Canônica Consolidada

**Plano Inteligente de Quitação · Servidor Sem Dívidas**

> Fonte direta para desenvolvimento. Substitui, nos temas aqui tratados, todas as redações anteriores da Matriz Canônica, do Questionário Canônico e das devolutivas intermediárias. Os PDFs permanecem como documentação metodológica e histórica.

---

## Índice

| # | Seção | Conteúdo |
|---|---|---|
| 1 | [Escopo e precedência](#sec-1) | O que este documento é e o que ele revoga |
| 2 | [Ciclo mensal canônico](#sec-2) | Os 12 passos da mecânica temporal do dinheiro |
| 3 | [Gatilhos de recálculo](#sec-3) | Quando a ordem é recalculada — e quando não é |
| 4 | [Resíduo e fluxo liberado](#sec-4) | Duas grandezas parecidas e distintas |
| 5 | [Os três métodos](#sec-5) | Avalanche, Bola de Neve e Híbrido |
| 6 | [Status do método](#sec-6) | NAO_CALCULAVEL × NAO_APLICAVEL |
| 7 | [Ordem publicada e versionamento](#sec-7) | O que o relatório mostra |
| 8 | [Parâmetros](#sec-8) | 45 valores ajustáveis, nenhum no código |
| 9 | [Regras do motor](#sec-9) | As 54 regras numeradas |
| 10 | [Gabaritos de homologação](#sec-10) | 3 casos numéricos + 5 invariantes |
| 11 | [Questionário — 291 perguntas](#sec-11) | A especificação de coleta, bloco a bloco |
| 12 | [Índice de variáveis](#sec-12) | 270 variáveis, onde cada uma é coletada |
| 13 | [Errata](#sec-13) | O que mudou dos PDFs e por quê |
| 14 | [Pendências](#sec-14) | O que segue aberto |
| 15 | [Arquitetura recomendada](#sec-15) | Como construir sem mutilar a metodologia |

**Atalho para os blocos do questionário:**

[Bloco 1](#bloco-1) · [Bloco 2](#bloco-2) · [Bloco 3](#bloco-3) · [Bloco 4](#bloco-4) · [Bloco 5](#bloco-5) · [Bloco 7](#bloco-7) · [Bloco 8](#bloco-8) · [Bloco 9](#bloco-9) · [Bloco 10](#bloco-10) · [Bloco 11](#bloco-11) · [Bloco 12](#bloco-12)

---

<a id="sec-1"></a>

## 1. Escopo e precedência

Este documento é a especificação canônica do PIQ v1.0.1. Foi produzido a partir da Matriz Canônica do Produto v1.0, do Questionário Canônico v1.0 e das devolutivas do especialista que resolveram as divergências abertas durante o discovery.

> **REGRA DE PRECEDÊNCIA** — Em caso de conflito com redações anteriores da Matriz Canônica, do Questionário Canônico, de devolutivas intermediárias ou de notas de implementação, prevalecem as regras deste documento.

O objetivo dessa regra é operacional: um desenvolvedor não deve precisar saber que uma página corrige outra. Todas as redações superadas já foram substituídas. Não existe regra de precedência escondida.

> **TRAVA** — Nenhuma decisão registrada neste documento fica a critério de implementação. Qualquer alteração futura exige nova versão formal da especificação.

<a id="sec-2"></a>

## 2. Ciclo mensal canônico

Vale igualmente para Avalanche, Bola de Neve e Híbrido. O que muda entre os métodos é a regra de seleção do alvo, não o ciclo.

1. Abrir o mês com os saldos e a capacidade disponíveis no início do período.
2. Aplicar juros, encargos e evolução contratual conforme o modelo de cada dívida.
3. Aplicar os pagamentos mensais normais de todas as dívidas, limitados ao saldo.
4. Aplicar o ataque adicional à `DIVIDA_ALVO_ATUAL`.
5. Se a dívida-alvo não for quitada: manter o mesmo alvo para o mês seguinte, salvo `EVENTO_RECALCULO` externo.
6. Se for quitada: confirmar a quitação, atualizar o estado e calcular `RESIDUO_ATAQUE_M`.
7. Havendo `RESIDUO_ATAQUE_M > 0`: recalcular a ordem das dívidas restantes, selecionar o novo alvo e aplicar o resíduo ainda no mês *m*.
8. Repetir o passo 7 enquanto houver resíduo e houver dívida elegível.
9. Encerrar o mês.
10. Consolidar o `VALOR_FLUXO_LIBERADO` das dívidas quitadas no período.
11. Incorporar o fluxo liberado à capacidade a partir de *m+1*.
12. Reavaliar a ordem para o próximo período **somente** se houve quitação no período ou `EVENTO_RECALCULO` externo material. Na ausência de ambos, preservar a `DIVIDA_ALVO_ATUAL`.

Precisão interna integral em todo o ciclo; arredondamento apenas na exibição.

<a id="sec-3"></a>

## 3. Gatilhos de recálculo da ordem

A ordem do PIQ é evento-dirigida. A simples passagem de um mês não dispara reranqueamento.

```
RECALCULAR_ORDEM  =  QUITACAO_CONFIRMADA
                  OU EVENTO_RECALCULO_EXTERNO

RECALCULAR_ORDEM  ≠  VIRADA_DO_MES
```

A quitação de **qualquer** dívida dispara recálculo, não apenas a da dívida-alvo. Uma dívida que se encerra apenas com o pagamento normal retira-se do estoque, libera fluxo e altera a capacidade — e portanto dispara novo ranqueamento.

### 3.1. Os dois ranqueamentos após uma quitação

| Momento | Finalidade | Delta usado |
|---|---|---|
| Imediato, ainda no mês *m* | Destinar o ataque que restou | `MIN(RESIDUO_ATAQUE_M, VALOR_RELEVANTE_PARA_QUITACAO)` |
| No encerramento do mês | Definir o alvo de *m+1* | Capacidade de *m+1*, já com o fluxo liberado |

> **REGRA DE OURO** — Passagem de mês não é evento de recálculo. Quitação e alteração material são.

### 3.2. Eventos materiais

Constituem `EVENTO_RECALCULO` externo e material: alteração relevante de renda; alteração relevante de despesas; nova dívida; renegociação efetivamente executada; troca ou portabilidade efetivamente executada; recurso extraordinário efetivamente recebido e aprovado; informação material antes desconhecida que passou a ser conhecida; mudança patrimonial material; proposta temporária relevante; alteração relevante de risco; outro evento expressamente classificado pela engine como material.

> **TRAVA** — Alteração meramente cadastral, correção textual, mudança cosmética de registro ou passagem ordinária do tempo **não** constitui `EVENTO_RECALCULO`.

Ocorrendo evento material, a engine **deve** reavaliar todas as decisões afetadas e gerar novo snapshot. Recalcular não implica mudar: se método, D\* e ordem seguirem sendo os melhores, permanecem.

<a id="sec-4"></a>

## 4. Resíduo de ataque e fluxo liberado

São duas grandezas parecidas e economicamente distintas. Confundi-las produz dupla contagem ou perda artificial de dinheiro.

### 4.1. Resíduo de ataque — mesmo mês

```
RESIDUO_ATAQUE_M = ATAQUE_DISPONIVEL_M
                 − ATAQUE_EFETIVAMENTE_NECESSARIO_PARA_QUITAR_ALVO
```

O ataque é orçamento do mês corrente, não pagamento dirigido a uma dívida específica. Se a dívida-alvo for quitada consumindo apenas parte dele, o restante segue para a próxima dívida elegível **ainda no mês *m***, repetidamente, até esgotar o ataque ou as dívidas elegíveis.

Não havendo dívida elegível, o valor é registrado como `ATAQUE_NAO_UTILIZADO` e permanece como caixa ou patrimônio do usuário.

> **TRAVA** — Nenhum valor disponível ao usuário pode desaparecer da simulação por convenção de cálculo.

### 4.2. Fluxo liberado — mês seguinte

```
CAPACIDADE_ATAQUE_M+1 = CAPACIDADE_ATAQUE_M
                      + VALOR_FLUXO_LIBERADO_M
                      + demais alterações aplicáveis
```

A prestação que deixa de sair do orçamento porque a dívida foi eliminada só reforça a capacidade a partir de *m+1*. Não há liberação retroativa dentro do mês da quitação.

*Exemplo:* uma dívida com pagamento de R$ 700 é quitada no mês 4. O resíduo do ataque pode seguir para outra dívida ainda no mês 4; os R$ 700 reforçam a capacidade somente no mês 5.

> **TRAVA DE DUPLA CONTAGEM** — O mesmo valor não pode ser utilizado simultaneamente como pagamento normal do mês *m* e como capacidade adicional retroativa no próprio mês *m*.

<a id="sec-5"></a>

## 5. Os três métodos

### 5.1. Avalanche

Alvo escolhido pelo maior `BENEFICIO_MARGINAL_AMORTIZACAO` no momento do ranqueamento, com `DELTA_TESTE_AVALANCHE = MIN(capacidade aplicável, VALOR_RELEVANTE_PARA_QUITACAO)`.

Uma vez escolhido, o alvo permanece até ser quitado ou até `EVENTO_RECALCULO` externo. Não há reranqueamento mensal. Havendo resíduo no mês da quitação, o recálculo ocorre imediatamente após a quitação e **antes** da aplicação do resíduo.

### 5.2. Bola de Neve

Alvo escolhido pelo menor `VALOR_RELEVANTE_PARA_QUITACAO`, respeitados os gates. Alvo fixo até quitação ou evento; não é reranqueada a cada passagem de mês.

Desempates, nesta ordem: maior `VALOR_FLUXO_LIBERADO`; maior custo financeiro; maior `PESO_EMOCIONAL`; `DIVIDA_ID` como desempate técnico final.

### 5.3. Híbrido

Uma única vitória estratégica inicial seguida da Avalanche event-driven das demais. Construção determinística em seis etapas.

| Etapa | Regra |
|---|---|
| 1 | Calcular `ORDEM_AVALANCHE` como referência de eficiência financeira. |
| 2 | Para cada dívida elegível D diferente da primeira da `ORDEM_AVALANCHE`, simular `CENARIO_HIBRIDO_D` = D primeiro + Avalanche para as restantes, respeitados previamente todos os gates. |
| 3 | D é candidata válida se, **cumulativamente**, atender às três tolerâncias abaixo. |
| 4 | Havendo várias candidatas, escolher lexicograficamente (ver abaixo). |
| 5 | `ORDEM_HIBRIDA` = D\* seguida da Avalanche event-driven das restantes. |
| 6 | Não havendo candidata: `CENARIO_HIBRIDO = NAO_APLICAVEL` e `ORDEM_HIBRIDA = NAO_APLICAVEL`. Não se fabrica um Híbrido. |

**Etapa 3 — condições cumulativas:**

```
    MESES_PRIMEIRA_VITORIA(CENARIO_HIBRIDO_D) ≤ P_MESES_VITORIA_RAPIDA
E   PENALIDADE_CUSTO_VS_AVALANCHE             ≤ P_DIFERENCA_CUSTO_EQUIVALENTE
E   ATRASO_PRAZO_VS_AVALANCHE                 ≤ P_DIFERENCA_PRAZO_EQUIVALENTE
```

**Etapa 4 — desempate lexicográfico:** 1º menor `MESES_PRIMEIRA_VITORIA`; 2º menor `PENALIDADE_CUSTO_VS_AVALANCHE`; 3º maior `VALOR_FLUXO_LIBERADO`; 4º maior `PESO_EMOCIONAL`; 5º maior `BENEFICIO_MARGINAL_AMORTIZACAO`; 6º menor `DIVIDA_ID`.

**Fases em execução:**

```
FASE_HIBRIDA_1:  DIVIDA_ALVO_ATUAL = D*
                 até QUITACAO_D* ou EVENTO_RECALCULO_EXTERNO

FASE_HIBRIDA_2:  Avalanche event-driven das dívidas restantes
```

D\* não pode ser substituída apenas porque a evolução mensal dos saldos alterou o `BENEFICIO_MARGINAL_AMORTIZACAO`. Ocorrendo evento material antes da quitação de D\*, todo o plano deve ser reavaliado, inclusive a validade da própria D\* — o que constitui novo snapshot, não troca espontânea de alvo.

<a id="sec-6"></a>

## 6. Status do método e cenários inexistentes

| Classificação | Significado canônico | Efeito no `STATUS_METODO` |
|---|---|---|
| `CENARIO_NAO_CALCULAVEL` | O cenário deveria existir, mas falta dado material para calculá-lo. | **Rebaixa** |
| `CENARIO_NAO_APLICAVEL` | Os dados são suficientes, mas a regra metodológica não produz aquele cenário. | Não rebaixa |

`STATUS_METODO = DEFINITIVO_NA_DATA` exige que todos os cenários **aplicáveis** sejam plenamente calculáveis e que não exista bloqueio material. Um Híbrido legitimamente inexistente não impede status definitivo.

### 6.1. Incompatibilidade comportamental

```
SE    INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE com o cenário mais econômico
E     nenhuma alternativa aplicável for ECONOMICAMENTE_PROXIMA
ENTÃO
      STATUS_METODO = PROVISORIO
      REVISAO_HUMANA_OBRIGATORIA = SIM
```

Híbrido `NAO_APLICAVEL` com Bola de Neve `ECONOMICAMENTE_PROXIMA` **não** aciona revisão humana: a Bola de Neve permanece como alternativa comportamental possível.

<a id="sec-7"></a>

## 7. Publicação da ordem e versionamento

`ORDEM_QUITACAO` não é lista inicial congelada. É a sequência **projetada** produzida pela simulação completa no snapshot atual, considerando os recálculos previstos por quitação e por eventos materiais.

| Variável | Significado |
|---|---|
| `ORDEM_QUITACAO` | Sequência projetada completa produzida pela simulação. |
| `DIVIDA_ALVO_ATUAL` | Única dívida que recebe ataque extraordinário no estado atual. |
| `PROXIMA_DIVIDA` | Próxima dívida projetada, sujeita a recálculo no evento de quitação. |

A apresentação ao usuário utiliza sempre o termo "projetada". Internamente a variável permanece `ORDEM_QUITACAO`; não se cria variável nova apenas para o rótulo visual.

> **REDAÇÃO CANÔNICA AO USUÁRIO**
> Título: "Sua ordem projetada de quitação"
> Texto: "Com os dados e condições atuais, o PIQ projeta a seguinte sequência de quitação. A ordem poderá ser recalculada se ocorrer alguma mudança material durante a execução."

`JUSTIFICATIVA_POSICAO` permanece obrigatória para cada dívida da sequência projetada e pode utilizar estado futuro projetado pela simulação.

### 7.1. Versionamento

Ocorrendo quitação real ou `EVENTO_RECALCULO`, a ordem anterior não pode ser sobrescrita silenciosamente. A engine cria novo snapshot.

```
ORDEM_QUITACAO_V1   DATA_REFERENCIA = DD/MM/AAAA
ORDEM_QUITACAO_V2   DATA_REFERENCIA = DD/MM/AAAA
                    MOTIVO_RECALCULO = QUITACAO_D003
```

Cada snapshot preserva ordem anterior, data, motivo, inputs relevantes, método, dívida-alvo e justificativas. Toda saída do motor carimba `ENGINE_VERSION` e `PARAMETROS_VERSION`.
<a id="sec-8"></a>

## 8. Parâmetros

Todos os valores ajustáveis do motor. **Nenhum destes números pode ser escrito no código** — o motor os lê em tempo de execução.

| Parâmetro | Valor | Unidade | Significado | Status |
|---|---|---|---|---|
| `P_DIFERENCA_ECONOMICA_MATERIAL` | 1 | % | Desempate material entre cenários | ✅ Fechado |
| `P_CUSTO_ELEVADO_GATILHO_B7` | 4 | % a.m. | Gatilho de renegociação por custo alto | ✅ Fechado |
| `P_PRESSAO_GATILHO_B7` | 20 | % | Gatilho de renegociação por pressão individual | ✅ Fechado |
| `P_DESCONTO_RELEVANTE` | 10 | % | Oportunidade relevante de desconto | ✅ Fechado |
| `P_CUSTO_RELEVANTE_GATILHO_B8` | 2 | % a.m. | Triagem para troca | ✅ Fechado |
| `P_SALDO_MINIMO_TROCA` | 5000 | R$ | Saldo mínimo para triagem de troca | ✅ Fechado |
| `P_PRAZO_MINIMO_TROCA` | 12 | parcelas | Prazo mínimo para triagem de troca | ✅ Fechado |
| `P_QTD_BARREIRAS_CENTRAIS` | 4 | unidades | Quantidade central recomendada no piloto | ✅ Fechado |
| `P_LIMIAR_RISCO_RECAIDA` | regra D.4 | regra | Classificação BAIXO / MODERADO / ALTO | ✅ Fechado |
| `P_LIMIAR_RISCO_COMPORTAMENTAL_GERAL` | regra D.4 | regra | Classificação BAIXO / MODERADO / ALTO | ✅ Fechado |
| `P_MESES_VITORIA_RAPIDA` | 3 | meses | Teto de meses para a vitória estratégica do Híbrido | ✅ Fechado |
| `P_DIFERENCA_CUSTO_EQUIVALENTE` | 5 | % | Tolerância de penalidade de custo vs Avalanche | ✅ Fechado |
| `P_DIFERENCA_PRAZO_EQUIVALENTE` | 2 | meses | Tolerância de atraso de prazo vs Avalanche | ✅ Fechado |
| `P_REDUCAO_RENDA_VARIAVEL` | 0,20 | fração | Redução do fator de segurança por renda variável | 🔧 Calibrável |
| `P_REDUCAO_CONFIABILIDADE_MEDIA` | 0,05 | fração | Redução por confiabilidade média do dado | 🔧 Calibrável |
| `P_REDUCAO_CONFIABILIDADE_BAIXA` | 0,15 | fração | Redução por confiabilidade baixa do dado | 🔧 Calibrável |
| `P_REDUCAO_RISCO_COMPORTAMENTAL_ALTO` | 0,15 | fração | Redução por risco comportamental alto | 🔧 Calibrável |
| `P_REDUCAO_HISTORICO_RECAIDA` | 0,10 | fração | Redução por histórico de recaída | 🔧 Calibrável |
| `P_FATOR_SEGURANCA_MINIMO` | 0,60 | fator | Piso do fator de segurança | 🔧 Calibrável |
| `P_FATOR_RENDA_VARIAVEL` | 0,80 | fator | Fator aplicado sobre renda variável | 🔧 Calibrável |
| `P_PISO_CAPACIDADE_ABSOLUTO` | 100,00 | R$ | Componente absoluto do piso de capacidade | 🔧 Calibrável |
| `P_PISO_CAPACIDADE_PERCENTUAL` | 3 | % da renda | Componente percentual do piso de capacidade | 🔧 Calibrável |
| `P_TAXA_TOX_MODERADA` | 2 | % a.m. | Faixa de toxicidade — moderada | 🔧 Calibrável |
| `P_TAXA_TOX_ALTA` | 4 | % a.m. | Faixa de toxicidade — alta | 🔧 Calibrável |
| `P_TAXA_TOX_MUITO_ALTA` | 8 | % a.m. | Faixa de toxicidade — muito alta | 🔧 Calibrável |
| `P_TAXA_TOX_CRITICA` | 12 | % a.m. | Faixa de toxicidade — crítica | 🔧 Calibrável |
| `P_PRESSAO_INDIVIDUAL` | 5 / 10 / 20 / 30 | % | Faixas de pressão individual | 🔧 Calibrável |
| `P_PRESSAO_TOTAL` | 20 / 30 / 45 / 60 | % | Faixas de pressão total | 🔧 Calibrável |
| `P_ESCALA_0_10` | 3 / 6 | pontos | Cortes das escalas 0–10 | 🔧 Calibrável |
| `P_DIFERENCA_TAXAS_RELEVANTE` | 3 | p.p. a.m. | Diferença de taxas considerada relevante | 🔧 Calibrável |
| `P_REVISAO_DESCONTO` | 20 | % | Gatilho de revisão por desconto | 🔧 Calibrável |
| `P_REVISAO_REDUCAO_CUSTO_TROCA` | 15 | % | Gatilho de revisão por redução de custo em troca | 🔧 Calibrável |
| `P_REVISAO_CAPACIDADE_PCT` | 75 | % | Gatilho de revisão por variação de capacidade | 🔧 Calibrável |
| `P_REVISAO_CAPACIDADE_MESES` | 2 | meses | Janela de apuração do gatilho acima | 🔧 Calibrável |
| `P_HORIZONTE_ALERTA` | 5 | anos | Horizonte a partir do qual o plano gera alerta | 🔧 Calibrável |
| `P_HORIZONTE_MAXIMO_SIMULACAO` | 10 | anos | Teto de simulação | 🔧 Calibrável |
| `P_INCOMPATIBILIDADE_NECESSIDADE_VITORIA` | 7 | escala 0–10 | Corte de NECESSIDADE_VITORIA para incompatibilidade | 🔧 Calibrável |
| `P_CAIXA_VS_ESTRUTURAL` | — | R$ ou % | Corte de materialidade do GAP_CAIXA_VS_ESTRUTURAL | ⚠️ A calibrar |
| `P_AUTOPERCEPCAO` | — | regra | Divergência relevante entre autopercepção e cálculo | ⚠️ A calibrar |
| `REGRA_RESIDUO_ATAQUE` | CASCATA | enum | DESCARTA \| CASCATA — decidida como CASCATA | ✅ Fechado |
| `REGRA_RANQUEAMENTO` | EVENT_DRIVEN | enum | EVENT_DRIVEN \| MENSAL — decidida como EVENT_DRIVEN | ✅ Fechado |
| `REGRA_DELTA_RESIDUO` | RESIDUO | enum | RESIDUO \| CAPACIDADE_CHEIA — decidida como RESIDUO | ✅ Fechado |
| `ENGINE_VERSION` | 1.0.1 | texto | Carimbada em todo plano e relatório emitido | ✅ Fechado |
| `PARAMETROS_VERSION` | 1.0.1 | texto | Versão do conjunto de parâmetros | ✅ Fechado |
| `DATA_VIGENCIA` | data de publicação desta versão | data | Vigência do conjunto acima | ✅ Fechado |

"Calibrável" significa que o número pode mudar em versão paramétrica posterior. **Não** significa que o desenvolvedor possa alterá-lo.

<a id="sec-9"></a>

## 9. Regras do motor — índice normativo

As seções 2 a 7 em forma tabular, para consulta e rastreamento em código. Cada regra tem identificador estável.

### Ciclo mensal

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `M-01` | 1. Abrir o mês com os saldos e a capacidade disponíveis no início do período. | Devolutiva final §9 |
| `M-02` | 2. Aplicar juros, encargos e evolução contratual conforme o modelo de cada dívida. | Devolutiva final §9 |
| `M-03` | 3. Aplicar os pagamentos mensais normais de todas as dívidas, limitados ao saldo. | Devolutiva final §9 |
| `M-04` | 4. Aplicar o ataque adicional à DIVIDA_ALVO_ATUAL. | Devolutiva final §9 |
| `M-05` | 5. Se a dívida-alvo não for quitada: manter o mesmo alvo para o mês seguinte, salvo EVENTO_RECALCULO externo. | Devolutiva final §9 |
| `M-06` | 6. Se for quitada: confirmar a quitação, atualizar o estado e calcular RESIDUO_ATAQUE_M. | Devolutiva final §9 |
| `M-07` | 7. Havendo RESIDUO_ATAQUE_M > 0: recalcular a ordem das dívidas restantes, selecionar o novo alvo e aplicar o resíduo ainda no mês m. | Devolutiva final §2 e §9 |
| `M-08` | 8. Repetir o passo 7 enquanto houver resíduo e houver dívida elegível. | Devolutiva final §9 |
| `M-09` | 9. Encerrar o mês. | Devolutiva final §9 |
| `M-10` | 10. Consolidar o VALOR_FLUXO_LIBERADO das dívidas quitadas no período. | Devolutiva final §9 |
| `M-11` | 11. Incorporar o fluxo liberado à capacidade a partir de m+1. | Devolutiva final §3 e §9 |
| `M-12` | 12. Reavaliar a ordem para o próximo período somente se houve quitação no período ou EVENTO_RECALCULO externo material. Na ausência de ambos, preservar a DIVIDA_ALVO_ATUAL. | Devolutiva final §9 |

### Gatilho de recálculo

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `R-01` | RECALCULAR_ORDEM = QUITACAO_CONFIRMADA (de qualquer dívida, inclusive a que se encerrou apenas pelo pagamento normal) OU EVENTO_RECALCULO_EXTERNO. | Devolutiva final §1 · Confirmação A.1 |
| `R-02` | RECALCULAR_ORDEM ≠ VIRADA_DO_MES. A passagem ordinária do tempo nunca recalcula a ordem. | Devolutiva final §1 |
| `R-03` | Ocorrem dois ranqueamentos distintos após uma quitação: (a) imediato, para destinar o ataque ainda disponível no mês m, com DELTA = RESIDUO_ATAQUE_M; (b) no encerramento do mês, para definir o alvo de m+1, com DELTA = capacidade de m+1 já acrescida do fluxo liberado. | Confirmação A.1 + A.2 · §9 passos 11 e 12 |
| `R-04` | Alteração meramente cadastral, correção textual, mudança cosmética de registro ou passagem ordinária do tempo não constitui EVENTO_RECALCULO. | Devolutiva final · TRAVA |
| `R-05` | Ocorrendo EVENTO_RECALCULO material, a engine DEVE reavaliar todas as decisões afetadas e gerar novo snapshot. Recalcular não implica mudar: se método, D* e ordem seguirem sendo os melhores, permanecem. | Confirmação A.3 |

### Resíduo de ataque

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `A-01` | RESIDUO_ATAQUE_M = ATAQUE_DISPONIVEL_M − ATAQUE_EFETIVAMENTE_NECESSARIO_PARA_QUITAR_ALVO. | Devolutiva final §2 |
| `A-02` | Se RESIDUO_ATAQUE_M > 0, aplicar à próxima dívida elegível ainda no mês m, repetindo até esgotar o ataque ou as dívidas elegíveis. | Devolutiva final §2 |
| `A-03` | Ao escolher o destino do resíduo: DELTA_TESTE_AVALANCHE = MIN(RESIDUO_ATAQUE_M, VALOR_RELEVANTE_PARA_QUITACAO). Nunca usar a capacidade mensal cheia nessa decisão. | Confirmação A.2 |
| `A-04` | Não havendo dívida elegível, o valor é registrado como ATAQUE_NAO_UTILIZADO e permanece como caixa ou patrimônio do usuário. Nenhum valor disponível pode desaparecer da simulação por convenção de cálculo. | Devolutiva final §2 · TRAVA |

### Fluxo liberado

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `F-01` | CAPACIDADE_ATAQUE_M+1 = CAPACIDADE_ATAQUE_M + VALOR_FLUXO_LIBERADO_M + demais alterações aplicáveis. | Devolutiva final §3 |
| `F-02` | O pagamento mensal liberado não retroage para aumentar a capacidade do mesmo mês da quitação. | Devolutiva final §3 |
| `F-03` | TRAVA DE DUPLA CONTAGEM: o mesmo valor não pode ser usado simultaneamente como pagamento normal do mês m e como capacidade adicional retroativa no próprio mês m. | Devolutiva final · TRAVA |

### Avalanche

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `O-01` | Alvo escolhido pelo maior BENEFICIO_MARGINAL_AMORTIZACAO no momento do ranqueamento, com DELTA_TESTE_AVALANCHE = MIN(capacidade aplicável, VALOR_RELEVANTE_PARA_QUITACAO). | Devolutiva final §4 |
| `O-02` | Uma vez escolhido, o alvo permanece até ser quitado ou até EVENTO_RECALCULO externo. Não há reranqueamento mensal. | Devolutiva final §4 |
| `O-03` | Havendo resíduo no mês da quitação, o recálculo ocorre imediatamente após a quitação e antes da aplicação do resíduo. | Devolutiva final §4 |

### Bola de Neve

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `O-04` | Alvo escolhido pelo menor VALOR_RELEVANTE_PARA_QUITACAO, respeitados os gates. Alvo fixo até quitação ou evento; não é reranqueada mensalmente. | Devolutiva final §5 |
| `O-05` | Desempates, nesta ordem: maior VALOR_FLUXO_LIBERADO; maior custo financeiro; maior PESO_EMOCIONAL; DIVIDA_ID como desempate técnico final. | Devolutiva final §5.1 |

### Híbrido

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `H-01` | ETAPA 1 — calcular ORDEM_AVALANCHE como referência de eficiência. | Devolutiva item 3 |
| `H-02` | ETAPA 2 — para cada dívida elegível D diferente da primeira da ORDEM_AVALANCHE, simular CENARIO_HIBRIDO_D = D primeiro + Avalanche para as restantes, respeitados os gates. | Devolutiva item 3 |
| `H-03` | ETAPA 3 — D é candidata válida se, cumulativamente: MESES_PRIMEIRA_VITORIA ≤ P_MESES_VITORIA_RAPIDA E PENALIDADE_CUSTO_VS_AVALANCHE ≤ P_DIFERENCA_CUSTO_EQUIVALENTE E ATRASO_PRAZO_VS_AVALANCHE ≤ P_DIFERENCA_PRAZO_EQUIVALENTE. | Devolutiva item 3 |
| `H-04` | ETAPA 4 — havendo várias candidatas, escolher lexicograficamente: 1º menor MESES_PRIMEIRA_VITORIA; 2º menor PENALIDADE_CUSTO_VS_AVALANCHE; 3º maior VALOR_FLUXO_LIBERADO; 4º maior PESO_EMOCIONAL; 5º maior BENEFICIO_MARGINAL_AMORTIZACAO; 6º menor DIVIDA_ID. | Devolutiva item 3 |
| `H-05` | ETAPA 5 — ORDEM_HIBRIDA = D* seguida da Avalanche event-driven das restantes. | Devolutiva item 3 · §6 |
| `H-06` | FASE_HIBRIDA_1: DIVIDA_ALVO_ATUAL = D* até QUITACAO_D* ou EVENTO_RECALCULO_EXTERNO. D* não pode ser substituída pela evolução mensal dos saldos. | Devolutiva final §6 |
| `H-07` | FASE_HIBRIDA_2: Avalanche event-driven — recalcular após cada quitação, nunca por passagem de mês. | Devolutiva final §6 |
| `H-08` | ETAPA 6 — não havendo candidata, CENARIO_HIBRIDO = NAO_APLICAVEL e ORDEM_HIBRIDA = NAO_APLICAVEL. Não se fabrica um Híbrido. | Devolutiva item 3 · §6.1 |

### Status do método

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `S-01` | CENARIO_NAO_CALCULAVEL = o cenário deveria existir, mas falta dado material. Somente este rebaixa STATUS_METODO. | Devolutiva final §6.1 |
| `S-02` | CENARIO_NAO_APLICAVEL = os dados são suficientes, mas a regra metodológica não produz aquele cenário. Não rebaixa STATUS_METODO. | Devolutiva final §6.1 |
| `S-03` | STATUS_METODO = DEFINITIVO_NA_DATA exige que todos os cenários aplicáveis sejam plenamente calculáveis e que não exista bloqueio material. | Devolutiva final §6.1 |
| `S-04` | SE INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE com o cenário mais econômico E nenhuma alternativa aplicável for ECONOMICAMENTE_PROXIMA, ENTÃO STATUS_METODO = PROVISORIO e REVISAO_HUMANA_OBRIGATORIA = SIM. | Devolutiva final §6.2 |
| `S-05` | Híbrido NAO_APLICAVEL com Bola de Neve ECONOMICAMENTE_PROXIMA não aciona revisão humana: a Bola de Neve pode ser avaliada como alternativa comportamental. | Devolutiva final §6.2 |

### Ordem publicada

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `Q-01` | ORDEM_QUITACAO = sequência realizada na simulação vigente. Não é lista inicial congelada nem sequência imutável. | Devolutiva final §7 |
| `Q-02` | Apresentação ao usuário usa sempre o termo "projetada". A variável interna permanece ORDEM_QUITACAO; não criar variável nova para o rótulo visual. | Devolutiva final §7.1 |
| `Q-03` | Título ao usuário: "Sua ordem projetada de quitação". Texto: "Com os dados e condições atuais, o PIQ projeta a seguinte sequência de quitação. A ordem poderá ser recalculada se ocorrer alguma mudança material durante a execução." | Devolutiva final §7.1 |
| `Q-04` | DIVIDA_ALVO_ATUAL = única dívida que recebe ataque extraordinário no estado atual. PROXIMA_DIVIDA = próxima dívida projetada, sujeita a recálculo no evento de quitação. | Devolutiva final §7.2 |
| `Q-05` | JUSTIFICATIVA_POSICAO é obrigatória para cada dívida da sequência projetada e pode utilizar estado futuro projetado pela simulação. | Devolutiva final §7.3 |

### Versionamento

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `V-01` | Ocorrendo quitação real ou EVENTO_RECALCULO, a ordem anterior não pode ser sobrescrita silenciosamente: criar novo snapshot (ORDEM_QUITACAO_V1, V2, ...). | Devolutiva final §8 |
| `V-02` | Cada snapshot preserva: ordem anterior, data, MOTIVO_RECALCULO, inputs relevantes, método, dívida-alvo e justificativas. | Devolutiva final §8 |
| `V-03` | Toda saída do motor carimba ENGINE_VERSION e PARAMETROS_VERSION. | Esta especificação |

### Troca / Bloco 8

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `T-01` | Em troca com DINHEIRO_NOVO > 0, a comparação econômica usa CENARIO_SUBSTITUICAO_EQUIVALENTE, correspondente apenas ao valor necessário para substituir a dívida antiga, sob as condições da nova operação. | Gabarito B-05 |
| `T-02` | O DINHEIRO_NOVO é tratado separadamente como novo endividamento, jamais como economia. Se destinado a consumo ou despesa não essencial, CLASSIFICACAO_TROCA = NAO_RECOMENDADA. | Gabarito B-05 |

### Precisão

| Regra | Enunciado normativo | Origem |
|---|---|---|
| `G-01` | Precisão interna integral; arredondamento apenas na exibição. | Matriz |
| `G-02` | Tolerância de homologação: ± R$ 0,05 em valores monetários acumulados, exclusivamente por arredondamento de centavos. | Devolutiva final §10.1 |

<a id="sec-10"></a>

## 10. Gabaritos de homologação

A engine é aprovada quando reproduz os três gabaritos numéricos e satisfaz os cinco invariantes.

### 10.1. Gabarito C — valores oficiais

| Método | Prazo | Custo futuro total | 1ª vitória | Sequência |
|---|---|---|---|---|
| **Avalanche** | 6 meses | R$ 23719,46 | Mês 4 | D001 → D002 → D003 |
| **Bola de Neve** | 6 meses | R$ 24463,97 | Mês 1 | D003 → D002 → D001 |
| **Híbrido** | 6 meses | R$ 24107,20 | Mês 1 | D003 → D001 → D002 |

`PENALIDADE_ECONOMICA_HIBRIDO` = 1,635% · `ATRASO_DE_PRAZO` = 0 mês · D\* = D003 · `ECONOMICAMENTE_PROXIMO(HIBRIDO)` = SIM · `VITORIA_RAPIDA(HIBRIDO)` = SIM · **`METODO_RECOMENDADO_PIQ` = HIBRIDO**

> Os valores anteriores do Gabarito C, que utilizavam descarte do resíduo do ataque, estão **revogados**.

### 10.2. Todos os casos

#### `GAB-A` — Déficit / falso superávit observado

*Numérico ponta a ponta*

**Entradas.** RENDA_TOTAL_RECORRENTE = 8.000 · DESPESAS_OPERACIONAIS_ATUAIS = 6.500 · DESPESAS_NAO_MENSAIS_NORMALIZADAS = 500 · D001: devido 1.200, efetivo 0 (atrasada) · D002: devido 800, efetivo 800 · inventário completo

**Saídas esperadas.** PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES = 2.000 · PAGAMENTOS_EFETIVOS_DIVIDAS = 800 · RESULTADO_CAIXA_OBSERVADO = +200 · RESULTADO_MENSAL_ATUAL = −1.000 · GAP_CAIXA_VS_ESTRUTURAL = 1.200 · DEFICIT_MENSAL = 1.000 · CAPACIDADE_ATAQUE_ATUAL = 0 · MODO_ESTABILIZACAO = SIM

**Invariante.** O sistema não pode afirmar que existem R$ 200 de sobra: o saldo observado é produzido pelo não pagamento de R$ 1.200 que continua devido. FASE 1 = Estabilização; FASE 2 = ordem de quitação condicional.

#### `GAB-B` — Equilíbrio frágil / potencial não é capacidade

*Numérico ponta a ponta*

**Entradas.** RENDA = 10.000 · DESPESAS_OPERACIONAIS = 7.600 · NÃO MENSAIS = 400 · DEVIDOS = 1.800 · EFETIVOS = 1.800 · CAPACIDADE_ATAQUE_DECLARADA = 500 · renda fixa · confiabilidade alta · sem recaída · risco comportamental não alto · ECONOMIA_POTENCIAL_IMEDIATA = 400 identificada e aceita, não implementada

**Saídas esperadas.** RESULTADO_MENSAL_ATUAL = 200 · RESULTADO_CAIXA_OBSERVADO = 200 · PISO_CAPACIDADE = MAX(100; 3% × 10.000) = 300 · STATUS_FINANCEIRO = EQUILIBRIO_FRAGIL · CAPACIDADE_ATAQUE_ATUAL = 200 · BASE_CONSERVADORA = MIN(200;500) = 200 · FATOR_SEGURANCA = 1,00 · CAPACIDADE_ATAQUE_CONSERVADORA = 200 · CAPACIDADE_ATAQUE_POTENCIAL = 600

**Invariante.** O cronograma-base não pode utilizar R$ 600. Enquanto os R$ 400 de economia não forem implementados, o máximo do cenário-base é R$ 200/mês. O Plano de Execução prioriza construção de capacidade.

#### `GAB-C` — Superávit / método Híbrido

*Numérico ponta a ponta*

**Entradas.** RENDA = 15.000 · DESPESAS_OPERACIONAIS = 8.500 · NÃO MENSAIS = 500 · CAPACIDADE_ATAQUE_CONSERVADORA = 3.000 · D001: saldo 12.000, 4% a.m., pgto 700 · D002: saldo 7.000, 2% a.m., pgto 500 (após portabilidade verdadeira: DINHEIRO_NOVO = 0, sem nova garantia, CLASSIFICACAO_TROCA = RECOMENDAVEL) · D003: saldo 3.000, 0%, pgto 300, peso emocional alto · NECESSIDADE_VITORIA = 8 · HISTORICO_ABANDONO = SIM · NIVEL_CONTROLE = FORTE · RISCO_RECAIDA = BAIXO

**Saídas esperadas.** Avalanche: 6m · R$ 23719.46 · 1ª vitória mês 4 · D001 → D002 → D003  
Bola de Neve: 6m · R$ 24463.97 · 1ª vitória mês 1 · D003 → D002 → D001  
Híbrido: 6m · R$ 24107.20 · 1ª vitória mês 1 · D003 → D001 → D002  
PENALIDADE_ECONOMICA_HIBRIDO = 1,635% · ATRASO_DE_PRAZO = 0 mês · D* = D003

**Invariante.** INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE = SIM · ECONOMICAMENTE_PROXIMO(HIBRIDO) = SIM · VITORIA_RAPIDA(HIBRIDO) = SIM · METODO_RECOMENDADO_PIQ = HIBRIDO. Valores anteriores que usavam descarte do resíduo estão revogados.

#### `GAB-01` — Dupla contagem — seguro dentro da parcela

*Invariante*

**Entradas.** Parcela = R$ 1.000 · seguro = R$ 50 · SEGURO_INCLUIDO_PARCELA = SIM

**Saídas esperadas.** Pagamento mensal / custo de caixa permanece R$ 1.000.

**Invariante.** O pagamento mensal não pode virar R$ 1.050. O seguro é informacional para decomposição e não é somado novamente.

#### `GAB-02` — Inventário incompleto

*Invariante*

**Entradas.** INVENTARIO_COMPLETO = FALSO

**Saídas esperadas.** Diagnóstico parcial permitido · totais apresentados como parciais · ORDEM_STATUS ≠ DEFINITIVA_NA_DATA · STATUS_METODO no máximo PROVISORIO

**Invariante.** Nenhum cronograma final pode ser apresentado como definitivo.

#### `GAB-03` — Rotativo sem parcela fixa

*Invariante*

**Entradas.** TIPO_DIVIDA = ROTATIVO · SALDO_DEVEDOR_ATUAL = DESCONHECIDO · PAGAMENTO_MENSAL_EFETIVO = DESCONHECIDO · sem obrigação fixa conhecida

**Saídas esperadas.** Dívida marcada como INFORMACAO_PENDENTE · trajetória e cronograma dessa dívida = BLOQUEADO

**Invariante.** Não inventar saldo, parcela nem pagamento. Se material para o plano, impede ordem definitiva.

#### `GAB-04` — Modo Estabilização ponta a ponta

*Invariante de relatório*

**Entradas.** Entradas do GAB-A: RESULTADO_CAIXA_OBSERVADO = +200 e RESULTADO_MENSAL_ATUAL = −1.000

**Saídas esperadas.** MODO_ESTABILIZACAO = SIM · CAPACIDADE_ATAQUE_ATUAL = 0 · ações de estabilização e intervenção em primeiro lugar

**Invariante.** O relatório não pode chamar os R$ 200 de sobra. Método, ordem de ataque e cronograma aparecem como FASE 2 — CONDICIONAL À ESTABILIZAÇÃO.

#### `GAB-05` — Troca com DINHEIRO_NOVO > 0

*Invariante*

**Entradas.** Quitação da dívida antiga = R$ 30.000 · nova operação = R$ 40.000 · DINHEIRO_NOVO = R$ 10.000

**Saídas esperadas.** CENARIO_SUBSTITUICAO_EQUIVALENTE calculado apenas sobre os R$ 30.000, sob as condições da nova operação

**Invariante.** Os R$ 10.000 adicionais são novo endividamento, jamais economia. Se destinados a consumo ou despesa não essencial, CLASSIFICACAO_TROCA = NAO_RECOMENDADA.

### 10.3. Tolerância

± R$ 0,05 em valores monetários acumulados, exclusivamente por diferenças de arredondamento de centavos.

**Tolerância zero** para: método recomendado, ordem, gates, status, número de meses, primeira vitória, classificação, dupla contagem, aplicação de resíduo, gatilho de recálculo, D\*, e `NAO_APLICAVEL` versus `PROVISORIO`.

<a id="sec-11"></a>

## 11. Questionário — 291 perguntas

Especificação de coleta. A interface deve ser **gerada a partir desta seção**, não codificada pergunta a pergunta — assim uma nova versão vira edição de registro, não reescrita de código. Os IDs são estáveis e nunca devem ser reaproveitados.

**Legenda de obrigatoriedade:** `OBR` sempre exibida · `COND` condicional · `OPT` opcional · `REP` repetida por item (dívida, vínculo, despesa, ativo).

**291 perguntas · 115 delas são REP.**

| Bloco | Tema | Perguntas | REP |
|---|---|---|---|
| [Bloco 1](#bloco-1) | Pacto da Virada | 16 | 3 |
| [Bloco 2](#bloco-2) | Autopercepção e controle | 15 | 0 |
| [Bloco 3](#bloco-3) | Fluxo de caixa real | 57 | 20 |
| [Bloco 4](#bloco-4) | Vínculos, margens e patrimônio | 49 | 37 |
| [Bloco 5](#bloco-5) | Inventário de dívidas | 58 | 55 |
| [Bloco 7](#bloco-7) | Renegociação | 21 | 0 |
| [Bloco 8](#bloco-8) | Troca e portabilidade | 25 | 0 |
| [Bloco 9](#bloco-9) | Comportamento e método | 6 | 0 |
| [Bloco 10](#bloco-10) | Ataque imediato | 2 | 0 |
| [Bloco 11](#bloco-11) | Execução e acompanhamento | 23 | 0 |
| [Bloco 12](#bloco-12) | Blindagem e pós-quitação | 19 | 0 |

> O Bloco 6 não coleta dados: é a etapa de motor que roda entre a Etapa B e a Etapa D.

<a id="bloco-1"></a>

### Bloco 1 — Pacto da Virada

*16 perguntas.* Índice: `B1.01` · `B1.02` · `B1.03` · `B1.03A` · `B1.04` · `B1.05` · `B1.06` · `B1.06A` · `B1.06B` · `B1.06C` · `B1.07` · `B1.08` · `B1.09` · `B1.10` · `B1.11` · `B1.12`

#### `B1.01` — Pacto

**OBR** · *Seleção única*

> Para executar este plano, qual destas frases melhor representa sua situação hoje?

**Opções:** Estou disposto(a) a não assumir novas dívidas ou parcelamentos enquanto estiver executando o · PIQ, salvo alguma operação de renegociação ou troca que faça parte do próprio plano. · Quero assumir esse compromisso, mas hoje ainda existe o risco de eu precisar recorrer a crédito ou · parcelamento. · Neste momento, ainda não consigo assumir esse compromisso.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `PACTO` |
| Valor interno / mapeamento | A = ESTABELECIDO · B = EM_CONSTRUCAO · C = NAO_ESTABELECIDO |
| Salto / consequência | NAO_ESTABELECIDO não bloqueia o PIQ. |
| Uso pelo motor | Risco de execução; RISCO_RECAIDA |

#### `B1.02` — Nova operação de crédito

**OBR** · *Seleção única*

> Hoje, você já pretende ou considera provável contratar algum novo crédito nos próximos meses?

*Considere empréstimo, financiamento, refinanciamento, uso de limite ou outra nova operação de crédito.*

**Opções:** Sim, já pretendo contratar. · Talvez. Existe uma possibilidade real. · Não.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `NOVA_DIVIDA_PREVISTA` |
| Valor interno / mapeamento | SIM · TALVEZ · NAO |
| Salto / consequência | Sim ou Talvez → abre B1.03, B1.04, B1.05. |
| Uso pelo motor | RISCO_RECAIDA; calendário de risco |

#### `B1.03` — Finalidade

**COND** · *Seleção única*

> Qual é a principal finalidade desse novo crédito?

**Opções:** Pagar uma necessidade ou despesa essencial. · Fazer uma compra ou financiar consumo. · Lidar com uma emergência ou imprevisto. · Quitar, substituir ou reorganizar uma dívida que já existe. · Outra finalidade.

| Campo | Valor |
|---|---|
| Condição de exibição | B1.02 = Sim ou Talvez |
| Variável gravada | `FINALIDADE_NOVA_DIVIDA` |
| Valor interno / mapeamento | NECESSIDADE · CONSUMO · EMERGENCIA · REESTRUTURACAO_DIVIDA · OUTRA |
| Salto / consequência | "Outra finalidade" → abre B1.03A. |
| Uso pelo motor | RISCO_RECAIDA (diferenciar consumo de reestruturação) |

#### `B1.03A` — Finalidade — outra

**OPT** · *Texto curto*

> Qual?

| Campo | Valor |
|---|---|
| Condição de exibição | B1.03 = Outra finalidade |
| Variável gravada | `FINALIDADE_NOVA_DIVIDA_OUTRA` |
| UX / observação | Texto curto; somente após seleção de "Outra". |

#### `B1.04` — Valor

**COND** · *Moeda R$*

> Qual é o valor aproximado desse novo crédito?

**Opções:** R$ ______ · Ainda não sei o valor.

| Campo | Valor |
|---|---|
| Condição de exibição | B1.02 = Sim ou Talvez |
| Variável gravada | `VALOR_NOVA_DIVIDA` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | Calendário futuro (não entra no fluxo atual) |

#### `B1.05` — Momento previsto

**COND** · *Seleção única*

> Quando você imagina que essa contratação pode acontecer?

**Opções:** Nos próximos 30 dias. · Entre 1 e 3 meses. · Entre 4 e 6 meses. · Entre 7 e 12 meses. · Depois de 12 meses. · Ainda não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B1.02 = Sim ou Talvez |
| Variável gravada | `JANELA_NOVA_DIVIDA` |
| Valor interno / mapeamento | ATE_30D · 1_3M · 4_6M · 7_12M · APOS_12M · NAO_SEI. DATA_NOVA_DIVIDA gravada somente quando houver data concreta. |
| Uso pelo motor | Calendário de risco |

#### `B1.06` — Obrigação futura

**OBR** · *Seleção única*

> Nos próximos 12 meses, você já sabe de alguma despesa relevante que terá de pagar e para a qual ainda não reservou todo o dinheiro necessário?

*Por exemplo: imposto, matrícula, tratamento, manutenção importante, mudança, viagem obrigatória ou outra despesa já previsível.*

**Opções:** Sim. · Não. · Não sei / ainda não consigo prever.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `OBRIGACAO_FUTURA_INEVITAVEL` |
| Valor interno / mapeamento | SIM · NAO · NAO_SEI |
| Salto / consequência | Sim → abre ficha REP B1.06A–C (permitir mais de uma obrigação). |
| Uso pelo motor | Sustentabilidade futura |

#### `B1.06A` — Obrigação futura — ficha REP

**COND** · **REP** · *Seleção única*

> Que despesa é essa?

**Opções:** Imposto ou obrigação anual · Educação · Saúde · Moradia · Veículo · Despesa familiar · Mudança · Viagem necessária · Outra

| Campo | Valor |
|---|---|
| Condição de exibição | B1.06 = Sim |
| Variável gravada | `TIPO_OBRIGACAO_FUTURA` |

#### `B1.06B` — Obrigação futura — ficha REP

**COND** · **REP** · *Moeda R$*

> Quanto você estima que precisará pagar?

**Opções:** R$ ______ · Ainda não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B1.06 = Sim |
| Variável gravada | `VALOR_OBRIGACAO_FUTURA` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B1.06C` — Obrigação futura — ficha REP

**COND** · **REP** · *Seleção única*

> Quando essa despesa deve acontecer?

**Opções:** Próximos 30 dias · 1–3 meses · 4–6 meses · 7–12 meses · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B1.06 = Sim |
| Variável gravada | `JANELA_OBRIGACAO_FUTURA` |

#### `B1.07` — Novo parcelamento

**OBR** · *Seleção única*

> Você já pretende fazer alguma nova compra parcelada nos próximos meses?

*Considere cartão, crediário ou outro parcelamento de compra. Não inclua aqui parcelamentos que já existem.*

**Opções:** Sim. · Talvez. · Não.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `NOVO_PARCELAMENTO_PREVISTO` |
| Valor interno / mapeamento | SIM · TALVEZ · NAO |
| Uso pelo motor | RISCO_RECAIDA; RISCO_COMPORTAMENTAL_GERAL |

#### `B1.08` — Uso de crédito

**OBR** · *Checklist (múltipla)*

> Hoje, você considera usar limite ou crédito disponível para alguma destas situações?

**Opções:** Para pagar despesas normais do mês. · Para uma compra ou gasto de consumo. · Para uma emergência. · Para pagar outra dívida. · Para substituir uma dívida cara por outra potencialmente mais barata. · Talvez eu precise usar, mas ainda não sei para quê. · Não pretendo utilizar crédito disponível.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `USO_CREDITO_PREVISTO` |
| Valor interno / mapeamento | DESPESAS_MES · CONSUMO · EMERGENCIA · OUTRA_DIVIDA · REESTRUTURACAO · INDEFINIDO · NAO_PRETENDE |
| Uso pelo motor | RISCO_RECAIDA (diferenciar consumo de reestruturação) |
| Exclusividade | "Não pretendo utilizar crédito disponível" é exclusiva. |

#### `B1.09` — Mecanismo de déficit

**OBR** · *Checklist (múltipla)*

> Quando o dinheiro do mês não é suficiente, o que você costuma fazer?

**Opções:** Corto ou adio algum gasto. · Uso dinheiro da reserva. · Uso cartão de crédito. · Entro no cheque especial. · Faço empréstimo ou uso crédito pré-aprovado. · Parcelo contas ou compras para caber no mês. · Atraso alguma conta ou dívida. · Peço ajuda financeira a familiar ou outra pessoa. · Busco renda extra ou vendo alguma coisa. · Isso normalmente não acontece comigo. · Outra situação.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `MECANISMO_DEFICIT` |
| Valor interno / mapeamento | CORTE · RESERVA · CARTAO · CHEQUE_ESPECIAL · EMPRESTIMO · PARCELAMENTO · ATRASO · TERCEIRO · RENDA_EXTRA · NAO_OCORRE · OUTRA |
| Salto / consequência | "Outra situação" → texto curto OPT. |
| Uso pelo motor | RISCO_RECAIDA; RISCO_COMPORTAMENTAL_GERAL; Bloco 12 |
| Exclusividade | "Isso normalmente não acontece comigo" é exclusiva. |

#### `B1.10` — Histórico de recaída

**OBR** · *Seleção única*

> Nos últimos 12 meses, você assumiu alguma nova dívida ou parcelamento mesmo já tendo outras dívidas em aberto?

**Opções:** Sim, mais de uma vez. · Sim, uma vez. · Não. · Não tenho certeza.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `HISTORICO_RECAIDA` |
| Valor interno / mapeamento | HISTORICO_RECAIDA: SIM (A ou B) · NAO · NAO_SEI. Auxiliar FREQUENCIA_RECAIDA_RECENTE: MAIS_DE_UMA · UMA · NENHUMA · NAO_SEI |
| Salto / consequência | Sim → abre B1.11. |
| Uso pelo motor | RISCO_RECAIDA; fator de segurança; Bloco 9 |

#### `B1.11` — Causa da recaída

**COND** · *Seleção única*

> Pensando principalmente nessa nova dívida ou parcelamento, qual foi o motivo mais importante?

**Opções:** A renda não foi suficiente para as despesas do mês. · Apareceu uma emergência ou imprevisto. · Eu não tinha reserva financeira. · Usei crédito ou parcelamento para conseguir fazer uma compra. · Fiz uma compra por impulso ou sem planejamento. · Mantive um padrão de gastos que meu orçamento não comportava. · Assumi a dívida para ajudar outra pessoa. · Fiz uma dívida para pagar outra dívida. · Perdi o controle ou não sabia exatamente quanto já estava comprometido. · Outro motivo. · Não consigo identificar um motivo principal.

| Campo | Valor |
|---|---|
| Condição de exibição | B1.10 = Sim (uma vez ou mais de uma vez) |
| Variável gravada | `CAUSA_RECAIDA` |
| Valor interno / mapeamento | RENDA_INSUFICIENTE · EMERGENCIA · SEM_RESERVA · COMPRA_CREDITO · IMPULSO · PADRAO_VIDA · AJUDA_TERCEIRO · DIVIDA_PARA_DIVIDA · FALTA_CONTROLE · OUTRO · NAO_IDENTIFICA |
| Salto / consequência | "Outro motivo" → texto curto OPT. |
| Uso pelo motor | Bloco 12 |

#### `B1.12` — Participação familiar

**OBR** · *Seleção única*

> Existe outra pessoa cuja renda, gastos ou decisões financeiras influenciem diretamente a execução do seu plano?

**Opções:** Não. Minha vida financeira e as decisões deste plano dependem principalmente de mim. · Sim. Essa pessoa conhece a situação e está alinhada comigo. · Sim. Essa pessoa conhece a situação, mas ainda não estamos totalmente alinhados. · Sim. Essa pessoa participa das finanças, mas conhece pouco ou ainda não conhece a situação · completa.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `PARTICIPACAO_FAMILIAR` |
| Valor interno / mapeamento | A = NAO_APLICAVEL · B = ALINHADA · C = PARCIALMENTE_ALINHADA · D = ALINHAMENTO_NECESSARIO |
| Salto / consequência | C ou D → pode gerar ACAO_ALINHAMENTO_FAMILIAR (B12.13). |
| Uso pelo motor | Bloco 12 Derivadas pelo motor, nunca perguntadas: RISCO_RECAIDA · RISCO_COMPORTAMENTAL_GERAL são derivados pelo motor a partir de B1.01–B1.12 e do Bloco 2. Nunca perguntar. BLOCO 2 Controle Absoluto Quanto da vida financeira o usuário realmente enxerga TELA DE ABERTURA Agora precisamos saber quanto da sua vida financeira você realmente consegue enxergar. Não queremos avaliar se você é ‘bom’ ou ‘ruim’ com dinheiro. Queremos descobrir se os números que você vê hoje representam de fato o que acontece no seu mês — porque um plano só funciona quando parte de uma fotografia confiável. |

<a id="bloco-2"></a>

### Bloco 2 — Autopercepção e controle

*15 perguntas.* Índice: `B2.01` · `B2.02` · `B2.03` · `B2.04` · `B2.05` · `B2.05A` · `B2.06` · `B2.07` · `B2.08` · `B2.09` · `B2.10` · `B2.10A` · `B2.11` · `B2.12` · `B2.13`

#### `B2.01` — Registro

**OBR** · *Seleção única*

> Hoje, quanto dos seus gastos você costuma registrar ou acompanhar de alguma forma?

**Opções:** Praticamente todos os meus gastos. · A maior parte, mas alguns ficam de fora. · Apenas uma parte dos gastos. · Registro muito pouco ou só de vez em quando. · Não registro meus gastos atualmente.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `REGISTRO_GASTOS` |
| Valor interno / mapeamento | TUDO · MAIORIA · PARTE · RARAMENTE · NAO_REGISTRA |
| Salto / consequência | NAO_REGISTRA → não exibir B2.02, B2.03, B2.04 e B2.05 (derivados logicamente: sem frequência, sem defasagem, sem cobertura). |
| Uso pelo motor | NIVEL_CONTROLE; CONFIABILIDADE_DADOS |

#### `B2.02` — Frequência

**COND** · *Seleção única*

> Com que regularidade você costuma atualizar esse controle?

**Opções:** Todos ou quase todos os dias. · Algumas vezes por semana. · Uma vez por semana. · Algumas vezes por mês. · Só quando percebo que preciso conferir o dinheiro. · Não existe uma frequência definida.

| Campo | Valor |
|---|---|
| Condição de exibição | B2.01 ≠ NAO_REGISTRA |
| Variável gravada | `FREQUENCIA_REGISTRO` |
| Valor interno / mapeamento | DIARIA · VARIAS_SEMANA · SEMANAL · VARIAS_MES · SOB_DEMANDA · INDEFINIDA |
| Uso pelo motor | NIVEL_CONTROLE |

#### `B2.03` — Defasagem

**COND** · *Seleção única*

> Quando você registra um gasto, normalmente faz isso quando?

**Opções:** Na hora em que gasto. · No mesmo dia. · Até alguns dias depois. · No fim da semana. · Só no fim do mês ou quando vou conferir as contas. · Não tenho um padrão.

| Campo | Valor |
|---|---|
| Condição de exibição | B2.01 ≠ NAO_REGISTRA |
| Variável gravada | `DEFASAGEM_REGISTRO` |
| Valor interno / mapeamento | NA_HORA · MESMO_DIA · DIAS_DEPOIS · FIM_SEMANA · FIM_MES · SEM_PADRAO |
| Uso pelo motor | CONFIABILIDADE_DADOS |

#### `B2.04` — Pequenos gastos

**COND** · *Seleção única*

> E aqueles gastos pequenos — café, lanche, estacionamento, aplicativo, pequenas compras, Pix de baixo valor — costumam entrar no seu controle?

**Opções:** Sim, praticamente todos. · A maioria. · Alguns. · Quase nenhum. · Normalmente não entram.

| Campo | Valor |
|---|---|
| Condição de exibição | B2.01 ≠ NAO_REGISTRA |
| Variável gravada | `COBERTURA_PEQUENOS_GASTOS` |
| Valor interno / mapeamento | TODOS · MAIORIA · ALGUNS · QUASE_NENHUM · NAO_ENTRAM |
| Uso pelo motor | CONFIABILIDADE_DADOS |

#### `B2.05` — Meios de pagamento

**COND** · *Seleção única*

> Pensando apenas nas formas de pagamento que você realmente usa, seu controle consegue acompanhar gastos feitos por todas elas?

**Opções:** Sim. Praticamente tudo entra, independentemente da forma de pagamento. · Quase tudo, mas existe uma forma de pagamento que às vezes fica fora. · Não. Algumas formas de pagamento ficam frequentemente fora do meu controle. · Não sei dizer.

| Campo | Valor |
|---|---|
| Condição de exibição | B2.01 ≠ NAO_REGISTRA |
| Variável gravada | `COBERTURA_MEIOS_PAGAMENTO` |
| Valor interno / mapeamento | TOTAL · QUASE_TOTAL · PARCIAL · NAO_SEI |
| Salto / consequência | QUASE_TOTAL ou PARCIAL → abre B2.05A. |
| Uso pelo motor | CONFIABILIDADE_DADOS |

#### `B2.05A` — Meios fora do controle

**COND** · *Checklist (múltipla)*

> Quais formas de pagamento costumam escapar mais do seu controle?

**Opções:** Pix · Cartão de crédito · Cartão de débito · Dinheiro · Débito automático · Transferências · Compras parceladas · Outra

| Campo | Valor |
|---|---|
| Condição de exibição | B2.05 = QUASE_TOTAL ou PARCIAL |
| Variável gravada | `MEIOS_PAGAMENTO_FORA_CONTROLE` |
| Salto / consequência | "Outra" → texto curto OPT. |
| Uso pelo motor | CONFIABILIDADE_DADOS; relatório seção 4 |

#### `B2.06` — Conhecimento do gasto

**OBR** · *Seleção única*

> Sem precisar abrir agora extratos ou faturas, você sabe aproximadamente quanto gastou no último mês?

**Opções:** Sim. Sei o valor com boa aproximação. · Tenho uma ideia razoável, mas não saberia dizer com muita segurança. · Tenho apenas uma noção geral. · Não sei quanto gastei.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `CONHECIMENTO_GASTO` |
| Valor interno / mapeamento | BOA_APROXIMACAO · RAZOAVEL · NOCAO_GERAL · NAO_SEI |
| Uso pelo motor | NIVEL_CONTROLE; GAP_AUTOPERCEPCAO |

#### `B2.07` — Gastos não identificados

**OBR** · *Seleção única*

> Quando você olha sua conta ou fatura, com que frequência encontra gastos ou cobranças que não lembra imediatamente de ter feito ou que não sabe explicar?

**Opções:** Nunca ou quase nunca. · Raramente. · Algumas vezes por mês. · Com frequência. · Eu quase não confiro extratos e faturas, então não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `GASTOS_NAO_IDENTIFICADOS` |
| Valor interno / mapeamento | NUNCA · RARAMENTE · ALGUMAS_MES · FREQUENTE · NAO_CONFERE |
| Salto / consequência | ALGUMAS_MES ou FREQUENTE → abre B2.08. |
| Uso pelo motor | NIVEL_CONTROLE |

#### `B2.08` — Valor não identificado

**COND** · *Moeda R$*

> Em um mês típico, quanto você estima que esses gastos ou cobranças que não consegue identificar representam?

**Opções:** R$ ______ · Não consigo estimar.

| Campo | Valor |
|---|---|
| Condição de exibição | B2.07 = ALGUMAS_MES ou FREQUENTE |
| Variável gravada | `VALOR_GASTOS_NAO_IDENTIFICADOS` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Salto / consequência | Não transformar automaticamente em economia. |
| Uso pelo motor | Diagnóstico (vazamentos) |

#### `B2.09` — Gastos fantasmas

**OBR** · *Seleção única*

> Hoje, você consegue identificar algum gasto recorrente que continua saindo todo mês, mas que você usa pouco, quase não percebe ou considera que poderia reduzir ou eliminar?

**Opções:** Sim. · Talvez. Preciso conferir melhor. · Não identifiquei nenhum.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `GASTOS_FANTASMAS` |
| Valor interno / mapeamento | SIM · TALVEZ · NAO |
| Salto / consequência | Sim → abre B2.10 e B2.10A. Talvez → gera ação de conferência (Bloco 11). |
| Uso pelo motor | ECONOMIA_POTENCIAL_IMEDIATA; Bloco 12 |

#### `B2.10` — Valor dos gastos fantasmas

**COND** · *Moeda R$*

> Quanto por mês você estima que poderia reduzir ou eliminar desses gastos?

**Opções:** R$ ______ · Ainda não sei quanto.

| Campo | Valor |
|---|---|
| Condição de exibição | B2.09 = Sim |
| Variável gravada | `VALOR_GASTOS_FANTASMAS` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | ECONOMIA_POTENCIAL_IMEDIATA (só se B2.10A = Sim) |

#### `B2.10A` — Aceite da redução

**COND** · *Seleção única*

> Você aceita considerar essa redução no seu PIQ?

**Opções:** Sim, posso considerar reduzir ou eliminar esse valor. · Talvez. Quero avaliar antes. · Não. Prefiro manter esses gastos.

| Campo | Valor |
|---|---|
| Condição de exibição | B2.09 = Sim |
| Variável gravada | `ACEITA_REDUCAO_GASTOS_FANTASMAS` |
| Valor interno / mapeamento | SIM · TALVEZ · NAO |
| Salto / consequência | Somente SIM torna VALOR_GASTOS_FANTASMAS elegível à economia potencial. |
| Uso pelo motor | ECONOMIA_POTENCIAL_IMEDIATA |

#### `B2.11` — Impulso

**OBR** · *Seleção única*

> Nos últimos 30 dias, com que frequência você fez alguma compra que não estava planejada e depois percebeu que poderia ter evitado ou adiado?

**Opções:** Nenhuma vez. · Uma vez. · Duas ou três vezes. · Quatro vezes ou mais. · Não consigo avaliar.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `RISCO_IMPULSO` |
| Valor interno / mapeamento | NENHUMA · UMA · DUAS_TRES · QUATRO_MAIS · NAO_SEI |
| Uso pelo motor | RISCO_COMPORTAMENTAL_GERAL; Bloco 12 (B12.07) |

#### `B2.12` — Revisão semanal

**OBR** · *Seleção única*

> Você costuma separar algum momento da semana para conferir como estão seus gastos, saldo, cartão e compromissos financeiros?

**Opções:** Sim, praticamente toda semana. · Na maioria das semanas. · Algumas semanas. · Raramente. · Nunca.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `REVISAO_SEMANAL` |
| Valor interno / mapeamento | SEMPRE · MAIORIA · ALGUMAS · RARAMENTE · NUNCA |
| Uso pelo motor | NIVEL_CONTROLE; Bloco 12 |

#### `B2.13` — Autopercepção

**OBR** · *Escala 0–10*

> Hoje, de 0 a 10, quanto você sente que sabe para onde o seu dinheiro está indo?

**Opções:** 0 = Tenho muito pouca visibilidade. · 10 = Sei com bastante clareza para onde meu dinheiro vai.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `AUTOPERCEPCAO_CONTROLE` |
| Uso pelo motor | GAP_AUTOPERCEPCAO Derivadas pelo motor, nunca perguntadas: NIVEL_CONTROLE · CONFIABILIDADE_DADOS · GAP_AUTOPERCEPCAO · ECONOMIA_POTENCIAL_IMEDIATA são derivados pelo motor. BLOCO 3 Mapeamento: Quanto Renda, despesas, conferência e consignação TELA DE ABERTURA Agora vamos construir a fotografia financeira do seu mês. Primeiro, quanto realmente entra. Depois, quanto custa a sua vida. As parcelas de empréstimos, financiamentos e outras dívidas serão cadastradas separadamente no Inventário de Dívidas — por isso, não devem ser incluídas novamente nas despesas deste bloco. Parte A — Renda |

<a id="bloco-3"></a>

### Bloco 3 — Fluxo de caixa real

*57 perguntas.* Índice: `B3.01` · `B3.02` · `B3.02A` · `B3.02B` · `B3.03` · `B3.03A` · `B3.03B` · `B3.03C` · `B3.04` · `B3.04A` · `B3.05` · `B3.05A` · `B3.05B` · `B3.05C` · `B3.05D` · `B3.06` · `B3.06A` · `B3.06B` · `B3.D01` · `B3.D02` · `B3.D03` · `B3.D04` · `B3.D05` · `B3.D06` · `B3.D07` · `B3.D08` · `B3.D09` · `B3.D10` · `B3.D11` · `B3.DF01` · `B3.DF02` · `B3.DF03` · `B3.DF04` · `B3.NM01` · `B3.NM02A` · `B3.NM02B` · `B3.NM02C` · `B3.NM02D` · `B3.C00` · `B3.C01` · `B3.C02` · `B3.C02A` · `B3.C02B` · `B3.S01` · `B3.S02` · `B3.S03` · `B3.S04` · `B3.S05` · `B3.S06A` · `B3.S06B` · `B3.S06C` · `B3.S06D` · `B3.S06E` · `B3.S07` · `B3.S07A` · `B3.S07B` · `B3.S08`

#### `B3.01` — Renda principal

**OBR** · *Moeda R$*

> Quanto você recebe líquidos, em média, por mês na sua principal fonte de renda?

**Opções:** R$ ______ · Minha renda é variável e não consigo representá-la por um único valor.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `RENDA_PRINCIPAL` |
| Qualidade do dado | Confirmado / Estimado / Não sei com segurança → CONFIRMADA · ESTIMADA · DESCONHECIDA |
| Salto / consequência | "Renda variável sem valor único" → RENDA_PRINCIPAL = DESCONHECIDA e B3.02 deve ser Variável. |
| Uso pelo motor | RENDA_TOTAL_RECORRENTE |

#### `B3.02` — Tipo de renda

**OBR** · *Seleção única*

> Qual destas opções descreve melhor a sua principal renda?

**Opções:** Fixa — recebo praticamente o mesmo valor líquido todos os meses. · Relativamente estável — o valor varia, mas normalmente dentro de uma faixa pequena. · Variável — o valor pode mudar bastante de um mês para outro.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `TIPO_RENDA` |
| Valor interno / mapeamento | A = FIXA · B = RELATIVAMENTE_ESTAVEL · C = VARIAVEL |
| Salto / consequência | VARIAVEL → abre B3.02A e B3.02B. |
| Uso pelo motor | REDUCAO_RENDA_VARIAVEL (fator de segurança) |

#### `B3.02A` — Renda variável — média

**COND** · *Moeda R$*

> Considerando os últimos meses, qual foi aproximadamente a sua renda líquida média mensal?

*Use, de preferência, uma média dos últimos 6 a 12 meses.*

**Opções:** R$ ______ · Não consigo estimar.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.02 = VARIAVEL |
| Variável gravada | `RENDA_VARIAVEL_MEDIA_HISTORICA` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | RENDA_VARIAVEL_CONSIDERADA |

#### `B3.02B` — Renda variável — piso

**COND** · *Moeda R$*

> Pensando em um mês mais fraco, qual valor líquido você considera realisticamente seguro esperar receber?

*Não informe o pior mês excepcional da sua vida. Queremos um valor conservador que represente um mês fraco, mas plausível.*

**Opções:** R$ ______ · Não consigo estimar.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.02 = VARIAVEL |
| Variável gravada | `RENDA_VARIAVEL_PISO_DECLARADO` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Salto / consequência | Ambos desconhecidos → PRIORIDADE DE INFORMAÇÃO (não inventar renda). |
| Uso pelo motor | RENDA_VARIAVEL_CONSIDERADA |
| UX / observação | Não perguntar FATOR_RENDA_VARIAVEL (parâmetro). |

#### `B3.03` — Renda adicional

**OBR** · *Sim / Não*

> Além da sua renda principal, você recebe algum outro valor de forma recorrente?

**Opções:** Sim · Não

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `RENDA_RECORRENTE_ADICIONAL_EXISTE` |
| Valor interno / mapeamento | SIM · NAO |
| Salto / consequência | Sim → ficha REP B3.03A–C. |
| Uso pelo motor | RENDA_RECORRENTE_ADICIONAL |

#### `B3.03A` — Renda adicional — ficha REP

**COND** · **REP** · *Seleção única*

> Que renda é essa?

**Opções:** Segundo trabalho ou vínculo · Trabalho autônomo/freelance · Aluguel · Pensão recebida · Benefício · Comissão · Renda de negócio · Outra renda recorrente

| Campo | Valor |
|---|---|
| Condição de exibição | B3.03 = Sim |
| Variável gravada | `TIPO_RENDA_ADICIONAL` |
| UX / observação | Aluguel lançado aqui não é relançado em B4.I05A. |

#### `B3.03B` — Renda adicional — ficha REP

**COND** · **REP** · *Moeda R$*

> Quanto essa renda acrescenta, em média, por mês?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.03 = Sim |
| Variável gravada | `RENDA_RECORRENTE_ADICIONAL (item)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B3.03C` — Renda adicional — ficha REP

**COND** · **REP** · *Seleção única*

> Esse valor costuma ser:

**Opções:** Praticamente fixo. · Relativamente estável. · Bastante variável.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.03 = Sim |
| Variável gravada | `TIPO_RENDA_ADICIONAL_ESTABILIDADE` |
| Valor interno / mapeamento | FIXA · RELATIVAMENTE_ESTAVEL · VARIAVEL (guardar como qualidade) |

#### `B3.04` — Contribuição familiar

**OBR** · *Sim / Não*

> Outra pessoa contribui regularmente com dinheiro para pagar as despesas que fazem parte deste orçamento?

**Opções:** Sim · Não

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `CONTRIBUICAO_FAMILIAR_EXISTE` |
| Salto / consequência | Sim → abre B3.04A. |

#### `B3.04A` — Contribuição familiar — valor

**COND** · *Moeda R$*

> Quanto essa pessoa efetivamente coloca, em média, por mês nas despesas deste orçamento?

*Informe apenas o valor que realmente participa das despesas consideradas neste PIQ — não necessariamente toda a renda da outra pessoa.*

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.04 = Sim |
| Variável gravada | `CONTRIBUICAO_FAMILIAR` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | RENDA_TOTAL_RECORRENTE |

#### `B3.05` — Recursos extraordinários

**OBR** · *Seleção única*

> Nos próximos 12 meses, você espera receber algum valor extraordinário que não faça parte da sua renda mensal normal?

**Opções:** Sim · Talvez · Não

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `RECURSOS_EXTRAORDINARIOS_EXISTE` |
| Valor interno / mapeamento | SIM · TALVEZ · NAO |
| Salto / consequência | Sim/Talvez → ficha REP B3.05A–D. |
| Uso pelo motor | ATAQUE_IMEDIATO_POTENCIAL (nunca renda recorrente) |

#### `B3.05A` — Recurso extraordinário — ficha REP

**COND** · **REP** · *Seleção única*

> Que valor extraordinário é esse?

**Opções:** 13º salário · Férias/abono · Bônus ou gratificação · Restituição de imposto · Precatório/RPV · Venda já prevista · Valor a receber de terceiro · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | B3.05 = Sim ou Talvez |
| Variável gravada | `TIPO_RECURSO_EXTRAORDINARIO` |

#### `B3.05B` — Recurso extraordinário — ficha REP

**COND** · **REP** · *Moeda R$*

> Quanto você espera receber?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.05 = Sim ou Talvez |
| Variável gravada | `VALOR_RECURSO_EXTRAORDINARIO` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B3.05C` — Recurso extraordinário — ficha REP

**COND** · **REP** · *Seleção única*

> Quando você espera receber?

**Opções:** Próximos 30 dias · 1–3 meses · 4–6 meses · 7–12 meses · Ainda não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B3.05 = Sim ou Talvez |
| Variável gravada | `JANELA_RECURSO_EXTRAORDINARIO` |

#### `B3.05D` — Recurso extraordinário — ficha REP

**COND** · **REP** · *Seleção única*

> Esse recebimento é:

**Opções:** Confirmado. · Provável, mas ainda não garantido. · Apenas uma possibilidade.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.05 = Sim ou Talvez |
| Variável gravada | `CERTEZA_RECURSO_EXTRAORDINARIO` |
| Valor interno / mapeamento | CONFIRMADO · PROVAVEL · POSSIVEL |
| Salto / consequência | Não compõe renda recorrente. |

#### `B3.06` — Renda extra recorrente potencial

**OBR** · *Seleção única*

> Existe alguma forma realista de aumentar sua renda mensal de maneira recorrente nos próximos meses?

**Opções:** Sim, e já tenho uma possibilidade concreta. · Talvez, mas ainda não existe nada definido. · Não vejo essa possibilidade no momento.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `RENDA_EXTRA_RECORRENTE_POTENCIAL_EXISTE` |
| Valor interno / mapeamento | CONCRETA · INDEFINIDA · NAO |
| Salto / consequência | CONCRETA → abre B3.06A e B3.06B. |
| Uso pelo motor | CAPACIDADE_ATAQUE_POTENCIAL (somente potencial) |

#### `B3.06A` — Renda extra — origem

**COND** · *Seleção única*

> De onde viria essa renda adicional?

**Opções:** Trabalho extra · Novo vínculo ou atividade · Horas extras/adicional · Aluguel · Negócio · Serviço autônomo · Outra

| Campo | Valor |
|---|---|
| Condição de exibição | B3.06 = CONCRETA |
| Variável gravada | `ORIGEM_RENDA_EXTRA_POTENCIAL` |

#### `B3.06B` — Renda extra — valor

**COND** · *Moeda R$*

> Quanto você estima que essa renda poderia acrescentar por mês?

**Opções:** R$ ______ · Ainda não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.06 = CONCRETA |
| Variável gravada | `RENDA_EXTRA_RECORRENTE_POTENCIAL` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | CAPACIDADE_ATAQUE_POTENCIAL Parte B — Despesas mensais ATENÇÃO Exibir antes das categorias: "IMPORTANTE: não inclua aqui parcelas de empréstimos, financiamentos, consignados, cheque especial, acordos ou outras dívidas. Elas serão cadastradas separadamente. Inclua os custos normais de viver e manter sua rotina." Para cada categoria, o usuário marca os itens presentes na rotina (checklist); para cada item marcado abre a Ficha Canônica de Despesa (B3.DF01–DF04). Cada item é um registro com VALOR_DESPESA e classificação própria. |

#### `B3.D01` — Despesa — Moradia

**OBR** · *Checklist (múltipla)*

> Quais destes gastos de moradia fazem parte da sua rotina?

**Opções:** Aluguel · Condomínio · Água · Energia · Gás · Internet · Telefone · Empregado/serviço doméstico · Manutenção recorrente · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `ITENS_DESPESA_MORADIA` |
| Valor interno / mapeamento | lista de itens marcados; cada item → ficha B3.DF |
| Salto / consequência | Cada item marcado → abre B3.DF01–DF04. "Outro" → texto curto OPT. |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |
| UX / observação | Alerta: não incluir financiamento imobiliário. |

#### `B3.D02` — Despesa — Alimentação

**OBR** · *Checklist (múltipla)*

> Quais destes gastos de alimentação fazem parte da sua rotina?

**Opções:** Supermercado · Feira/açougue · Alimentação no trabalho · Delivery · Restaurantes · Lanches/cafés · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `ITENS_DESPESA_ALIMENTACAO` |
| Valor interno / mapeamento | lista de itens marcados; cada item → ficha B3.DF |
| Salto / consequência | Cada item marcado → abre B3.DF01–DF04. "Outro" → texto curto OPT. |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |

#### `B3.D03` — Despesa — Transporte

**OBR** · *Checklist (múltipla)*

> Quais destes gastos de transporte fazem parte da sua rotina?

**Opções:** Combustível · Transporte público · Aplicativos/táxi · Estacionamento · Pedágio · Seguro do veículo · Manutenção média · Outros custos recorrentes

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `ITENS_DESPESA_TRANSPORTE` |
| Valor interno / mapeamento | lista de itens marcados; cada item → ficha B3.DF |
| Salto / consequência | Cada item marcado → abre B3.DF01–DF04. "Outro" → texto curto OPT. |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |
| UX / observação | Não incluir financiamento do veículo. |

#### `B3.D04` — Despesa — Saúde

**OBR** · *Checklist (múltipla)*

> Quais destes gastos de saúde fazem parte da sua rotina?

**Opções:** Plano de saúde · Medicamentos contínuos · Terapias · Consultas/exames recorrentes · Tratamentos · Odontologia · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `ITENS_DESPESA_SAÚDE` |
| Valor interno / mapeamento | lista de itens marcados; cada item → ficha B3.DF |
| Salto / consequência | Cada item marcado → abre B3.DF01–DF04. "Outro" → texto curto OPT. |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |

#### `B3.D05` — Despesa — Educação

**OBR** · *Checklist (múltipla)*

> Quais destes gastos de educação fazem parte da sua rotina?

**Opções:** Escola/faculdade · Cursos · Material · Transporte escolar · Atividades extracurriculares · Reforço/aulas · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `ITENS_DESPESA_EDUCACAO` |
| Valor interno / mapeamento | lista de itens marcados; cada item → ficha B3.DF |
| Salto / consequência | Cada item marcado → abre B3.DF01–DF04. "Outro" → texto curto OPT. |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |

#### `B3.D06` — Despesa — Filhos e dependentes

**OBR** · *Checklist (múltipla)*

> Quais destes gastos de filhos e dependentes fazem parte da sua rotina?

**Opções:** Pensão paga · Mesada · Cuidador/babá · Vestuário recorrente · Apoio financeiro · Outras despesas

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `ITENS_DESPESA_FILHOS` |
| Valor interno / mapeamento | lista de itens marcados; cada item → ficha B3.DF |
| Salto / consequência | Cada item marcado → abre B3.DF01–DF04. "Outro" → texto curto OPT. |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |
| UX / observação | Não repetir itens já lançados em outras categorias. |

#### `B3.D07` — Despesa — Seguros e proteção

**OBR** · *Checklist (múltipla)*

> Quais destes gastos de seguros e proteção fazem parte da sua rotina?

**Opções:** Seguro de vida · Seguro residencial · Seguro de equipamentos · Outros seguros

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `ITENS_DESPESA_SEGUROS` |
| Valor interno / mapeamento | lista de itens marcados; cada item → ficha B3.DF |
| Salto / consequência | Cada item marcado → abre B3.DF01–DF04. "Outro" → texto curto OPT. |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |
| UX / observação | Seguro do veículo entra somente uma vez (já em B3.D03). |

#### `B3.D08` — Despesa — Lazer

**OBR** · *Checklist (múltipla)*

> Quais destes gastos de lazer fazem parte da sua rotina?

**Opções:** Restaurantes/lazer ainda não lançados · Streaming · Clubes · Viagens recorrentes · Eventos · Hobbies · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `ITENS_DESPESA_LAZER` |
| Valor interno / mapeamento | lista de itens marcados; cada item → ficha B3.DF |
| Salto / consequência | Cada item marcado → abre B3.DF01–DF04. "Outro" → texto curto OPT. |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |

#### `B3.D09` — Despesa — Compras e consumo

**OBR** · *Checklist (múltipla)*

> Quais destes gastos de compras e consumo fazem parte da sua rotina?

**Opções:** Roupas · Cosméticos · Eletrônicos · Compras online · Presentes · Outros

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `ITENS_DESPESA_COMPRAS` |
| Valor interno / mapeamento | lista de itens marcados; cada item → ficha B3.DF |
| Salto / consequência | Cada item marcado → abre B3.DF01–DF04. "Outro" → texto curto OPT. |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |

#### `B3.D10` — Despesa — Cuidados pessoais

**OBR** · *Checklist (múltipla)*

> Quais destes gastos de cuidados pessoais fazem parte da sua rotina?

**Opções:** Academia · Salão/barbearia · Estética · Serviços pessoais · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `ITENS_DESPESA_CUIDADOS` |
| Valor interno / mapeamento | lista de itens marcados; cada item → ficha B3.DF |
| Salto / consequência | Cada item marcado → abre B3.DF01–DF04. "Outro" → texto curto OPT. |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |

#### `B3.D11` — Despesa não listada

**OBR** · *Sim / Não*

> Existe alguma despesa mensal relevante que ainda não apareceu?

**Opções:** Sim · Não

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `DESPESA_EXTRA_EXISTE` |
| Salto / consequência | Sim → ficha REP: nome (texto curto) + B3.DF01–DF04. Ficha Canônica de Despesa (por item marcado) |

#### `B3.DF01` — Ficha de despesa — REP

**COND** · **REP** · *Moeda R$*

> Qual é o valor mensal de [despesa]?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Item marcado em B3.D01–D11 |
| Variável gravada | `VALOR_DESPESA` |
| Qualidade do dado | ver B3.DF04 |
| Uso pelo motor | DESPESAS_OPERACIONAIS_ATUAIS |

#### `B3.DF02` — Ficha de despesa — REP

**COND** · **REP** · *Seleção única*

> Esse gasto costuma ser fixo ou variável?

**Opções:** Fixo · Variável · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Item marcado |
| Variável gravada | `CLASSIFICACAO_FIXA_VARIAVEL` |
| Valor interno / mapeamento | FIXA · VARIAVEL · NAO_SEI |
| UX / observação | Não inferir pela categoria. |

#### `B3.DF03` — Ficha de despesa — REP

**COND** · **REP** · *Seleção única*

> No seu orçamento atual, esse gasto é obrigatório ou não obrigatório?

**Opções:** Obrigatório · Não obrigatório · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Item marcado |
| Variável gravada | `CLASSIFICACAO_OBRIGATORIA` |
| Valor interno / mapeamento | OBRIGATORIA · NAO_OBRIGATORIA · NAO_SEI |
| UX / observação | Não inferir pela categoria. |

#### `B3.DF04` — Ficha de despesa — REP

**COND** · **REP** · *Seleção única*

> O valor informado foi conferido recentemente ou é uma estimativa?

**Opções:** Conferido. · Estimativa. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Item marcado |
| Variável gravada | `QUALIDADE_VALOR_DESPESA` |
| Valor interno / mapeamento | CONFIRMADA · ESTIMADA · DESCONHECIDA Parte C — Despesas não mensais |

#### `B3.NM01` — Despesas não mensais

**OBR** · *Seleção única*

> Você tem despesas previsíveis que não acontecem todos os meses, mas que sabe que precisará pagar ao longo do ano?

**Opções:** Sim. · Não. · Não sei / preciso levantar.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `DESPESAS_NAO_MENSAIS_EXISTE` |
| Valor interno / mapeamento | SIM · NAO · NAO_SEI |
| Salto / consequência | Sim → ficha REP B3.NM02A–D. NAO_SEI → ação de levantamento. |
| Uso pelo motor | DESPESAS_NAO_MENSAIS_NORMALIZADAS |

#### `B3.NM02A` — Despesa não mensal — ficha REP

**COND** · **REP** · *Seleção única*

> Que despesa é essa?

**Opções:** IPTU · IPVA/licenciamento · Matrícula · Material escolar · Seguro anual · Manutenção programada · Imposto/taxa · Assinatura anual · Outra

| Campo | Valor |
|---|---|
| Condição de exibição | B3.NM01 = Sim |
| Variável gravada | `TIPO_DESPESA_NAO_MENSAL` |

#### `B3.NM02B` — Despesa não mensal — ficha REP

**COND** · **REP** · *Moeda R$*

> Qual é o valor total previsto?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.NM01 = Sim |
| Variável gravada | `VALOR_DESPESA_NAO_MENSAL` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B3.NM02C` — Despesa não mensal — ficha REP

**COND** · **REP** · *Seleção única*

> Com que frequência ela ocorre?

**Opções:** Uma vez por ano · Duas vezes por ano · Trimestral · Outra

| Campo | Valor |
|---|---|
| Condição de exibição | B3.NM01 = Sim |
| Variável gravada | `FREQUENCIA_DESPESA_NAO_MENSAL` |
| Valor interno / mapeamento | ANUAL · SEMESTRAL · TRIMESTRAL · OUTRA |
| Uso pelo motor | DESPESA_NAO_MENSAL_EQUIVALENTE |

#### `B3.NM02D` — Despesa não mensal — ficha REP

**COND** · **REP** · *Seleção única*

> Esse valor já está sendo reservado ou contabilizado mensalmente em alguma despesa que você informou antes?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B3.NM01 = Sim |
| Variável gravada | `DESPESA_NAO_MENSAL_JA_CONTABILIZADA` |
| Salto / consequência | Sim → não normalizar novamente (impedir dupla contagem). Parte D — Conferência |

#### `B3.C00` — Conferência do mapeamento

**OBR** · *Seleção única*

> Essa fotografia de renda e despesas parece representar razoavelmente o seu mês?

**Opções:** Sim. · Não, acho que alguma despesa ficou de fora. · Não, algum valor parece errado. · Ainda não consigo avaliar.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `CONFIRMACAO_MAPEAMENTO_DESPESAS` |
| Valor interno / mapeamento | SIM · FALTA_DESPESA · VALOR_ERRADO · NAO_SEI |
| Salto / consequência | FALTA_DESPESA → retorna a B3.D11; VALOR_ERRADO → permite editar fichas. |

#### `B3.C01` — Capacidade declarada

**OBR** · *Moeda R$*

> Pensando na sua realidade de hoje, qual valor adicional você acredita conseguir separar todos os meses para acelerar a quitação das dívidas, sem precisar fazer uma nova dívida para conseguir fechar o mês?

*Estamos falando de dinheiro além dos pagamentos normais das dívidas que já existem.*

**Opções:** R$ ______ · Hoje não consigo separar nenhum valor adicional. · Ainda não consigo estimar.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `CAPACIDADE_ATAQUE_DECLARADA` |
| Valor interno / mapeamento | valor · 0 · DESCONHECIDA |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | BASE_CONSERVADORA |

#### `B3.C02` — Percepção de fechamento

**OBR** · *Seleção única*

> Na prática, como seus últimos meses costumam terminar?

**Opções:** Normalmente sobra dinheiro. · Normalmente fica praticamente no zero a zero. · Normalmente falta dinheiro. · Varia muito de um mês para outro. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `PERCEPCAO_FECHAMENTO_MES` |
| Valor interno / mapeamento | SOBRA · ZERO · FALTA · VARIA · NAO_SEI |
| Salto / consequência | SOBRA → B3.C02A; FALTA → B3.C02B. |
| Uso pelo motor | Validação do RESULTADO_MENSAL_ATUAL (não substitui a matemática) |

#### `B3.C02A` — Sobra percebida

**COND** · *Moeda R$*

> Quanto costuma sobrar, aproximadamente?

**Opções:** R$ ______

| Campo | Valor |
|---|---|
| Condição de exibição | B3.C02 = SOBRA |
| Variável gravada | `SOBRA_PERCEBIDA` |
| Qualidade do dado | ESTIMADA |

#### `B3.C02B` — Falta percebida

**COND** · *Moeda R$*

> Quanto costuma faltar, aproximadamente?

**Opções:** R$ ______

| Campo | Valor |
|---|---|
| Condição de exibição | B3.C02 = FALTA |
| Variável gravada | `FALTA_PERCEBIDA` |
| Qualidade do dado | ESTIMADA Parte E — Servidor / consignação |

#### `B3.S01` — Vínculo com consignação

**OBR** · *Seleção única*

> Alguma das suas rendas está ligada a vínculo público, aposentadoria ou pensão com possibilidade de consignação?

**Opções:** Sim. · Não. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `VINCULO_CONSIGNAVEL` |
| Valor interno / mapeamento | SIM · NAO · NAO_SEI |
| Salto / consequência | Não → encerra a Parte E. Sim/Não sei → B3.S02. |

#### `B3.S02` — Situação

**COND** · *Checklist (múltipla)*

> Qual é a sua situação principal?

**Opções:** Servidor público federal · Servidor público estadual · Servidor público municipal · Militar · Aposentado/pensionista do serviço público · Aposentado/pensionista do INSS · Outra situação com consignação

| Campo | Valor |
|---|---|
| Condição de exibição | B3.S01 ≠ Não |
| Variável gravada | `REGIME_MARGEM` |
| Valor interno / mapeamento | FEDERAL · ESTADUAL · MUNICIPAL · MILITAR · APOSENTADO_PUBLICO · INSS · OUTRO (permitir mais de um vínculo) |

#### `B3.S03` — Órgão

**COND** · *Busca / texto curto*

> Qual é o órgão ou a fonte pagadora desse vínculo?

| Campo | Valor |
|---|---|
| Condição de exibição | B3.S01 ≠ Não |
| Variável gravada | `ORGAO_FONTE_PAGADORA` |

#### `B3.S04` — Remuneração bruta

**COND** · *Moeda R$*

> Qual é a sua remuneração bruta nesse vínculo?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.S01 ≠ Não |
| Variável gravada | `RENDA_BRUTA_VINCULO` |
| Qualidade do dado | CONFIRMADA (contracheque) / ESTIMADA / DESCONHECIDA |
| Uso pelo motor | valor de margem declarado pela fonte pagadora × renda bruta (parâmetro por regime) |
| UX / observação | Não calcular margem por percentual legal; usar o valor declarado. |

#### `B3.S05` — Acesso às margens

**COND** · *Seleção única*

> Você consegue consultar atualmente suas margens consignáveis?

**Opções:** Sim. · Tenho apenas parte das informações. · Não.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.S01 ≠ Não |
| Variável gravada | `ACESSO_MARGENS` |
| Valor interno / mapeamento | SIM · PARCIAL · NAO |
| Salto / consequência | NAO → gera ação de obtenção (Bloco 11); ficha B3.S06 fica com valores DESCONHECIDOS. |

#### `B3.S06A` — Margem — ficha REP

**COND** · **REP** · *Seleção única*

> Qual é o tipo desta margem?

**Opções:** Empréstimo consignado · Cartão consignado · Cartão benefício · Outra margem do regime

| Campo | Valor |
|---|---|
| Condição de exibição | B3.S01 ≠ Não |
| Variável gravada | `TIPO_MARGEM` |
| Valor interno / mapeamento | EMPRESTIMO · CARTAO_CONSIGNADO · CARTAO_BENEFICIO · OUTRA_DO_REGIME. SYS: MARGEM_ID por ficha. |

#### `B3.S06B` — Margem — ficha REP

**COND** · **REP** · *Moeda R$*

> Qual é o valor total disponível para essa modalidade?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | ficha de margem |
| Variável gravada | `VALOR_TOTAL_MARGEM` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |

#### `B3.S06C` — Margem — ficha REP

**COND** · **REP** · *Moeda R$*

> Quanto está atualmente utilizado?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | ficha de margem |
| Variável gravada | `VALOR_UTILIZADO_MARGEM` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |

#### `B3.S06D` — Margem — ficha REP

**COND** · **REP** · *Moeda R$*

> Qual é o valor livre informado pelo sistema ou contracheque?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | ficha de margem |
| Variável gravada | `VALOR_LIVRE_MARGEM` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |
| UX / observação | Margem livre não é dinheiro nem recomendação de crédito. |

#### `B3.S06E` — Margem — ficha REP

**COND** · **REP** · *Data*

> De quando é essa informação?

**Opções:** Data · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | ficha de margem |
| Variável gravada | `DATA_REFERENCIA_MARGEM` |

#### `B3.S07` — Margem a liberar

**COND** · *Sim / Não / Não sei*

> Você sabe se alguma parcela consignada termina nos próximos 12 meses e liberará margem?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B3.S01 ≠ Não |
| Variável gravada | `MARGEM_A_LIBERAR_EXISTE` |
| Salto / consequência | Sim → B3.S07A e B3.S07B. |
| Uso pelo motor | VALOR_A_LIBERAR_MARGEM |

#### `B3.S07A` — Margem a liberar — valor

**COND** · *Moeda R$*

> Qual é o valor da parcela que deixará de ocupar margem?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B3.S07 = Sim |
| Variável gravada | `VALOR_A_LIBERAR_MARGEM` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| UX / observação | Conciliar com a dívida consignada correspondente no Bloco 5. |

#### `B3.S07B` — Margem a liberar — quando

**COND** · *Seleção única*

> Quando isso deve ocorrer?

**Opções:** 1–3 meses · 4–6 meses · 7–12 meses · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B3.S07 = Sim |
| Variável gravada | `JANELA_LIBERACAO_MARGEM` |

#### `B3.S08` — Desconto não reconhecido

**COND** · *Sim / Não / Não sei*

> Existe algum desconto relacionado a crédito ou consignação no seu contracheque que você não reconhece ou não consegue identificar?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B3.S01 ≠ Não |
| Variável gravada | `DESCONTO_CONTRACHEQUE_NAO_RECONHECIDO` |
| Salto / consequência | Sim/Não sei → ação: obter extrato de consignações (Bloco 11). |
| Uso pelo motor | Derivadas pelo motor, nunca perguntadas: RENDA_TOTAL_RECORRENTE · RENDA_VARIAVEL_CONSIDERADA · DESPESAS_OPERACIONAIS_ATUAIS · DESPESAS_NAO_MENSAIS_NORMALIZADAS · RESULTADO_CAIXA_OBSERVADO · RESULTADO_MENSAL_ATUAL · GAP_CAIXA_VS_ESTRUTURAL · CAPACIDADE_ATAQUE_ATUAL · BASE_CONSERVADORA · FATOR_SEGURANCA · CAPACIDADE_ATAQUE_CONSERVADORA · CAPACIDADE_ATAQUE_POTENCIAL · PISO_CAPACIDADE · semáforo · Modo Estabilização. BLOCO 4 Mapeamento: O Quê O que a pessoa possui e qual papel pode — ou não — exercer TELA DE ABERTURA Agora vamos olhar para o que você já construiu. Dinheiro em conta, reserva, investimentos, imóveis, veículos e outros bens podem fazer parte da sua estratégia — mas possuir um patrimônio não significa que ele deva ser usado para pagar dívidas. Primeiro vamos mapear. A decisão de usar ou não algum recurso vem depois. |

<a id="bloco-4"></a>

### Bloco 4 — Vínculos, margens e patrimônio

*49 perguntas.* Índice: `B4.01` · `B4.01A` · `B4.02` · `B4.02A` · `B4.02B` · `B4.03` · `B4.03A` · `B4.04` · `B4.04A` · `B4.04B` · `B4.05` · `B4.06` · `B4.06A` · `B4.06B` · `B4.I01` · `B4.I02` · `B4.I03` · `B4.I04` · `B4.I04A` · `B4.I05` · `B4.I05A` · `B4.I06` · `B4.I07` · `B4.I08` · `B4.I09` · `B4.V01` · `B4.V02` · `B4.V03` · `B4.V04` · `B4.V04A` · `B4.V05` · `B4.V06` · `B4.V07` · `B4.V08` · `B4.V08A` · `B4.V08B` · `B4.V08C` · `B4.V09` · `B4.O01` · `B4.O02` · `B4.O03` · `B4.O04` · `B4.O04A` · `B4.O05` · `B4.O06` · `B4.O07` · `B4.O08` · `B4.O09` · `B4.F01`

#### `B4.01` — Dinheiro disponível

**OBR** · *Seleção única*

> Hoje, fora da sua reserva financeira e dos seus investimentos, você possui algum dinheiro disponível que não esteja comprometido com as despesas normais até a próxima entrada de renda?

**Opções:** Sim · Não · Não sei ao certo

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `DINHEIRO_DISPONIVEL_EXISTE` |
| Valor interno / mapeamento | SIM · NAO · NAO_SEI |
| Salto / consequência | Sim → B4.01A. |
| Uso pelo motor | ATAQUE_IMEDIATO_POTENCIAL |

#### `B4.01A` — Dinheiro disponível — valor

**COND** · *Moeda R$*

> Quanto aproximadamente?

**Opções:** R$ ______

| Campo | Valor |
|---|---|
| Condição de exibição | B4.01 = Sim |
| Variável gravada | `DINHEIRO_DISPONIVEL` |
| Qualidade do dado | ESTIMADA |

#### `B4.02` — Reserva

**OBR** · *Seleção única*

> Você possui hoje alguma reserva financeira separada para emergências, imprevistos ou proteção do orçamento?

**Opções:** Sim. · Tenho algum dinheiro guardado, mas não considero uma reserva estruturada. · Não.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `RESERVA_EXISTE` |
| Valor interno / mapeamento | SIM · INFORMAL · NAO |
| Salto / consequência | SIM ou INFORMAL → B4.02A, B4.02B, B4.03. |
| Uso pelo motor | Regra da reserva (B4) |

#### `B4.02A` — Reserva — valor

**COND** · *Moeda R$*

> Qual é o valor total que você considera hoje como reserva ou dinheiro guardado para proteção?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.02 ≠ NAO |
| Variável gravada | `RESERVA_TOTAL` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B4.02B` — Reserva — onde

**COND** · *Checklist (múltipla)*

> Onde esse dinheiro está guardado?

**Opções:** Conta corrente · Conta remunerada · Poupança · CDB/RDB · Tesouro Direto · Fundo de renda fixa · Outro investimento · Dinheiro em espécie · Outro · Não sei dizer

| Campo | Valor |
|---|---|
| Condição de exibição | B4.02 ≠ NAO |
| Variável gravada | `LOCAL_RESERVA` |
| UX / observação | Valores aqui informados como reserva NÃO são relançados em B4.04 (investimentos). B4.04 pergunta explicitamente "além dos valores já informados como reserva". |

#### `B4.03` — Disposição de uso da reserva

**COND** · *Seleção única*

> Se a análise mostrar que usar uma parte da reserva pode ser financeiramente vantajoso sem deixar você desprotegido, você aceitaria considerar essa possibilidade?

**Opções:** Sim, aceitaria avaliar o uso de uma parte. · Sim, aceitaria avaliar até mesmo o uso de grande parte da reserva. · Talvez. Quero ver os números antes. · Não. Prefiro preservar integralmente minha reserva.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.02 ≠ NAO |
| Variável gravada | `DISPOSICAO_USO_RESERVA` |
| Valor interno / mapeamento | PARTE · GRANDE_PARTE · TALVEZ · NAO |
| Salto / consequência | ≠ NAO → B4.03A. |
| Uso pelo motor | RESERVA_MOBILIZAVEL; ATAQUE_IMEDIATO_RECOMENDADO |

#### `B4.03A` — Reserva mobilizável

**COND** · *Moeda R$*

> Qual é o valor máximo da sua reserva que você aceitaria colocar em análise para uma possível quitação?

**Opções:** R$ ______ · Prefiro decidir somente depois de ver a análise. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.03 ≠ NAO |
| Variável gravada | `RESERVA_MOBILIZAVEL` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| UX / observação | Valor para análise. Não é recomendação automática. |

#### `B4.04` — Investimentos

**OBR** · *Seleção única*

> Além dos valores que você já informou como reserva, você possui outros investimentos?

**Opções:** Sim · Não · Não sei exatamente

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `INVESTIMENTOS_EXISTE` |
| Valor interno / mapeamento | SIM · NAO · NAO_SEI |
| Salto / consequência | Sim → ficha REP B4.04A–B4.06B. |
| Uso pelo motor | INVESTIMENTOS_TOTAL; ATIVOS_TOTAIS |

#### `B4.04A` — Investimento — ficha REP

**COND** · **REP** · *Seleção única*

> Que investimento é esse?

**Opções:** Poupança · CDB/RDB · Tesouro Direto · LCI/LCA · Fundo de renda fixa · Previdência privada · Fundo de investimento · Ações · ETF · Fundo imobiliário · Criptoativo · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | B4.04 = Sim |
| Variável gravada | `TIPO_INVESTIMENTO` |

#### `B4.04B` — Investimento — ficha REP

**COND** · **REP** · *Moeda R$*

> Qual é aproximadamente o valor atual desse investimento?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.04 = Sim |
| Variável gravada | `VALOR_ESTIMADO_ATIVO (investimento)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | INVESTIMENTOS_TOTAL |

#### `B4.05` — Investimento — liquidez

**COND** · **REP** · *Seleção única*

> Se você decidisse resgatar esse investimento, em quanto tempo o dinheiro normalmente ficaria disponível?

**Opções:** No mesmo dia · Em até 1 dia útil · Em até 7 dias · Em até 30 dias · Em mais de 30 dias · Há carência ou bloqueio · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B4.04 = Sim |
| Variável gravada | `LIQUIDEZ_INVESTIMENTOS` |
| Valor interno / mapeamento | D0 · D1 · D7 · D30 · MAIS_30 · BLOQUEADO · NAO_SEI |
| Uso pelo motor | ATAQUE_IMEDIATO_POTENCIAL |

#### `B4.06` — Investimento — custo de saída

**COND** · **REP** · *Seleção única*

> Você sabe se teria algum custo, perda relevante, multa, imposto específico ou outra consequência para resgatar esse investimento agora?

**Opções:** Não há custo ou perda relevante que eu conheça. · Sim. · Pode haver, mas não sei calcular. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.04 = Sim |
| Variável gravada | `CUSTO_DESMOBILIZACAO_INVESTIMENTOS_EXISTE` |
| Valor interno / mapeamento | NAO · SIM · TALVEZ · NAO_SEI |
| Salto / consequência | Sim → B4.06A. |

#### `B4.06A` — Investimento — custo

**COND** · **REP** · *Moeda R$ ou Percentual %*

> Quanto você estima que perderia ou pagaria para retirar esse investimento?

**Opções:** R$ ______ · ____ % · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B4.06 = Sim |
| Variável gravada | `CUSTO_DESMOBILIZACAO_INVESTIMENTOS` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | VALOR_LIQUIDO_REALIZAVEL_ATIVO |

#### `B4.06B` — Investimento — disposição

**COND** · **REP** · *Seleção única*

> Você aceitaria considerar o uso desse investimento para reduzir dívidas, caso a análise mostre vantagem financeira?

**Opções:** Sim · Talvez · Não

| Campo | Valor |
|---|---|
| Condição de exibição | B4.04 = Sim |
| Variável gravada | `DISPOSICAO_USO_INVESTIMENTO` |
| Valor interno / mapeamento | SIM · TALVEZ · NAO |
| Uso pelo motor | Classificação do ativo (motor) Imóveis — ficha REP |

#### `B4.I01` — Imóveis

**OBR** · *Sim / Não*

> Você possui algum imóvel, total ou parcialmente?

**Opções:** Sim · Não

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `IMOVEL_EXISTE` |
| Salto / consequência | Sim → ficha REP B4.I02–I09 (uma por imóvel). |

#### `B4.I02` — Imóvel — ficha REP

**COND** · **REP** · *Seleção única*

> Que imóvel é esse?

**Opções:** Casa/apartamento onde moro · Outro imóvel residencial · Imóvel alugado · Terreno · Imóvel comercial · Imóvel de lazer · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | B4.I01 = Sim |
| Variável gravada | `TIPO_IMOVEL` |

#### `B4.I03` — Imóvel — ficha REP

**COND** · **REP** · *Moeda R$*

> Quanto você estima que esse imóvel vale hoje?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.I01 = Sim |
| Variável gravada | `VALOR_IMOVEL (= VALOR_ESTIMADO_ATIVO)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | ATIVOS_TOTAIS |

#### `B4.I04` — Imóvel — ficha REP

**COND** · **REP** · *Sim / Não / Não sei*

> Esse imóvel possui hoje financiamento ou outra dívida diretamente vinculada a ele?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B4.I01 = Sim |
| Variável gravada | `IMOVEL_POSSUI_PASSIVO` |
| Salto / consequência | Sim → B4.I04A. |

#### `B4.I04A` — Imóvel — ficha REP

**COND** · **REP** · *Moeda R$*

> Qual é aproximadamente o saldo devedor atual?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.I04 = Sim |
| Variável gravada | `SALDO_FINANCIAMENTO_IMOVEL (= SALDO_PASSIVO_VINCULADO)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| UX / observação | Conciliar com a dívida correspondente no Bloco 5 (contada uma única vez como dívida). |

#### `B4.I05` — Imóvel — ficha REP

**COND** · **REP** · *Sim / Não*

> Esse imóvel gera alguma renda recorrente para você?

**Opções:** Sim · Não

| Campo | Valor |
|---|---|
| Condição de exibição | B4.I01 = Sim |
| Variável gravada | `IMOVEL_GERA_RENDA` |
| Salto / consequência | Sim → B4.I05A. |

#### `B4.I05A` — Imóvel — ficha REP

**COND** · **REP** · *Moeda R$*

> Quanto líquido, aproximadamente, por mês?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.I05 = Sim |
| Variável gravada | `RENDA_IMOVEL` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| UX / observação | Não duplicar renda de aluguel já registrada em B3.03. |

#### `B4.I06` — Imóvel — ficha REP

**COND** · **REP** · *Moeda R$*

> Além de eventual financiamento, quanto esse imóvel custa para você por mês, em média?

**Opções:** R$ ______ · Não possui custo relevante. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.I01 = Sim |
| Variável gravada | `CUSTO_IMOVEL` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| UX / observação | Não duplicar despesas de moradia já lançadas em B3.D01. |

#### `B4.I07` — Imóvel — ficha REP

**COND** · **REP** · *Seleção única*

> Qual é o papel desse imóvel na sua vida hoje?

**Opções:** É minha moradia principal e considero essencial mantê-lo. · É importante, mas eu poderia avaliar mudanças em uma situação específica. · Não é essencial para minha moradia ou atividade principal.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.I01 = Sim |
| Variável gravada | `IMOVEL_ESSENCIAL` |
| Valor interno / mapeamento | ESSENCIAL · IMPORTANTE · NAO_ESSENCIAL |

#### `B4.I08` — Imóvel — ficha REP

**COND** · **REP** · *Seleção única*

> Você consideraria vender esse imóvel como parte de uma reorganização financeira?

**Opções:** Não. Quero preservar este imóvel. · Somente em uma situação extrema. · Talvez, dependendo dos números. · Sim, considero essa possibilidade. · Já pretendo vender.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.I01 = Sim |
| Variável gravada | `POSSIBILIDADE_VENDA_IMOVEL` |
| Valor interno / mapeamento | NAO · EXTREMO · TALVEZ · SIM · JA_PRETENDE |

#### `B4.I09` — Imóvel — ficha REP

**COND** · **REP** · *Moeda R$ ou Percentual %*

> Você sabe aproximadamente quais seriam os custos para vender ou transferir esse imóvel?

**Opções:** R$ ______ · ____ % · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.I01 = Sim |
| Variável gravada | `CUSTOS_ESTIMADOS_DESMOBILIZACAO (imóvel)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA Veículos — ficha REP |

#### `B4.V01` — Veículos

**OBR** · *Sim / Não*

> Você possui algum veículo?

**Opções:** Sim · Não

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `VEICULO_EXISTE` |
| Salto / consequência | Sim → ficha REP B4.V02–V09. |

#### `B4.V02` — Veículo — ficha REP

**COND** · **REP** · *Seleção única*

> Que tipo de veículo é esse?

**Opções:** Carro · Moto · Utilitário · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V01 = Sim |
| Variável gravada | `TIPO_VEICULO` |

#### `B4.V03` — Veículo — ficha REP

**COND** · **REP** · *Moeda R$*

> Quanto você estima que esse veículo vale hoje?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V01 = Sim |
| Variável gravada | `VALOR_VEICULO (= VALOR_ESTIMADO_ATIVO)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B4.V04` — Veículo — ficha REP

**COND** · **REP** · *Sim / Não / Não sei*

> Esse veículo possui financiamento ou outra dívida vinculada?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V01 = Sim |
| Variável gravada | `VEICULO_POSSUI_PASSIVO` |
| Salto / consequência | Sim → B4.V04A. |

#### `B4.V04A` — Veículo — ficha REP

**COND** · **REP** · *Moeda R$*

> Qual é aproximadamente o saldo atual?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V04 = Sim |
| Variável gravada | `SALDO_FINANCIAMENTO_VEICULO (= SALDO_PASSIVO_VINCULADO)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| UX / observação | Conciliar com o Bloco 5. |

#### `B4.V05` — Veículo — ficha REP

**COND** · **REP** · *Moeda R$*

> Além da parcela de eventual financiamento, quanto esse veículo custa por mês, em média?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V01 = Sim |
| Variável gravada | `CUSTO_RECORRENTE_VEICULO` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| UX / observação | Não duplicar custos já lançados em B3.D03. |

#### `B4.V06` — Veículo — ficha REP

**COND** · **REP** · *Seleção única*

> Esse veículo é essencial para sua rotina atual?

**Opções:** Sim, é essencial para trabalho, saúde, dependentes ou deslocamento sem alternativa razoável. · É muito importante, mas existem alternativas. · Não é essencial.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V01 = Sim |
| Variável gravada | `VEICULO_ESSENCIAL` |
| Valor interno / mapeamento | ESSENCIAL · IMPORTANTE · NAO_ESSENCIAL |

#### `B4.V07` — Veículo — ficha REP

**COND** · **REP** · *Seleção única*

> Você consideraria vender esse veículo como parte de uma reorganização financeira?

**Opções:** Não. · Somente em situação extrema. · Talvez, dependendo dos números. · Sim. · Já pretendo vender.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V01 = Sim |
| Variável gravada | `POSSIBILIDADE_VENDA_VEICULO` |
| Valor interno / mapeamento | NAO · EXTREMO · TALVEZ · SIM · JA_PRETENDE |

#### `B4.V08` — Veículo — ficha REP

**COND** · **REP** · *Seleção única*

> Você consideraria trocar esse veículo por outro de menor valor ou menor custo mensal?

**Opções:** Sim. · Talvez. · Não. · Não se aplica.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V01 = Sim |
| Variável gravada | `POSSIBILIDADE_SUBSTITUICAO` |
| Valor interno / mapeamento | SIM · TALVEZ · NAO · NAO_APLICA |
| Salto / consequência | Sim/Talvez → B4.V08A–C. |

#### `B4.V08A` — Veículo — ficha REP

**COND** · **REP** · *Moeda R$*

> Se essa troca acontecesse, quanto você imagina gastar aproximadamente no veículo substituto?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V08 = Sim ou Talvez |
| Variável gravada | `VALOR_VEICULO_SUBSTITUTO` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B4.V08B` — Veículo — ficha REP

**COND** · **REP** · *Sim / Não / Não sei*

> Você estima que essa substituição reduziria seus gastos mensais com o veículo?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V08 = Sim ou Talvez |
| Variável gravada | `SUBSTITUICAO_REDUZ_CUSTO` |
| Salto / consequência | Sim → B4.V08C. |

#### `B4.V08C` — Veículo — ficha REP

**COND** · **REP** · *Moeda R$*

> Em quanto aproximadamente por mês?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V08B = Sim |
| Variável gravada | `ECONOMIA_RECORRENTE_SUBSTITUICAO_VEICULO` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | ECONOMIA_RECORRENTE_POTENCIAL |

#### `B4.V09` — Veículo — ficha REP

**COND** · **REP** · *Moeda R$*

> Você estima algum custo relevante para vender, transferir ou substituir esse veículo?

**Opções:** R$ ______ · Não há custo relevante que eu conheça. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.V01 = Sim |
| Variável gravada | `CUSTOS_ESTIMADOS_DESMOBILIZACAO (veículo)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA Outros ativos — ficha REP |

#### `B4.O01` — Outros ativos

**OBR** · *Sim / Não*

> Além de dinheiro, investimentos, imóveis e veículos, você possui algum outro bem de valor relevante que poderia gerar dinheiro, renda ou redução de despesas se fosse vendido ou reorganizado?

**Opções:** Sim · Não

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `OUTRO_ATIVO_EXISTE` |
| Salto / consequência | Sim → ficha REP B4.O02–O09. |
| UX / observação | Não transformar em inventário doméstico irrelevante. |

#### `B4.O02` — Outro ativo — ficha REP

**COND** · **REP** · *Seleção única*

> O que é?

**Opções:** Equipamento profissional · Joias/objetos de valor · Participação societária · Embarcação · Bem de coleção · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | B4.O01 = Sim |
| Variável gravada | `TIPO_OUTRO_ATIVO` |

#### `B4.O03` — Outro ativo — ficha REP

**COND** · **REP** · *Moeda R$*

> Quanto você estima que vale?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.O01 = Sim |
| Variável gravada | `VALOR_ESTIMADO_ATIVO (outro)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B4.O04` — Outro ativo — ficha REP

**COND** · **REP** · *Sim / Não / Não sei*

> Existe dívida diretamente vinculada a esse ativo?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B4.O01 = Sim |
| Variável gravada | `OUTRO_ATIVO_POSSUI_PASSIVO` |
| Salto / consequência | Sim → B4.O04A. |

#### `B4.O04A` — Outro ativo — ficha REP

**COND** · **REP** · *Moeda R$*

> Qual é o saldo aproximado?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.O04 = Sim |
| Variável gravada | `SALDO_PASSIVO_VINCULADO (outro)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| UX / observação | Conciliar com o Bloco 5. |

#### `B4.O05` — Outro ativo — ficha REP

**COND** · **REP** · *Sim / Não*

> Esse ativo produz renda?

**Opções:** Sim · Não → se Sim: R$ ______ por mês

| Campo | Valor |
|---|---|
| Condição de exibição | B4.O01 = Sim |
| Variável gravada | `RENDA_OUTRO_ATIVO` |
| Qualidade do dado | ESTIMADA |
| UX / observação | Não duplicar renda já lançada em B3.03. |

#### `B4.O06` — Outro ativo — ficha REP

**COND** · **REP** · *Sim / Não*

> Esse ativo gera custo recorrente?

**Opções:** Sim · Não → se Sim: R$ ______ por mês

| Campo | Valor |
|---|---|
| Condição de exibição | B4.O01 = Sim |
| Variável gravada | `CUSTO_OUTRO_ATIVO` |
| Qualidade do dado | ESTIMADA |

#### `B4.O07` — Outro ativo — ficha REP

**COND** · **REP** · *Seleção única*

> Esse ativo é essencial para sua rotina ou atividade?

**Opções:** Sim · Parcialmente · Não

| Campo | Valor |
|---|---|
| Condição de exibição | B4.O01 = Sim |
| Variável gravada | `OUTRO_ATIVO_ESSENCIAL` |
| Valor interno / mapeamento | ESSENCIAL · PARCIAL · NAO_ESSENCIAL |

#### `B4.O08` — Outro ativo — ficha REP

**COND** · **REP** · *Seleção única*

> Você consideraria vender ou desmobilizar esse ativo?

**Opções:** Não. · Apenas em situação extrema. · Talvez. · Sim. · Já pretendo.

| Campo | Valor |
|---|---|
| Condição de exibição | B4.O01 = Sim |
| Variável gravada | `POSSIBILIDADE_VENDA_OUTRO_ATIVO` |
| Valor interno / mapeamento | NAO · EXTREMO · TALVEZ · SIM · JA_PRETENDE |

#### `B4.O09` — Outro ativo — ficha REP

**COND** · **REP** · *Moeda R$ ou Percentual %*

> Quais seriam aproximadamente os custos para vendê-lo ou desmobilizá-lo?

**Opções:** R$ ______ · ____ % · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B4.O01 = Sim |
| Variável gravada | `CUSTOS_ESTIMADOS_DESMOBILIZACAO (outro)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B4.F01` — Conferência patrimonial

**OBR** · *Seleção única*

> Existe algum recurso ou patrimônio relevante que ainda não apareceu?

**Opções:** Não, está completo. · Sim, preciso acrescentar algo. · Não tenho certeza.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `CONFIRMACAO_MAPEAMENTO_PATRIMONIAL` |
| Valor interno / mapeamento | COMPLETO · FALTA · NAO_SEI |
| Salto / consequência | FALTA → retorna às fichas do Bloco 4. |
| Uso pelo motor | Derivadas pelo motor, nunca perguntadas: Classificação dos ativos (NAO_MOBILIZAR · MOBILIZACAO_COM_RESSALVAS · MOBILIZACAO_POSSIVEL · MOBILIZACAO_RECOMENDAVEL), ATIVOS_TOTAIS, PASSIVOS_VINCULADOS_ATIVOS, PATRIMONIO_LIQUIDO, VALOR_LIQUIDO_REALIZAVEL_ATIVO, PATRIMONIO_MOBILIZAVEL, PATRIMONIO_ESTRATEGICAMENTE_MOBILIZAVEL, ECONOMIA_RECORRENTE_POTENCIAL, ATAQUE_IMEDIATO_POTENCIAL / RECOMENDADO são derivados pelo motor. Nunca perguntar a classificação do ativo. BLOCO 5 Inventário 360º das Dívidas Uma ficha por operação financeira TELA DE ABERTURA Agora vamos mapear todas as suas dívidas, uma por uma. Cadastre cada operação separadamente. Se você tem duas dívidas no mesmo banco, são dois registros. Se no mesmo cartão existe rotativo e um parcelamento antigo da fatura, são duas dívidas diferentes. Se não souber alguma informação, marque ‘Não sei’. É melhor reconhecer um dado desconhecido do que preencher um valor incorreto. ATENÇÃO Aviso exibido: "Não deixe uma dívida de fora apenas porque está atrasada, negativada, sendo cobrada, renegociada ou sem pagamento atualmente." |

<a id="bloco-5"></a>

### Bloco 5 — Inventário de dívidas

*58 perguntas.* Índice: `B5.00` · `B5.00A` · `B5.A01` · `B5.A02` · `B5.A03` · `B5.A04` · `B5.A05` · `B5.A05A` · `B5.B01` · `B5.B02` · `B5.B03` · `B5.B04` · `B5.B05` · `B5.B05A` · `B5.B05B` · `B5.C01` · `B5.C02` · `B5.C03` · `B5.C04` · `B5.C05` · `B5.C05A` · `B5.C06` · `B5.C06A` · `B5.C07` · `B5.C07A` · `B5.D01` · `B5.D01A` · `B5.D01B` · `B5.D02` · `B5.D03` · `B5.D03A` · `B5.D04` · `B5.D04A` · `B5.D05` · `B5.D05A` · `B5.D05B` · `B5.E01` · `B5.E02` · `B5.E03` · `B5.E04` · `B5.E05` · `B5.F01` · `B5.F02` · `B5.F03` · `B5.F04` · `B5.G01` · `B5.G02` · `B5.G03` · `B5.H01` · `B5.H02` · `B5.H03` · `B5.H04` · `B5.I01` · `B5.I02` · `B5.I03` · `B5.CHECK` · `B5.FIM01` · `B5.FIM02`

#### `B5.00` — Quantidade declarada

**OBR** · *Número*

> Quantas dívidas ou operações financeiras diferentes você acredita ter hoje?

**Opções:** ___ dívida(s) · Não sei exatamente quantas.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `QUANTIDADE_DIVIDAS_DECLARADA_INICIAL` |
| Valor interno / mapeamento | inteiro · DESCONHECIDA |
| Uso pelo motor | INVENTARIO_COMPLETO (comparar com cadastradas) |
| UX / observação | Se desconhecida, preservar essa informação; a quantidade final confirmada é registrada separadamente em B5.FIM. |

#### `B5.00A` — Tipos declarados

**OBR** · *Checklist (múltipla)*

> Para ajudar a lembrar, quais destes tipos você possui ou acredita possuir atualmente?

**Opções:** Empréstimo consignado · Empréstimo pessoal · Financiamento de veículo · Financiamento imobiliário · Cartão com saldo rotativo · Parcelamento de fatura · Cheque especial · Parcelamento de compra · Dívida tributária · Dívida com familiar ou outra pessoa · Acordo/renegociação · Outra · Não tenho certeza

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `TIPOS_DIVIDA_DECLARADOS` |
| Uso pelo motor | Checagem de completude do inventário |
| UX / observação | Cada operação cadastrada recebe SYS: DIVIDA_ID (D001, D002…), estável. Grupo A — Identificação (ficha REP por dívida) |
| Exclusividade | "Não tenho certeza" é exclusiva. |

#### `B5.A01` — A — Credor

**REP** · *Busca/seleção + nome do credor*

> Para quem você deve nessa operação?

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `CREDOR` |

#### `B5.A02` — A — Tipo

**REP** · *Seleção única*

> Que tipo de dívida é esta?

**Opções:** Empréstimo consignado · Empréstimo pessoal · Financiamento de veículo · Financiamento imobiliário · Cartão de crédito — saldo rotativo · Cartão de crédito — parcelamento de fatura · Cheque especial · Parcelamento de compra · Dívida tributária · Dívida com familiar ou outra pessoa · Acordo ou renegociação · Outra

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `TIPO_DIVIDA` |
| Valor interno / mapeamento | CONSIGNADO · PESSOAL · FIN_VEICULO · FIN_IMOBILIARIO · CARTAO_ROTATIVO · CARTAO_PARCELADO · CHEQUE_ESPECIAL · PARCELAMENTO_COMPRA · TRIBUTARIA · PESSOA_FISICA · ACORDO · OUTRA |
| Salto / consequência | Define modelo da engine, exibição de B5.C07 (linhas reutilizáveis) e de B5.G03 (modalidades portáveis). |
| Uso pelo motor | Modelo A–E; gatilho B8 |

#### `B5.A03` — A — Finalidade

**REP** · *Seleção única*

> Para que essa dívida foi originalmente feita?

**Opções:** Pagar despesas do mês · Emergência ou imprevisto · Saúde · Moradia · Veículo · Educação · Compra de bem ou serviço · Reforma · Viagem/lazer · Ajudar outra pessoa · Quitar ou substituir outra dívida · Não lembro · Outra

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `FINALIDADE_DIVIDA` |
| Uso pelo motor | Risco comportamental; Bloco 12 |

#### `B5.A04` — A — Status

**REP** · *Seleção única*

> Qual destas opções descreve melhor esta operação hoje?

**Opções:** Está ativa. · Está em acordo ou renegociação. · Está sendo cobrada, mas não possui pagamento regular definido. · Acredito que esteja quitada, mas preciso confirmar. · Outra situação.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `STATUS_DIVIDA` |
| Valor interno / mapeamento | ATIVA · EM_ACORDO · COBRANCA_SEM_PAGAMENTO · QUITADA_A_CONFIRMAR · OUTRA |
| Salto / consequência | QUITADA_A_CONFIRMAR → ação de confirmação (Bloco 11); não entra em DIVIDA_TOTAL até confirmar. |

#### `B5.A05` — A — Origem

**REP** · *Sim / Não / Não sei*

> Esta operação nasceu de uma renegociação ou substituição de uma dívida anterior?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `ORIGEM_RENEGOCIACAO` |
| Salto / consequência | Sim → B5.A05A. |

#### `B5.A05A` — A — Dívida anterior

**COND** · **REP** · *Seleção única*

> A dívida anterior ainda continua existindo separadamente?

**Opções:** Não. Esta operação substituiu a anterior. · Sim. Ainda existe algum saldo ou obrigação separado. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.A05 = Sim |
| Variável gravada | `DIVIDA_ANTERIOR_SUBSISTE` |
| Valor interno / mapeamento | SUBSTITUIDA · SUBSISTE · NAO_SEI |
| Salto / consequência | SUBSTITUIDA → não cadastrar a antiga como ativa. SUBSISTE → cadastrar o resíduo como dívida própria. |
| UX / observação | Não contar antiga e nova simultaneamente como ativas quando houve substituição integral. Grupo B — Valores e saldo |

#### `B5.B01` — B — Valor original

**REP** · *Seleção única*

> Você sabe quanto foi originalmente contratado ou devido nessa operação?

**Opções:** Sim. · Aproximadamente. · Não.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `QUALIDADE_VALOR_ORIGINAL` |
| Valor interno / mapeamento | CONFIRMADA · ESTIMADA · DESCONHECIDA |
| Salto / consequência | Sim/Aproximadamente → campo R$ → VALOR_ORIGINAL. |

#### `B5.B02` — B — Já pago

**REP** · *Moeda R$*

> Você sabe aproximadamente quanto já pagou nessa operação desde o início?

**Opções:** R$ ______ · Tenho apenas uma estimativa. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `VALOR_JA_PAGO` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |
| UX / observação | Não entra no custo comparável (valor passado). |

#### `B5.B03` — B — Saldo devedor

**REP** · *Moeda R$*

> Qual é o saldo devedor atual desta dívida?

*Informe o saldo informado pelo credor hoje ou na data mais recente que você possui. Não use ‘parcela × número de parcelas restantes’ para estimar.*

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `SALDO_DEVEDOR_ATUAL` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |
| Salto / consequência | DESCONHECIDA → PRIORIDADE DE INFORMAÇÃO; STATUS_DIVIDA_TOTAL = PARCIAL. |
| Uso pelo motor | DIVIDA_TOTAL_CONHECIDA; toxicidade; ordem |

#### `B5.B04` — B — Data do saldo

**REP** · *Seleção única*

> De quando é essa informação?

**Opções:** Data (dd/mm/aaaa) · Este mês · Mês passado · Há mais tempo · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B5.B03 ≠ Não sei |
| Variável gravada | `DATA_REFERENCIA_SALDO` |
| Uso pelo motor | DESEMBOLSO_FUTURO_ATUAL |

#### `B5.B05` — B — Quitação consultada

**REP** · *Seleção única*

> Você já consultou quanto precisaria pagar hoje para quitar integralmente esta dívida?

**Opções:** Sim. · Não. · Consultei, mas o valor já venceu/expirou. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `QUITACAO_CONSULTADA` |
| Valor interno / mapeamento | SIM · NAO · EXPIROU · NAO_SEI |
| Salto / consequência | SIM → B5.B05A e B5.B05B. EXPIROU → B5.B05A como histórico (STATUS_VALIDADE_PROPOSTA = EXPIRADA). NAO → ação de consulta (Bloco 11). |

#### `B5.B05A` — B — Valor de quitação

**COND** · **REP** · *Moeda R$*

> Qual foi o valor informado para quitar a dívida?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.B05 = SIM ou EXPIROU |
| Variável gravada | `VALOR_QUITACAO_HOJE` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |
| Uso pelo motor | DESCONTO_QUITACAO; VALOR_RELEVANTE_PARA_QUITACAO |
| UX / observação | Saldo devedor ≠ valor de quitação. |

#### `B5.B05B` — B — Validade

**COND** · **REP** · *Seleção única*

> Até quando esse valor é válido?

**Opções:** Data · Validade não informada. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.B05 = SIM |
| Variável gravada | `DATA_VALIDADE_PROPOSTA` |
| Valor interno / mapeamento | data · VALIDADE_DESCONHECIDA. STATUS_VALIDADE_PROPOSTA derivado (VIGENTE · EXPIRADA · VALIDADE_DESCONHECIDA). |
| Salto / consequência | Validade desconhecida e material → PRIORIDADE DE INFORMAÇÃO. Grupo C — Fluxo |

#### `B5.C01` — C — Parcela definida

**REP** · *Sim / Não / Não sei*

> Esta dívida possui uma parcela ou prestação mensal definida atualmente?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `POSSUI_PARCELA_DEFINIDA` |
| Salto / consequência | Sim → B5.C02–C04 (Modelo 1). Não/Não sei → B5.C05 (Modelo 2). |

#### `B5.C02` — C — Parcela

**COND** · **REP** · *Moeda R$*

> Qual é o valor da parcela ou prestação que deveria ser paga atualmente?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.C01 = Sim |
| Variável gravada | `PARCELA_CONTRATUAL (= PAGAMENTO_MENSAL_DEVIDO_VIGENTE)` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |
| Uso pelo motor | RESULTADO_MENSAL_ATUAL; PRESSAO_INDIVIDUAL |

#### `B5.C03` — C — Parcelas restantes

**COND** · **REP** · *Número*

> Quantas parcelas ainda faltam?

**Opções:** ___ parcelas · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.C01 = Sim |
| Variável gravada | `PARCELAS_RESTANTES` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |
| Uso pelo motor | Engine (Modelo A); gatilho B8 |

#### `B5.C04` — C — Término

**COND** · **REP** · *Mês/ano*

> Você sabe quando essa operação termina se seguir normalmente até o fim?

**Opções:** Mês/ano · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.C01 = Sim |
| Variável gravada | `DATA_TERMINO_CONTRATUAL` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |

#### `B5.C05` — C — Mínimo exigido

**COND** · **REP** · *Sim / Não / Não sei*

> Existe algum pagamento mínimo ou valor mensal formalmente exigido hoje?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B5.C01 ≠ Sim |
| Variável gravada | `POSSUI_PAGAMENTO_MINIMO` |
| Salto / consequência | Sim → B5.C05A. Não/Não sei e B5.C06 = Não sei → cronograma definitivo desta dívida bloqueado (Matriz, Bloco 5 Grupo C). |

#### `B5.C05A` — C — Valor mínimo

**COND** · **REP** · *Moeda R$*

> Qual é esse valor mínimo?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.C05 = Sim |
| Variável gravada | `PAGAMENTO_MINIMO_INFORMADO (= PAGAMENTO_MENSAL_DEVIDO_VIGENTE)` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |

#### `B5.C06` — C — Pagamento efetivo

**REP** · *Moeda R$*

> Na prática, quanto você está pagando por mês nesta dívida atualmente?

*Informe o que realmente está saindo do seu caixa hoje, mesmo que seja diferente da parcela prevista.*

**Opções:** R$ ______ · Não estou pagando nada atualmente. · O valor varia muito. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `PAGAMENTO_MENSAL_EFETIVO` |
| Valor interno / mapeamento | valor · 0 (não pagando) · VARIA · DESCONHECIDA |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Salto / consequência | VARIA → B5.C06A. |
| Uso pelo motor | RESULTADO_CAIXA_OBSERVADO; VALOR_FLUXO_LIBERADO; Trajetória Atual |

#### `B5.C06A` — C — Média paga

**COND** · **REP** · *Moeda R$*

> Nos últimos 3 meses, qual foi aproximadamente a média mensal paga?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.C06 = VARIA |
| Variável gravada | `PAGAMENTO_MENSAL_EFETIVO (média 3 meses)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B5.C07` — C — Linha reutilizável

**COND** · **REP** · *Seleção única*

> Mesmo enquanto paga essa dívida, você continua usando esse limite ou linha de crédito?

**Opções:** Sim, com frequência. · Às vezes. · Não. · Não se aplica.

| Campo | Valor |
|---|---|
| Condição de exibição | TIPO_DIVIDA ∈ {CARTAO_ROTATIVO, CHEQUE_ESPECIAL, CARTAO_PARCELADO com limite aberto} |
| Variável gravada | `LINHA_CONTINUA_SENDO_UTILIZADA` |
| Valor interno / mapeamento | SIM · AS_VEZES · NAO · NAO_APLICA |
| Salto / consequência | SIM/AS_VEZES → B5.C07A. |
| Uso pelo motor | RISCO_COMPORTAMENTAL_DIVIDA; NOVO_USO na engine |

#### `B5.C07A` — C — Novo uso

**COND** · **REP** · *Moeda R$*

> Quanto aproximadamente você volta a utilizar por mês?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.C07 = SIM ou AS_VEZES |
| Variável gravada | `NOVO_USO` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | Engine (SALDO_ATUALIZADO) Grupo D — Custo |

#### `B5.D01` — D — Taxa

**REP** · *Seleção única*

> Você sabe qual é a taxa de juros desta operação?

**Opções:** Sim. · Tenho uma taxa, mas não sei exatamente o que ela representa. · Não.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `QUALIDADE_TAXA_INFORMADA` |
| Valor interno / mapeamento | CONFIRMADA · ESTIMADA · DESCONHECIDA |
| Salto / consequência | Sim/Tenho → B5.D01A e B5.D01B. Não → PRIORIDADE DE INFORMAÇÃO se material; taxa de referência só em cenário estimado. |

#### `B5.D01A` — D — Taxa informada

**COND** · **REP** · *Percentual %*

> Qual é a taxa informada?

**Opções:** ____ %

| Campo | Valor |
|---|---|
| Condição de exibição | B5.D01 ≠ Não |
| Variável gravada | `TAXA_INFORMADA` |
| Uso pelo motor | TAXA_EFETIVA_MENSAL_NORMALIZADA |

#### `B5.D01B` — D — Periodicidade

**COND** · **REP** · *Seleção única*

> Essa taxa é:

**Opções:** ao mês · ao ano · outra periodicidade · não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B5.D01 ≠ Não |
| Variável gravada | `PERIODICIDADE_TAXA` |
| Valor interno / mapeamento | MENSAL · ANUAL · OUTRA · NAO_SEI |
| Uso pelo motor | Normalização de taxas |

#### `B5.D02` — D — Natureza

**COND** · **REP** · *Seleção única*

> O documento informa se essa taxa é efetiva ou nominal?

**Opções:** Efetiva · Nominal · Não está indicado · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B5.D01 ≠ Não E documento disponível (B5.I01 inclui contrato/DDC/extrato) |
| Variável gravada | `NATUREZA_TAXA` |
| Valor interno / mapeamento | EFETIVA · NOMINAL · NAO_INDICADO · NAO_SEI |
| UX / observação | Exibir somente quando fizer sentido documentalmente. |

#### `B5.D03` — D — CET

**REP** · *Seleção única*

> Você possui o CET — Custo Efetivo Total — desta operação?

**Opções:** Sim. · Não. · Não sei o que é.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `POSSUI_CET` |
| Valor interno / mapeamento | SIM · NAO · NAO_SEI |
| Salto / consequência | Sim → B5.D03A. "Não sei o que é" → exibir explicação curta e tratar como NAO. |

#### `B5.D03A` — D — CET informado

**COND** · **REP** · *Percentual %*

> Qual é o CET informado?

**Opções:** ____ % · + periodicidade: ao mês / ao ano

| Campo | Valor |
|---|---|
| Condição de exibição | B5.D03 = Sim |
| Variável gravada | `CET (+ PERIODICIDADE_CET)` |
| Qualidade do dado | CONFIRMADA |
| Uso pelo motor | Comparação econômica (não evolução de saldo) |

#### `B5.D04` — D — Outros custos

**REP** · *Sim / Não / Não sei*

> Além dos juros, existe alguma tarifa, encargo ou custo relevante que você saiba estar sendo cobrado nessa operação?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `OUTROS_CUSTOS_EXISTE` |
| Salto / consequência | Sim → B5.D04A. |

#### `B5.D04A` — D — Outros custos — valor

**COND** · **REP** · *Moeda R$*

> Quanto aproximadamente?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.D04 = Sim |
| Variável gravada | `OUTROS_CUSTOS` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |
| Uso pelo motor | DESEMBOLSO_FUTURO_ATUAL |

#### `B5.D05` — D — Seguro

**REP** · *Sim / Não / Não sei*

> Existe seguro prestamista ou outro seguro associado a esta dívida?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `SEGURO_PRESTAMISTA` |
| Salto / consequência | Sim → B5.D05A e B5.D05B. Sim/Não sei → ACAO_VERIFICAR_SEGURO. |

#### `B5.D05A` — D — Custo do seguro

**COND** · **REP** · *Seleção única*

> Você sabe quanto esse seguro custa?

**Opções:** R$ ___ por mês · R$ ___ no total · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B5.D05 = Sim |
| Variável gravada | `CUSTO_SEGURO (+ base MENSAL/TOTAL)` |
| Qualidade do dado | ESTIMADA ou DESCONHECIDA |

#### `B5.D05B` — D — Seguro na parcela

**COND** · **REP** · *Sim / Não / Não sei*

> Esse custo já está incluído no valor da parcela que você informou?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B5.D05 = Sim |
| Variável gravada | `SEGURO_INCLUIDO_PARCELA` |
| UX / observação | Nunca duplicar custo do seguro. Grupo E — Situação |

#### `B5.E01` — E — Pagamento hoje

**REP** · *Seleção única*

> Como está o pagamento desta dívida hoje?

**Opções:** Está em dia. · Existe parcela/valor vencido. · Estou pagando parcialmente. · Não existe pagamento regular definido atualmente. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `DIVIDA_EM_DIA / DIVIDA_ATRASADA` |
| Valor interno / mapeamento | EM_DIA · VENCIDO · PARCIAL · SEM_PAGAMENTO_REGULAR · NAO_SEI |
| Salto / consequência | VENCIDO/PARCIAL → B5.E02. |
| Uso pelo motor | Toxicidade; RISCO_PATRIMONIAL; gatilho B7 |

#### `B5.E02` — E — Tempo de atraso

**COND** · **REP** · *Seleção única*

> Há quanto tempo existe valor vencido?

**Opções:** Menos de 30 dias · 1–3 meses · 4–6 meses · 7–12 meses · Mais de 12 meses · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B5.E01 = VENCIDO ou PARCIAL |
| Variável gravada | `TEMPO_ATRASO` |

#### `B5.E03` — E — Negativação

**REP** · *Sim / Não / Não sei*

> Esta dívida aparece atualmente em cadastro de inadimplência/negativação?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `NEGATIVACAO` |
| Uso pelo motor | Gatilho B7 |

#### `B5.E04` — E — Cobrança

**REP** · *Seleção única*

> Você está recebendo atualmente cobranças relacionadas a essa dívida?

**Opções:** Sim, com frequência. · Sim, eventualmente. · Não. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `COBRANCA_ATIVA` |
| Valor interno / mapeamento | FREQUENTE · EVENTUAL · NAO · NAO_SEI |

#### `B5.E05` — E — Judicial

**REP** · *Sim / Não / Não sei*

> Você tem conhecimento de algum processo judicial ou cobrança judicial relacionada a esta dívida?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `COBRANCA_JUDICIAL_INFORMADA` |
| UX / observação | Não inferir consequências jurídicas. Grupo F — Garantia |

#### `B5.F01` — F — Garantia

**REP** · *Sim / Não / Não sei*

> Esta dívida está vinculada a algum bem ou garantia?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `POSSUI_GARANTIA` |
| Salto / consequência | Sim → B5.F02 e B5.F03. |
| Uso pelo motor | RISCO_PATRIMONIAL |

#### `B5.F02` — F — Tipo de garantia

**COND** · **REP** · *Seleção única*

> Qual é a garantia?

**Opções:** Imóvel · Veículo · Outro bem · Aval/fiança · Saldo/aplicação financeira · Outra · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B5.F01 = Sim |
| Variável gravada | `TIPO_GARANTIA` |
| UX / observação | Imóvel/Veículo → vincular à ficha do Bloco 4 correspondente (SALDO_PASSIVO_VINCULADO). |

#### `B5.F03` — F — Bem essencial

**COND** · **REP** · *Seleção única*

> Esse bem é essencial para sua moradia, trabalho, saúde ou rotina familiar?

**Opções:** Sim. · É importante, mas existem alternativas. · Não. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B5.F01 = Sim |
| Variável gravada | `GARANTIA_ESSENCIAL` |
| Valor interno / mapeamento | ESSENCIAL · IMPORTANTE · NAO · NAO_SEI |

#### `B5.F04` — F — Consequência

**REP** · *Checklist (múltipla)*

> Você sabe de alguma consequência específica que pode ocorrer se esta dívida continuar sem pagamento ou irregular?

**Opções:** Risco sobre um bem dado em garantia · Negativação · Cobrança · Desconto em folha · Outra consequência informada pelo credor/documento · Não sei · Nenhuma consequência específica que eu conheça

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `CONSEQUENCIA_INADIMPLEMENTO` |
| UX / observação | Não inferir consequências não informadas. Grupo G — Oportunidades |
| Exclusividade | "Não sei" e "Nenhuma" são exclusivas. |

#### `B5.G01` — G — Proposta atual

**REP** · *Seleção única*

> Existe alguma proposta atual do credor para esta dívida?

**Opções:** Sim. · Não. · Recebi uma proposta, mas ela já venceu. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `PROPOSTA_ATUAL` |
| Valor interno / mapeamento | SIM · NAO · EXPIRADA · NAO_SEI |
| Uso pelo motor | Gatilho B7 (detalhes coletados no Bloco 7) |

#### `B5.G02` — G — Já renegociada

**REP** · *Sim / Não / Não sei*

> Esta dívida já foi renegociada alguma vez?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `JA_RENEGOCIADA` |
| Uso pelo motor | Bloco 7 |

#### `B5.G03` — G — Portabilidade

**COND** · **REP** · *Seleção única*

> Você já consultou a possibilidade de levar ou substituir esta dívida por uma condição mais barata em outra instituição?

**Opções:** Sim. · Não. · Não sei / nunca verifiquei.

| Campo | Valor |
|---|---|
| Condição de exibição | TIPO_DIVIDA em modalidade substituível (consignado, pessoal, financiamentos, cartão, cheque especial) |
| Variável gravada | `PORTABILIDADE_CONSULTADA` |
| Valor interno / mapeamento | SIM · NAO · NAO_SEI |
| Uso pelo motor | Gatilho B8 Grupo H — Dimensão humana |

#### `B5.H01` — H — Peso emocional

**REP** · *Escala 0–10*

> De 0 a 10, quanto esta dívida pesa emocionalmente para você hoje?

**Opções:** 0 = praticamente não me incomoda. · 10 = é uma das dívidas que mais me preocupa ou desgasta.

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `PESO_EMOCIONAL` |
| Salto / consequência | ≥ 4 → B5.H02. |
| Uso pelo motor | Dimensão 5; Ranking Emocional; Bloco 9/10 |

#### `B5.H02` — H — Motivo do peso

**COND** · **REP** · *Checklist (múltipla)*

> O que mais faz essa dívida pesar para você?

**Opções:** Juros muito altos · Parcela pesada · Está atrasada · Cobranças · Risco sobre algum bem · Envolve familiar ou pessoa próxima · Quero me livrar dela há muito tempo · Vergonha, culpa ou preocupação · Não consigo entender bem a dívida · Outro

| Campo | Valor |
|---|---|
| Condição de exibição | B5.H01 ≥ 4 |
| Variável gravada | `MOTIVO_PESO_EMOCIONAL` |
| Salto / consequência | "Outro" → texto curto OPT. |

#### `B5.H03` — H — Urgência

**REP** · *Escala 0–10*

> Na sua percepção, de 0 a 10, com que urgência esta dívida precisa ser resolvida?

**Opções:** 0 = pode esperar, sem urgência relevante · 10 = máxima urgência na percepção do usuário

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `URGENCIA_PERCEBIDA` |
| Valor interno / mapeamento | URGENCIA_PERCEBIDA = inteiro 0–10 |
| UX / observação | Slider 0–10 com âncoras nas pontas. Não usar rótulos qualitativos. |

#### `B5.H04` — H — Preferência

**REP** · *Sim / Não / Não sei*

> Se você pudesse eliminar apenas uma das suas dívidas primeiro, esta estaria entre suas primeiras escolhas?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `PREFERENCIA_QUITACAO` |
| Uso pelo motor | Bloco 9/10 (não decide sozinha) Grupo I — Documentação |

#### `B5.I01` — I — Documentos

**REP** · *Checklist (múltipla)*

> Que documentos ou informações você possui hoje sobre esta dívida?

**Opções:** Contrato · Extrato/demonstrativo atualizado · Documento Descritivo de Crédito — DDC ou equivalente · Fatura · Proposta de negociação · Comprovante/print de aplicativo ou internet banking · Outro documento · Não tenho nenhum documento agora

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `DOCUMENTACAO_DISPONIVEL` |
| Uso pelo motor | Qualidade; exibição de B5.D02 |
| Exclusividade | "Não tenho nenhum documento agora" é exclusiva. |

#### `B5.I02` — I — Fonte

**REP** · *Seleção única*

> De onde vieram principalmente as informações que você acabou de preencher?

**Opções:** Documento/contrato · Aplicativo ou internet banking · Atendimento do credor · Contracheque · Minha memória · Uma combinação dessas fontes · Outra

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `FONTE_DADO` |
| Valor interno / mapeamento | ORIGEM_DADO = DOCUMENTO (documento/app/contracheque) ou USUARIO (memória/atendimento/combinação) |

#### `B5.I03` — I — Atualização

**REP** · *Seleção única*

> As informações desta dívida foram consultadas ou atualizadas quando?

**Opções:** Hoje · Nos últimos 7 dias · Neste mês · Há 1–3 meses · Há mais de 3 meses · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Cada dívida |
| Variável gravada | `DATA_REFERENCIA_DADO B5.I04 — SYS: DOCUMENTO_REFERENCIA é vinculado pelo sistema quando disponível. Não exigir upload universal. Fechamento da ficha e do inventário` |

#### `B5.CHECK` — Fechamento da ficha

**REP** · *Seleção única*

> Essa ficha está correta?

**Opções:** Sim, salvar dívida. · Quero corrigir alguma informação.

| Campo | Valor |
|---|---|
| Condição de exibição | Fim de cada ficha |
| Variável gravada | `SYS (salvar/editar)` |
| Salto / consequência | Corrigir → retorna à ficha. |

#### `B5.FIM01` — Próxima dívida

**REP** · *Seleção única*

> Você ainda precisa cadastrar alguma outra dívida ou operação financeira?

**Opções:** Sim, cadastrar outra. · Não, esta foi a última. · Não tenho certeza.

| Campo | Valor |
|---|---|
| Condição de exibição | Após B5.CHECK |
| Variável gravada | `SYS (loop)` |
| Salto / consequência | Sim → nova ficha. Não/Não tenho certeza → resumo + B5.FIM02. |

#### `B5.FIM02` — Confirmação do inventário

**OBR** · *Seleção única*

> Pelo que você sabe hoje, todas as suas dívidas e operações financeiras foram cadastradas?

**Opções:** Sim. O inventário está completo. · Não. Ainda falta pelo menos uma dívida. · Não tenho certeza.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `CONFIRMACAO_FIM_CADASTRO` |
| Valor interno / mapeamento | SIM · NAO · NAO_SEI. SYS: QUANTIDADE_DIVIDAS_CADASTRADA; QUANTIDADE_DIVIDAS_DECLARADA (final confirmada, separada da inicial). |
| Salto / consequência | ≠ SIM → INVENTARIO_COMPLETO = falso → bloqueio global da Ordem Definitiva; diagnóstico parcial permitido. |
| Uso pelo motor | INVENTARIO_COMPLETO Derivadas pelo motor, nunca perguntadas: DIVIDA_TOTAL_CONHECIDA · QTD_SALDOS_DESCONHECIDOS · STATUS_DIVIDA_TOTAL · PAGAMENTOS_EFETIVOS_DIVIDAS · PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES · DESCONTO_QUITACAO · STATUS_VALIDADE_PROPOSTA · TAXA_EFETIVA_MENSAL_NORMALIZADA · INVENTARIO_COMPLETO · listas DIVIDAS_* são derivados pelo motor. BLOCO 6 Anatomia e Toxicidade Nenhuma pergunta ao usuário Derivadas pelo motor, nunca perguntadas: Nenhuma pergunta ao usuário. Entradas: Blocos 1–5. O motor calcula separadamente: toxicidade financeira; pressão orçamentária; risco patrimonial; risco comportamental; peso emocional; oportunidade; prioridade de informação; prioridade de intervenção; elegibilidade para ordenação; gatilhos de B7; gatilhos de B8. Não existe toxicidade total 0–100. Nenhum desses resultados é perguntado ou confirmado pelo usuário. BLOCO 7 Renegociação Estratégica Somente para dívidas selecionadas pelo motor CONDICIONAL O Bloco 7 abre somente para dívidas com gatilho B7 identificado pelo motor (Bloco 6). As perguntas são por dívida (REP implícito por DIVIDA_ID qualificada). TELA DE ABERTURA Antes de definir a posição desta dívida no seu plano, precisamos verificar se ela pode ser melhorada. O objetivo não é simplesmente conseguir uma parcela menor. Vamos comparar custo, prazo, juros, entrada, seguros e impacto no seu orçamento. |

<a id="bloco-7"></a>

### Bloco 7 — Renegociação

*21 perguntas.* Índice: `B7.01` · `B7.02` · `B7.03` · `B7.04` · `B7.05` · `B7.06` · `B7.07` · `B7.08` · `B7.09` · `B7.10` · `B7.11` · `B7.12` · `B7.13` · `B7.13A` · `B7.14` · `B7.15` · `B7.16` · `B7.S01` · `B7.EX01` · `B7.EX02` · `B7.EX03`

#### `B7.01` — Tentativa anterior

**COND** · *Seleção única*

> Você já tentou renegociar esta dívida com o credor?

**Opções:** Sim · Não · Não lembro ou não sei

| Campo | Valor |
|---|---|
| Condição de exibição | Dívida qualificada para B7 |
| Variável gravada | `JA_TENTOU_RENEGOCIAR` |
| Valor interno / mapeamento | SIM · NAO · NAO_SEI |
| Salto / consequência | Sim → B7.02 e B7.03. |

#### `B7.02` — Data da tentativa

**COND** · *Seleção única*

> Quando foi sua tentativa mais recente de renegociação?

**Opções:** Data · últimos 30 dias · 1–3 meses · 4–6 meses · 7–12 meses · há mais de 1 ano · não lembro

| Campo | Valor |
|---|---|
| Condição de exibição | B7.01 = Sim |
| Variável gravada | `DATA_ULTIMA_RENEGOCIACAO` |

#### `B7.03` — Resultado anterior

**COND** · *Seleção única*

> Qual foi o resultado dessa tentativa?

**Opções:** Recebi uma proposta, mas não aceitei. · Fiz uma renegociação e esta é a dívida resultante. · O credor não ofereceu uma condição diferente. · Não consegui concluir o atendimento. · A proposta venceu antes da decisão. · Outro resultado. · Não lembro.

| Campo | Valor |
|---|---|
| Condição de exibição | B7.01 = Sim |
| Variável gravada | `RESULTADO_RENEGOCIACAO_ANTERIOR` |
| Valor interno / mapeamento | RECUSEI · EXECUTADA · SEM_OFERTA · NAO_CONCLUIDA · EXPIROU · OUTRO · NAO_SEI |

#### `B7.04` — Proposta concreta

**COND** · *Seleção única*

> Você possui hoje uma proposta concreta do credor para renegociar ou quitar esta dívida?

**Opções:** Sim, e a proposta ainda está válida. · Sim, mas não sei se ainda está válida. · Recebi uma proposta, mas ela já expirou. · Não tenho uma proposta atualmente.

| Campo | Valor |
|---|---|
| Condição de exibição | Dívida qualificada para B7 |
| Variável gravada | `EXISTE_PROPOSTA_RENEGOCIACAO (+ STATUS_VALIDADE_PROPOSTA)` |
| Valor interno / mapeamento | VIGENTE · VALIDADE_DESCONHECIDA · EXPIRADA · NAO |
| Salto / consequência | NAO → STATUS_PROCESSO_RENEGOCIACAO = AGUARDANDO_PROPOSTA; gera ação; não pedir condições hipotéticas. VIGENTE/VALIDADE_DESCONHECIDA → B7.05–B7.16. EXPIRADA → B7.05–B7.16 como histórico (não determina decisão). |

#### `B7.05` — Conteúdo da proposta

**COND** · *Checklist (múltipla)*

> O que essa proposta oferece ou pretende fazer?

**Opções:** Quitar a dívida à vista · Dar desconto · Reduzir juros · Reduzir CET · Reduzir custo total · Reduzir parcela · Reduzir prazo · Regularizar valores em atraso · Retirar seguro, tarifa ou outro custo · Outra condição

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA |
| Variável gravada | `OBJETIVO_RENEGOCIACAO` |

#### `B7.06` — Entrada

**COND** · *Sim / Não / Não sei*

> A proposta exige algum valor de entrada?

**Opções:** Sim → R$ ______ · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA |
| Variável gravada | `PROPOSTA_ENTRADA` |
| Qualidade do dado | CONFIRMADA / DESCONHECIDA |
| Uso pelo motor | DESEMBOLSO_FUTURO_PROPOSTA |

#### `B7.07` — Nova parcela

**COND** · *Moeda R$*

> Se a proposta for aceita, qual será o valor da nova parcela?

**Opções:** R$ ______ · Não há parcelas; é quitação à vista. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA |
| Variável gravada | `PROPOSTA_PARCELA` |
| Valor interno / mapeamento | valor · A_VISTA · DESCONHECIDA |

#### `B7.08` — Quantidade de parcelas

**COND** · *Número*

> Quantas parcelas serão pagas nessa proposta?

**Opções:** ___ parcelas · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B7.07 ≠ A_VISTA |
| Variável gravada | `PROPOSTA_QTD_PARCELAS` |

#### `B7.09` — Prazo

**COND** · *Seleção única*

> O prazo da proposta é diferente da quantidade de parcelas mensais informada?

**Opções:** Não · Sim → informar prazo (meses) · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B7.07 ≠ A_VISTA |
| Variável gravada | `PROPOSTA_PRAZO` |

#### `B7.10` — Nova taxa

**COND** · *Sim / Não / Não sei*

> A proposta informa uma nova taxa de juros?

**Opções:** Sim → ____ % + periodicidade (ao mês / ao ano) · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA |
| Variável gravada | `PROPOSTA_TAXA (+ periodicidade)` |

#### `B7.11` — CET da proposta

**COND** · *Sim / Não / Não sei*

> A proposta informa o CET — Custo Efetivo Total?

**Opções:** Sim → ____ % + periodicidade · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA |
| Variável gravada | `PROPOSTA_CET (+ periodicidade)` |

#### `B7.12` — Custo total informado

**COND** · *Sim / Não / Não sei*

> O documento ou o credor informa quanto você pagará no total se cumprir essa proposta até o fim?

**Opções:** Sim → R$ ______ · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA |
| Variável gravada | `PROPOSTA_CUSTO_TOTAL` |
| UX / observação | Insumo; a comparação usa PROPOSTA_CUSTO_TOTAL_COMPARAVEL (motor). |

#### `B7.13` — Desconto

**COND** · *Sim / Não / Não sei*

> O credor diz que existe desconto nessa proposta?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA |
| Variável gravada | `PROPOSTA_DESCONTO_EXISTE` |
| Salto / consequência | Sim → B7.13A. |

#### `B7.13A` — Desconto — valor

**COND** · *Seleção única*

> Foi informado algum valor de desconto?

**Opções:** R$ ______ · ____ % · O credor informou apenas que existe desconto, sem detalhar. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B7.13 = Sim |
| Variável gravada | `PROPOSTA_DESCONTO` |
| Qualidade do dado | CONFIRMADA / DESCONHECIDA |
| UX / observação | Não usar alvo universal de 20%. |

#### `B7.14` — Custos adicionais

**COND** · *Sim / Não / Não sei*

> A proposta inclui alguma tarifa, seguro, encargo ou outro custo adicional que não esteja claramente dentro da parcela informada?

**Opções:** Sim → tipo + valor R$ · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA |
| Variável gravada | `PROPOSTA_CUSTOS_ADICIONAIS` |
| Uso pelo motor | DESEMBOLSO_FUTURO_PROPOSTA |

#### `B7.15` — Validade

**COND** · *Seleção única*

> Até quando esta proposta é válida?

**Opções:** Data · O credor não informou validade. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA |
| Variável gravada | `DATA_VALIDADE_PROPOSTA → STATUS_VALIDADE_PROPOSTA` |
| Salto / consequência | Validade desconhecida e material → PRIORIDADE DE INFORMAÇÃO. |

#### `B7.16` — Registro da proposta

**COND** · *Seleção única*

> Você possui essa proposta registrada em algum documento ou canal do credor?

**Opções:** Sim, documento/contrato. · Sim, aplicativo ou internet banking. · Sim, mensagem/e-mail. · Foi apenas informada em atendimento. · Não tenho registro.

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA |
| Variável gravada | `FONTE_DADO (proposta)` |
| Valor interno / mapeamento | ORIGEM_DADO = DOCUMENTO ou USUARIO |

#### `B7.S01` — Seguro na proposta

**COND** · *Seleção única*

> A proposta altera ou mantém o seguro associado a essa dívida?

**Opções:** Mantém. · Retira. · Inclui novo seguro. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B7.04 = VIGENTE, VALIDADE_DESCONHECIDA ou EXPIRADA E SEGURO_PRESTAMISTA ≠ Não |
| Variável gravada | `PROPOSTA_SEGURO` |
| Valor interno / mapeamento | MANTEM · RETIRA · NOVO · NAO_SEI |
| UX / observação | Não afirmar automaticamente que deve cancelar ou que há restituição. Execução posterior (acompanhamento) |

#### `B7.EX01` — Contratação

**COND** · *Seleção única*

> Esta renegociação foi efetivamente contratada?

**Opções:** Sim · Não · Ainda não

| Campo | Valor |
|---|---|
| Condição de exibição | Ação de renegociação em acompanhamento |
| Variável gravada | `STATUS_PROCESSO_RENEGOCIACAO` |
| Valor interno / mapeamento | Sim = EXECUTADA · Não = ENCERRADA_SEM_ACORDO · Ainda não = mantém estado |
| Salto / consequência | Sim → B7.EX02, B7.EX03. |

#### `B7.EX02` — Data

**COND** · *Data*

> Em que data?

| Campo | Valor |
|---|---|
| Condição de exibição | B7.EX01 = Sim |
| Variável gravada | `DATA_EXECUCAO_RENEGOCIACAO` |

#### `B7.EX03` — Conformidade

**COND** · *Sim / Não / Não sei*

> As condições contratadas foram as mesmas analisadas pelo PIQ?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B7.EX01 = Sim |
| Variável gravada | `CONDICOES_CONFORME_ANALISE` |
| Salto / consequência | Não/Não sei → recadastrar condição real (B7.05–B7.15) antes de atualizar a dívida. Nova versão D00x_V2; preservar histórico. |
| Uso pelo motor | Derivadas pelo motor, nunca perguntadas: STATUS_PROCESSO_RENEGOCIACAO (exceto execução), CLASSIFICACAO_PROPOSTA_RENEGOCIACAO, ECONOMIA_RENEGOCIACAO, ALIVIO_FLUXO_RENEGOCIACAO, script de negociação são derivados pelo motor. BLOCO 8 Troca Inteligente Somente para dívidas qualificadas pelo motor CONDICIONAL O Bloco 8 abre somente para dívidas com gatilho B8 identificado pelo motor. Perguntas por dívida qualificada. TELA DE ABERTURA Existe a possibilidade de substituir esta dívida por outra operação. Antes de decidir, precisamos verificar se a troca realmente melhora a estrutura da dívida. Juros menores ou parcela menor, sozinhos, não bastam. |

<a id="bloco-8"></a>

### Bloco 8 — Troca e portabilidade

*25 perguntas.* Índice: `B8.00` · `B8.01` · `B8.02` · `B8.03` · `B8.04` · `B8.05` · `B8.05A` · `B8.06` · `B8.07` · `B8.08` · `B8.09` · `B8.10` · `B8.11` · `B8.12` · `B8.12A` · `B8.12B` · `B8.13` · `B8.13A` · `B8.13B` · `B8.14` · `B8.15` · `B8.P01` · `B8.P02` · `B8.EX01` · `B8.EX02`

#### `B8.00` — Proposta de troca

**COND** · *Seleção única*

> Você já possui uma proposta concreta para substituir ou transferir esta dívida?

**Opções:** Sim. · Não. · Estou consultando, mas ainda não recebi condições completas.

| Campo | Valor |
|---|---|
| Condição de exibição | Dívida qualificada para B8 |
| Variável gravada | `STATUS_TROCA` |
| Valor interno / mapeamento | Sim = PROPOSTA_RECEBIDA · Não = AGUARDANDO_PROPOSTA (gera ação) · Consultando = PROPOSTA_INCOMPLETA |
| Salto / consequência | Sim → B8.01–B8.15. Não/Consultando → gerar ação; não inventar números. |

#### `B8.01` — Tipo de troca

**COND** · *Seleção única*

> Qual destas opções descreve melhor a proposta recebida?

**Opções:** Portabilidade — a dívida será levada para outra instituição sem liberação de dinheiro novo. · Novo crédito para quitar esta dívida — nova operação especificamente para encerrar a atual. · Nova operação que quita a dívida atual e ainda libera dinheiro adicional. · Não sei identificar.

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `TIPO_TROCA` |
| Valor interno / mapeamento | A = A_PORTABILIDADE_VERDADEIRA · B = B_CREDITO_SUBSTITUTIVO · C = C_DINHEIRO_NOVO · D = NAO_SEI |

#### `B8.02` — Instituição

**COND** · *Busca / texto curto*

> Qual instituição está oferecendo a nova operação?

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `NOVA_INSTITUICAO` |

#### `B8.03` — Valor da nova operação

**COND** · *Moeda R$*

> Qual é o valor total da nova operação proposta?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `VALOR_NOVA_OPERACAO` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |

#### `B8.04` — Valor de substituição

**COND** · *Moeda R$*

> Quanto dessa nova operação será usado diretamente para encerrar a dívida que estamos analisando?

**Opções:** R$ ______ · Todo o valor da nova operação. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `VALOR_SUBSTITUICAO` |
| Valor interno / mapeamento | valor · = VALOR_NOVA_OPERACAO · DESCONHECIDA |
| Uso pelo motor | DINHEIRO_NOVO |

#### `B8.05` — Dinheiro adicional

**COND** · *Sim / Não / Não sei*

> Depois de quitar a dívida atual, a nova operação libera algum dinheiro adicional para você?

**Opções:** Sim → Quanto? R$ ______ · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `DINHEIRO_NOVO` |
| Qualidade do dado | CONFIRMADA / ESTIMADA / DESCONHECIDA |
| Salto / consequência | Sim → exibir box e B8.05A. |
| Uso pelo motor | RISCO_NOVO_ENDIVIDAMENTO; CENARIO_SUBSTITUICAO_EQUIVALENTE ATENÇÃO Box exibido ao usuário quando B8.05 = Sim: "DINHEIRO ADICIONAL NÃO É ECONOMIA. Se a nova operação libera valor além do necessário para quitar a dívida atual, esse valor representa novo endividamento." |

#### `B8.05A` — Finalidade do dinheiro adicional

**COND** · *Seleção única*

> Qual seria a finalidade desse dinheiro adicional?

**Opções:** Quitar outra dívida · Emergência · Despesa necessária já prevista · Compra ou consumo · Formar/manter caixa · Outra finalidade

| Campo | Valor |
|---|---|
| Condição de exibição | B8.05 = Sim |
| Variável gravada | `FINALIDADE_DINHEIRO_NOVO` |
| Valor interno / mapeamento | OUTRA_DIVIDA · EMERGENCIA · DESPESA_PREVISTA · CONSUMO · CAIXA · OUTRA |
| Salto / consequência | CONSUMO → ALERTA DE NOVO ENDIVIDAMENTO (motor). |

#### `B8.06` — Nova taxa

**COND** · *Percentual %*

> Qual é a taxa de juros da nova operação?

**Opções:** ____ % + periodicidade (ao mês / ao ano) · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `NOVA_TAXA (+ periodicidade)` |
| Qualidade do dado | CONFIRMADA / DESCONHECIDA |

#### `B8.07` — Novo CET

**COND** · *Sim / Não / Não sei*

> A proposta informa o CET da nova operação?

**Opções:** Sim → ____ % + periodicidade · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `NOVO_CET` |
| Salto / consequência | Não/Não sei → bloqueio local: CLASSIFICACAO_TROCA = A_ANALISAR (portabilidade sem CET não conclui). |

#### `B8.08` — Nova parcela

**COND** · *Moeda R$*

> Qual será o valor da nova parcela?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `NOVA_PARCELA` |
| Qualidade do dado | CONFIRMADA / DESCONHECIDA |
| Uso pelo motor | ALIVIO_MENSAL_TROCA |

#### `B8.09` — Novo prazo

**COND** · *Número*

> Quantas parcelas terá a nova operação?

**Opções:** ___ parcelas · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `NOVO_PRAZO` |

#### `B8.10` — Custo total informado

**COND** · *Sim / Não / Não sei*

> A proposta informa quanto será pago no total até o fim da nova operação?

**Opções:** Sim → R$ ______ · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `NOVO_CUSTO_TOTAL` |
| UX / observação | Insumo; comparação usa NOVO_CUSTO_TOTAL_COMPARAVEL (motor). |

#### `B8.11` — Tarifas

**COND** · *Sim / Não / Não sei*

> Existe alguma tarifa ou custo adicional na nova operação?

**Opções:** Sim → R$ ______ · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `NOVAS_TARIFAS` |

#### `B8.12` — Seguro

**COND** · *Sim / Não / Não sei*

> A nova operação inclui algum seguro?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `NOVO_SEGURO_EXISTE` |
| Salto / consequência | Sim → B8.12A e B8.12B. |

#### `B8.12A` — Seguro — custo

**COND** · *Seleção única*

> Qual é o custo desse seguro?

**Opções:** R$ ___ por mês · R$ ___ total · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.12 = Sim |
| Variável gravada | `NOVO_SEGURO` |

#### `B8.12B` — Seguro — na parcela

**COND** · *Sim / Não / Não sei*

> Esse custo já está incluído na parcela informada?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.12 = Sim |
| Variável gravada | `NOVO_SEGURO_INCLUIDO_PARCELA` |
| UX / observação | Nunca duplicar. |

#### `B8.13` — Nova garantia

**COND** · *Sim / Não / Não sei*

> A nova operação exige alguma garantia que a dívida atual não possui?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `NOVA_GARANTIA_EXISTE` |
| Salto / consequência | Sim → B8.13A e B8.13B. |
| Uso pelo motor | AGRAVAMENTO_PATRIMONIAL |

#### `B8.13A` — Nova garantia — tipo

**COND** · *Seleção única*

> Qual é essa garantia?

**Opções:** Imóvel · Veículo · Investimento · Outro bem · Aval/fiança · Outra

| Campo | Valor |
|---|---|
| Condição de exibição | B8.13 = Sim |
| Variável gravada | `NOVA_GARANTIA` |

#### `B8.13B` — Nova garantia — essencial

**COND** · *Seleção única*

> Esse bem é essencial para sua moradia, trabalho, saúde ou rotina familiar?

**Opções:** Sim · Parcialmente · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.13 = Sim |
| Variável gravada | `NOVA_GARANTIA_ESSENCIAL` |
| Valor interno / mapeamento | SIM · PARCIAL · NAO · NAO_SEI |

#### `B8.14` — Validade

**COND** · *Seleção única*

> Até quando esta proposta de troca é válida?

**Opções:** Data · Não informado · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `DATA_VALIDADE_PROPOSTA (troca) → STATUS_VALIDADE_PROPOSTA` |

#### `B8.15` — Fonte

**COND** · *Seleção única*

> De onde vieram as condições desta proposta?

**Opções:** Documento formal · Aplicativo/internet banking · Simulação fornecida pela instituição · Atendimento · Correspondente · Outra fonte

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `FONTE_DADO (troca)` |

#### `B8.P01` — Cascata

**COND** · *Sim / Não / Não sei*

> Esta proposta depende de alguma outra portabilidade ou substituição ser concluída antes?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.00 = Sim |
| Variável gravada | `TROCA_DEPENDE_DE_OUTRA` |
| Salto / consequência | Sim → B8.P02. |
| Uso pelo motor | Portabilidade em cascata (modelar sequência) |

#### `B8.P02` — Cascata — dependência

**COND** · *Seleção de DIVIDA_ID*

> Qual operação precisa ser concluída antes?

| Campo | Valor |
|---|---|
| Condição de exibição | B8.P01 = Sim |
| Variável gravada | `TROCA_DEPENDENCIA_DIVIDA_ID Execução posterior (acompanhamento)` |

#### `B8.EX01` — Conclusão

**COND** · *Seleção única*

> A troca/portabilidade foi efetivamente concluída?

**Opções:** Sim · Não · Ainda está em andamento

| Campo | Valor |
|---|---|
| Condição de exibição | Ação de troca em acompanhamento |
| Variável gravada | `STATUS_TROCA` |
| Valor interno / mapeamento | Sim = EXECUTADA · Não = ENCERRADA_SEM_TROCA · Em andamento = mantém |
| Salto / consequência | Sim → B8.EX02. |

#### `B8.EX02` — Encerramento da antiga

**COND** · *Sim / Não / Não sei*

> A dívida antiga foi integralmente encerrada pela nova operação?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B8.EX01 = Sim |
| Variável gravada | `DIVIDA_ANTIGA_ENCERRADA` |
| Salto / consequência | Sim → DIVIDA_ORIGEM STATUS = QUITADA_POR_SUBSTITUICAO; DIVIDA_SUBSTITUTA criada com ORIGEM = SUBSTITUICAO_D00x; preservar vínculo. Não → cadastrar resíduo. STATUS_TROCA (enum operacional): NAO_APLICAVEL · INVESTIGAR · AGUARDANDO_PROPOSTA · PROPOSTA_RECEBIDA · PROPOSTA_INCOMPLETA · EXECUTADA · ENCERRADA_SEM_TROCA. Não confundir com CLASSIFICACAO_TROCA (motor). |
| Uso pelo motor | Derivadas pelo motor, nunca perguntadas: CLASSIFICACAO_TROCA, ECONOMIA_TROCA, CENARIO_SUBSTITUICAO_EQUIVALENTE, ALIVIO_MENSAL_TROCA, RISCO_NOVO_ENDIVIDAMENTO, AGRAVAMENTO_PATRIMONIAL são derivados pelo motor. BLOCO 9 Método de Quitação Como o usuário tende a executar um plano de longo prazo TELA DE ABERTURA Agora precisamos entender como você tende a executar um plano de longo prazo. Duas pessoas com as mesmas dívidas podem precisar de estratégias diferentes. Para uma, esperar mais tempo em troca de maior economia funciona bem. Para outra, eliminar uma dívida mais cedo pode ser importante para manter o plano vivo. As próximas perguntas não escolhem o método sozinhas. Elas serão combinadas com a matemática das suas dívidas. |

<a id="bloco-9"></a>

### Bloco 9 — Comportamento e método

*6 perguntas.* Índice: `B9.01` · `B9.02` · `B9.03` · `B9.04` · `B9.04A` · `B9.05`

#### `B9.01` — Tolerância à espera

**OBR** · *Escala 0–10*

> De 0 a 10, quanto você acredita que consegue manter um plano mesmo que demore alguns meses para a primeira dívida desaparecer?

**Opções:** 0 = Eu teria muita dificuldade. · 10 = Consigo esperar se souber que a estratégia faz sentido.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `TOLERANCIA_ESPERA` |
| Uso pelo motor | Tabela de decisão do método |

#### `B9.02` — Necessidade de vitória

**OBR** · *Escala 0–10*

> De 0 a 10, quanto eliminar uma dívida relativamente cedo aumentaria sua confiança para continuar executando o plano?

**Opções:** 0 = Isso faria pouca diferença para mim. · 10 = Uma primeira quitação rápida faria muita diferença para eu continuar.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `NECESSIDADE_VITORIA` |
| Uso pelo motor | Tabela de decisão; incompatibilidade comportamental grave |

#### `B9.03` — Disciplina

**OBR** · *Escala 0–10*

> De 0 a 10, quão consistente você costuma ser ao seguir um plano financeiro por vários meses, mesmo quando ele exige repetir as mesmas ações?

**Opções:** 0 = Tenho muita dificuldade de manter. · 10 = Normalmente mantenho até o objetivo.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `DISCIPLINA_EXECUCAO` |

#### `B9.04` — Histórico de abandono

**OBR** · *Seleção única*

> Nos últimos dois anos, você começou algum plano para organizar as finanças, quitar dívidas, economizar ou investir e depois abandonou antes de alcançar o objetivo?

**Opções:** Sim, isso aconteceu mais de uma vez. · Sim, aconteceu uma vez. · Não. · Não comecei nenhum plano desse tipo nesse período. · Não lembro / não sei avaliar.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `HISTORICO_ABANDONO` |
| Valor interno / mapeamento | MAIS_DE_UMA · UMA · NAO · SEM_PLANO · NAO_SEI (HISTORICO_ABANDONO = SIM para A ou B) |
| Salto / consequência | Sim → B9.04A. |

#### `B9.04A` — Motivo do abandono

**COND** · *Checklist (múltipla)*

> O que mais contribuiu para você abandonar esses planos?

**Opções:** Demorei a perceber resultado. · O plano era difícil demais de acompanhar. · Surgiu um imprevisto financeiro. · Minha renda caiu. · Voltei a fazer novas dívidas. · Perdi motivação. · O plano exigia um valor que eu não conseguia sustentar. · Faltava acompanhamento. · Não conseguia controlar os gastos. · Outro motivo. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B9.04 = Sim |
| Variável gravada | `MOTIVO_ABANDONO` |
| Uso pelo motor | Justificativa do método; Bloco 12 |
| Exclusividade | "Não sei" é exclusiva. |

#### `B9.05` — Preferência

**OBR** · *Seleção única*

> Se mais de uma estratégia for viável para o seu caso, qual destas formas de avançar combina mais com você?

**Opções:** Quero priorizar a maior economia possível, mesmo que a primeira dívida demore mais para · desaparecer. · Prefiro eliminar uma dívida mais cedo, mesmo que isso possa custar um pouco mais, desde que a · diferença não seja grande. · Prefiro buscar um equilíbrio: conquistar uma vitória relativamente cedo e depois concentrar o plano · na maior eficiência financeira. · Não tenho preferência. Quero seguir a estratégia que o PIQ indicar como mais adequada.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `PREFERENCIA_METODO (= METODO_PREFERIDO_USUARIO)` |
| Valor interno / mapeamento | A = AVALANCHE · B = BOLA_DE_NEVE · C = HIBRIDO · D = SEM_PREFERENCIA |
| Uso pelo motor | Derivadas pelo motor, nunca perguntadas: METODO_RECOMENDADO_PIQ · STATUS_METODO · cenários · JUSTIFICATIVA_METODO são derivados pelo motor. Reutiliza RISCO_RECAIDA, NIVEL_CONTROLE, RISCO_COMPORTAMENTAL_GERAL, PESO_EMOCIONAL, PREFERENCIA_QUITACAO sem repetir perguntas. BLOCO 10 Ordem Inteligente de Ataque 100% motor — exceção: confirmação do ataque imediato Derivadas pelo motor, nunca perguntadas: O Bloco 10 não possui perguntas destinadas à formação da ordem. A Ordem Inteligente de Ataque é 100% motor. Somente após a recomendação de uso imediato de recursos existe confirmação humana. |
| UX / observação | Preferência não decide sozinha. |

<a id="bloco-10"></a>

### Bloco 10 — Ataque imediato

*2 perguntas.* Índice: `B10.C01` · `B10.C01A`

#### `B10.C01` — Confirmação do ataque imediato

**COND** · *Seleção única*

> Quanto desse valor recomendado você realmente confirma que pretende utilizar no plano?

**Opções:** Quero utilizar todo o valor recomendado. · Quero utilizar apenas uma parte. · Não quero utilizar esse recurso agora. · Quero revisar a recomendação antes de decidir.

| Campo | Valor |
|---|---|
| Condição de exibição | ATAQUE_IMEDIATO_RECOMENDADO > 0 |
| Variável gravada | `ATAQUE_IMEDIATO_APROVADO` |
| Valor interno / mapeamento | TODO → = RECOMENDADO · PARTE → B10.C01A · NAO → 0 · REVISAR → pendente (0 até decidir) |
| Salto / consequência | Validação: 0 ≤ APROVADO ≤ RECOMENDADO. Não perguntar qual dívida receberá o recurso — a ordem é do motor. |
| Uso pelo motor | Cronograma-base |

#### `B10.C01A` — Valor confirmado

**COND** · *Moeda R$*

> Qual valor você confirma?

**Opções:** R$ ______

| Campo | Valor |
|---|---|
| Condição de exibição | B10.C01 = PARTE |
| Variável gravada | `ATAQUE_IMEDIATO_APROVADO` |
| Qualidade do dado | CONFIRMADA BLOCO 11 Plano de Execução Perguntas surgem durante execução e acompanhamento — não no diagnóstico inicial REGRA CANÔNICA Este bloco não é um questionário inicial. As perguntas surgem durante execução e acompanhamento, vinculadas a ACAO_ID (SYS) ou DIVIDA_ID. TELA DE ABERTURA Seu plano agora precisa sair do papel. O PIQ organizou o que deve ser feito primeiro, o que pode esperar e o que depende de alguma informação ou resposta de terceiros. Você não precisa resolver tudo hoje. Execute a próxima ação indicada e atualize o resultado. |

<a id="bloco-11"></a>

### Bloco 11 — Execução e acompanhamento

*23 perguntas.* Índice: `B11.01` · `B11.02` · `B11.03-INF` · `B11.03-REN` · `B11.03-TRO` · `B11.03-ECO` · `B11.03-E` · `B11.04` · `B11.05` · `B11.Q01` · `B11.Q02` · `B11.Q03` · `B11.Q04` · `B11.Q04A` · `B11.Q05` · `B11.Q06` · `B11.RE01` · `B11.RE02` · `B11.RE03` · `B11.RE03A` · `B11.A01` · `B11.A01A` · `B11.A02`

#### `B11.01` — Status da ação

**COND** · *Seleção única*

> Como está esta ação?

**Opções:** Ainda não comecei. · Estou fazendo. · Já fiz e estou aguardando resposta de outra pessoa ou instituição. · Não consegui concluir porque apareceu algum impedimento. · Concluí. · Esta ação não será mais necessária.

| Campo | Valor |
|---|---|
| Condição de exibição | Por ação (ACAO_ID) em acompanhamento |
| Variável gravada | `ACAO_STATUS` |
| Valor interno / mapeamento | PENDENTE · EM_EXECUCAO · AGUARDANDO_TERCEIRO · BLOQUEADA · CONCLUIDA · DESCARTADA |
| Salto / consequência | CONCLUIDA → B11.02 + resultado por tipo. BLOQUEADA → B11.05. |

#### `B11.02` — Data de conclusão

**COND** · *Data*

> Quando você concluiu esta ação?

| Campo | Valor |
|---|---|
| Condição de exibição | B11.01 = CONCLUIDA |
| Variável gravada | `ACAO_DATA_CONCLUSAO` |

#### `B11.03-INF` — Resultado — informação

**COND** · *Seleção única*

> Você conseguiu obter a informação solicitada?

**Opções:** Sim. · Parcialmente. · Não.

| Campo | Valor |
|---|---|
| Condição de exibição | B11.01 = CONCLUIDA E TIPO_ACAO = INFORMAÇÃO |
| Variável gravada | `RESULTADO_ACAO_INFORMACAO` |
| Salto / consequência | Sim → abrir exclusivamente o campo que estava faltando (ex.: B5.B03, B5.D01A). |

#### `B11.03-REN` — Resultado — renegociação

**COND** · *Seleção única*

> Você recebeu uma proposta?

**Opções:** Sim. · Não. · Ainda estou aguardando.

| Campo | Valor |
|---|---|
| Condição de exibição | TIPO_ACAO = INTERVENÇÃO (renegociação) |
| Variável gravada | `RESULTADO_ACAO_RENEGOCIACAO` |
| Salto / consequência | Sim → abrir Bloco 7 (B7.05–B7.16). |

#### `B11.03-TRO` — Resultado — troca

**COND** · *Seleção única*

> Você recebeu uma proposta concreta de troca/portabilidade?

**Opções:** Sim. · Não. · Ainda estou aguardando.

| Campo | Valor |
|---|---|
| Condição de exibição | TIPO_ACAO = TROCA |
| Variável gravada | `RESULTADO_ACAO_TROCA` |
| Salto / consequência | Sim → abrir Bloco 8 (B8.01–B8.15). |

#### `B11.03-ECO` — Resultado — economia

**COND** · *Seleção única*

> A redução de gasto foi realmente implementada?

**Opções:** Sim, integralmente. · Sim, parcialmente. · Não.

| Campo | Valor |
|---|---|
| Condição de exibição | TIPO_ACAO = CORREÇÃO (economia) |
| Variável gravada | `RESULTADO_ACAO_ECONOMIA` |
| Salto / consequência | Integral/parcial → B11.03-ECO-A. |

#### `B11.03-E` — CO-A Economia realizada

**COND** · *Moeda R$*

> Qual foi a economia mensal realmente obtida?

**Opções:** R$ ______

| Campo | Valor |
|---|---|
| Condição de exibição | B11.03-ECO ≠ Não |
| Variável gravada | `ECONOMIA_REALIZADA` |
| Qualidade do dado | CONFIRMADA |
| Salto / consequência | Converter potencial em realizado; retirar de ECONOMIA_POTENCIAL_IMEDIATA (não duplicar). |

#### `B11.04` — Resultado diferente

**COND** · *Sim / Não / Não sei*

> O resultado foi diferente do que estava previsto no seu plano?

**Opções:** Sim · Não · Não sei

| Campo | Valor |
|---|---|
| Condição de exibição | B11.01 = CONCLUIDA |
| Variável gravada | `RESULTADO_DIVERGENTE` |
| Salto / consequência | Sim → abrir apenas os dados que mudaram e recalcular (EVENTO_RECALCULO). |

#### `B11.05` — Impedimento

**COND** · *Seleção única*

> O que impediu você de concluir esta ação?

**Opções:** Não consegui contato com o credor. · O credor recusou. · Não consegui o documento necessário. · A condição oferecida foi diferente. · Não tenho o recurso financeiro necessário. · Surgiu uma despesa inesperada. · Minha renda mudou. · Não consegui executar no prazo. · Decidi não executar. · Outro motivo.

| Campo | Valor |
|---|---|
| Condição de exibição | B11.01 = BLOQUEADA |
| Variável gravada | `MOTIVO_BLOQUEIO_ACAO` |
| Salto / consequência | Acionar Plano B correspondente (motor). Quitação real |

#### `B11.Q01` — Quitação

**COND** · *Seleção única*

> A dívida [Dxxx] foi efetivamente quitada?

**Opções:** Sim, foi quitada. · Ainda não. · Acredito que sim, mas ainda preciso confirmar.

| Campo | Valor |
|---|---|
| Condição de exibição | Dívida com STATUS_QUITACAO_PROJETADO = quitada ou declarada pelo usuário |
| Variável gravada | `STATUS_QUITACAO_REAL` |
| Valor interno / mapeamento | Sim = QUITADA · Ainda não = NAO · Acredito = A_CONFIRMAR |
| Salto / consequência | Somente Sim pode tornar STATUS_QUITACAO_REAL = QUITADA → B11.Q02–Q06. |

#### `B11.Q02` — Data da quitação

**COND** · *Data*

> Em que data a dívida foi quitada?

| Campo | Valor |
|---|---|
| Condição de exibição | B11.Q01 = QUITADA |
| Variável gravada | `DATA_QUITACAO_REAL` |

#### `B11.Q03` — Valor pago

**COND** · *Moeda R$*

> Quanto foi efetivamente pago no pagamento final/quitação?

**Opções:** R$ ______ · Não sei com segurança.

| Campo | Valor |
|---|---|
| Condição de exibição | B11.Q01 = QUITADA |
| Variável gravada | `VALOR_PAGO_QUITACAO` |
| Qualidade do dado | CONFIRMADA / DESCONHECIDA |

#### `B11.Q04` — Saldo restante

**COND** · *Seleção única*

> Depois desse pagamento, o credor confirmou que não existe saldo restante?

**Opções:** Sim, saldo zerado/contrato encerrado. · Ainda aparece algum saldo. · Ainda não confirmei.

| Campo | Valor |
|---|---|
| Condição de exibição | B11.Q01 = QUITADA |
| Variável gravada | `CONFIRMACAO_SALDO_ZERO` |
| Valor interno / mapeamento | ZERADO · RESIDUO · NAO_CONFIRMADO |
| Salto / consequência | RESIDUO → B11.Q04A (dívida permanece ativa com resíduo). |

#### `B11.Q04A` — Resíduo

**COND** · *Moeda R$*

> Qual saldo ainda aparece?

**Opções:** R$ ______ · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B11.Q04 = RESIDUO |
| Variável gravada | `SALDO_DEVEDOR_ATUAL (resíduo)` |
| Qualidade do dado | CONFIRMADA / DESCONHECIDA |

#### `B11.Q05` — Comprovante

**COND** · *Seleção única*

> Você possui comprovante ou confirmação da quitação?

**Opções:** Sim. · Não. · Ainda não.

| Campo | Valor |
|---|---|
| Condição de exibição | B11.Q01 = QUITADA |
| Variável gravada | `COMPROVANTE_QUITACAO` |
| Salto / consequência | Não/Ainda não → ação: obter comprovante. |

#### `B11.Q06` — Fluxo liberado

**COND** · *Seleção única*

> Depois da quitação, quanto realmente deixou de sair do seu orçamento todos os meses?

*Mostrar o valor que vinha sendo efetivamente pago (PAGAMENTO_MENSAL_EFETIVO).*

**Opções:** R$ X está correto. · O valor real é outro → R$ ______ · Nenhum valor foi liberado, porque eu não estava pagando essa dívida atualmente. · Não sei.

| Campo | Valor |
|---|---|
| Condição de exibição | B11.Q01 = QUITADA |
| Variável gravada | `VALOR_FLUXO_LIBERADO` |
| Valor interno / mapeamento | X · outro valor · 0 · DESCONHECIDA |
| Uso pelo motor | CAPACIDADE_POS_QUITACAO (efeito cascata) Recursos extraordinários |

#### `B11.RE01` — Recebimento

**COND** · *Seleção única*

> O recurso extraordinário que você esperava receber já entrou?

**Opções:** Sim. · Ainda não. · Não será mais recebido. · O valor mudou.

| Campo | Valor |
|---|---|
| Condição de exibição | Recurso extraordinário previsto em B3.05 com janela vencida ou atualização |
| Variável gravada | `STATUS_RECURSO_EXTRAORDINARIO` |
| Valor interno / mapeamento | RECEBIDO · PENDENTE · CANCELADO · ALTERADO |
| Salto / consequência | RECEBIDO/ALTERADO → B11.RE02, B11.RE03. CANCELADO → EVENTO_RECALCULO. |

#### `B11.RE02` — Valor recebido

**COND** · *Moeda R$*

> Quanto você efetivamente recebeu?

**Opções:** R$ ______

| Campo | Valor |
|---|---|
| Condição de exibição | B11.RE01 = RECEBIDO ou ALTERADO |
| Variável gravada | `VALOR_RECURSO_EXTRAORDINARIO (realizado)` |
| Qualidade do dado | CONFIRMADA |

#### `B11.RE03` — Destinação

**COND** · *Seleção única*

> Quanto desse recurso você confirma que pretende direcionar ao seu plano de quitação?

**Opções:** Todo o valor. · Uma parte. · Nenhum valor neste momento. · Quero comparar os cenários antes de decidir.

| Campo | Valor |
|---|---|
| Condição de exibição | B11.RE01 = RECEBIDO ou ALTERADO |
| Variável gravada | `ATAQUE_IMEDIATO_APROVADO (recurso extraordinário)` |
| Valor interno / mapeamento | TODO · PARTE → B11.RE03A · NENHUM = 0 · COMPARAR = pendente |
| UX / observação | Nunca utilizar regra 70/30 automática. Não reaparece como evento separado na engine. |

#### `B11.RE03A` — Destinação — valor

**COND** · *Moeda R$*

> Qual valor?

**Opções:** R$ ______

| Campo | Valor |
|---|---|
| Condição de exibição | B11.RE03 = PARTE |
| Variável gravada | `ATAQUE_IMEDIATO_APROVADO (parcela)` |
| Qualidade do dado | CONFIRMADA Ataque mensal |

#### `B11.A01` — Ataque do mês

**COND** · *Seleção única*

> Neste mês, você conseguiu realizar o ataque adicional previsto pelo PIQ?

**Opções:** Sim, integralmente. · Sim, mas apenas uma parte. · Não consegui fazer ataque adicional neste mês. · Fiz um valor maior do que o planejado.

| Campo | Valor |
|---|---|
| Condição de exibição | Revisão mensal |
| Variável gravada | `ATAQUE_ADICIONAL_REALIZADO_STATUS` |
| Valor interno / mapeamento | INTEGRAL · PARCIAL · NENHUM · MAIOR |
| Salto / consequência | ≠ INTEGRAL → B11.A01A e B11.A02. |

#### `B11.A01A` — Valor direcionado

**COND** · *Moeda R$*

> Quanto foi efetivamente direcionado?

**Opções:** R$ ______

| Campo | Valor |
|---|---|
| Condição de exibição | B11.A01 ≠ INTEGRAL |
| Variável gravada | `ATAQUE_ADICIONAL_REALIZADO` |
| Qualidade do dado | CONFIRMADA |
| Uso pelo motor | ADERENCIA_PLANO (motor); gatilho de revisão de capacidade |

#### `B11.A02` — Motivo da diferença

**COND** · *Seleção única*

> O que mais contribuiu para essa diferença?

**Opções:** Renda menor. · Despesa maior. · Emergência. · Nova dívida. · Gasto não previsto. · Decidi preservar caixa. · Recebi recurso adicional. · Consegui economizar mais. · Outra razão.

| Campo | Valor |
|---|---|
| Condição de exibição | B11.A01 ≠ INTEGRAL |
| Variável gravada | `MOTIVO_DIFERENCA_ATAQUE` |
| Salto / consequência | Nova dívida / renda menor → EVENTO_RECALCULO. |
| Uso pelo motor | Derivadas pelo motor, nunca perguntadas: ADERENCIA_PLANO é derivada pelo motor. Não perguntar "sua aderência é alta/média/baixa". BLOCO 12 Blindagem Antidívidas Mecanismos de não retorno TELA DE ABERTURA Seu PIQ não termina quando a última dívida desaparece. Agora vamos criar algumas regras simples para reduzir a chance de o endividamento voltar. Você não precisa viver cercado de proibições. O objetivo é identificar os seus principais riscos e criar poucas barreiras que realmente funcionem para você. REGRA CANÔNICA Reutiliza sem repetir: MECANISMO_DEFICIT, HISTORICO_RECAIDA, CAUSA_RECAIDA, PARTICIPACAO_FAMILIAR (B1); RISCO_IMPULSO, GASTOS_FANTASMAS, NIVEL_CONTROLE, GAP_AUTOPERCEPCAO (B2); linhas reutilizáveis, cartão, cheque especial, risco comportamental (B5/B6). |

<a id="bloco-12"></a>

### Bloco 12 — Blindagem e pós-quitação

*19 perguntas.* Índice: `B12.01` · `B12.02` · `B12.03` · `B12.04` · `B12.05` · `B12.06` · `B12.07` · `B12.08` · `B12.09` · `B12.10` · `B12.11` · `B12.12` · `B12.12A` · `B12.13` · `B12.14` · `B12.15` · `B12.16` · `B12.16A` · `B12.17`

#### `B12.01` — Causas

**OBR** · *Checklist (múltipla)*

> Olhando para a sua história financeira, quais fatores contribuíram de verdade para suas dívidas atuais?

**Opções:** Minhas despesas ficaram maiores que minha renda. · Emergência ou imprevisto. · Perda ou redução de renda. · Falta de reserva financeira. · Uso do cartão de crédito. · Parcelamentos sucessivos. · Facilidade de acesso a crédito. · Compras por impulso. · Padrão de vida acima do que o orçamento comportava. · Ajuda financeira a familiares ou terceiros. · Fiz uma dívida para pagar outra. · Falta de acompanhamento/controle financeiro. · Um evento excepcional. · Outra causa.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `CAUSAS_ENDIVIDAMENTO` |
| Salto / consequência | "Outra causa" → texto curto OPT. |

#### `B12.02` — Causa principal

**OBR** · *Seleção única*

> Se você tivesse de escolher apenas uma, qual dessas causas mais explica o seu endividamento atual?

**Opções:** (mostrar somente as opções escolhidas em B12.01)

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre (opções filtradas por B12.01) |
| Variável gravada | `CAUSA_PRINCIPAL_ENDIVIDAMENTO` |

#### `B12.03` — Risco principal

**OBR** · *Seleção única*

> Qual destas situações representa hoje o maior risco de você voltar a se endividar ou aumentar novamente as dívidas?

**Opções:** Cartão de crédito · Novos parcelamentos · Uso de limite/crédito disponível · Emergência · Ajuda a familiar/terceiro · Falta de controle · Renda insuficiente · Compras por impulso · Padrão de vida · Outra · Não consigo identificar

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `RISCO_PRINCIPAL_RECAIDA` |
| Valor interno / mapeamento | CARTAO · PARCELAMENTO · LIMITE · EMERGENCIA · AJUDA_FAMILIAR · FALTA_CONTROLE · RENDA_INSUFICIENTE · IMPULSO · PADRAO_VIDA · OUTRO · NAO_IDENTIFICA |
| Salto / consequência | Define relevância de B12.07, B12.08, B12.09, B12.12. |

#### `B12.04` — Gatilhos

**OBR** · *Checklist (múltipla)*

> Em quais situações você percebe que fica mais vulnerável a gastar, parcelar ou usar crédito sem planejamento?

**Opções:** Promoções · Redes sociais · Estresse · Ansiedade · Cansaço · Vontade de me recompensar · Pressão familiar/social · Quando recebo dinheiro extra · Quando o banco aumenta meu limite · Quando uma parcela ‘parece caber’ · Emergências · Datas comemorativas · Outra · Não identifico um gatilho específico

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `GATILHOS_RECAIDA` |
| Exclusividade | "Não identifico um gatilho específico" é exclusiva. |

#### `B12.05` — Barreiras externas

**OBR** · *Checklist (múltipla)*

> Para reduzir o risco de recaída, quais destas barreiras você aceita adotar?

**Opções:** Reduzir limite do cartão. · Cancelar cartão que não preciso. · Bloquear cheque especial. · Remover cartões salvos em aplicativos/sites. · Retirar aplicativo que facilita compras impulsivas. · Desabilitar ofertas de crédito. · Não solicitar aumento de margem. · Cancelar assinatura/gasto recorrente identificado. · Separar uma conta específica para gastos. · Automatizar transferência. · Outra barreira.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre; mostrar somente opções relevantes ao caso (cartão, cheque especial, margem, gastos fantasmas, impulso) |
| Variável gravada | `BARREIRAS_EXTERNAS` |
| UX / observação | Pergunta adaptativa. |

#### `B12.06` — Barreiras internas

**OBR** · *Checklist (múltipla)*

> Quais regras pessoais você aceita usar para tornar uma decisão de gasto mais consciente?

**Opções:** Aplicar uma regra de espera. · Consultar o orçamento antes da compra. · Não parcelar consumo. · Falar com uma pessoa de confiança antes de uma decisão relevante. · Comprar somente o que estiver em lista/planejamento. · Criar um teto pessoal para determinados gastos. · Criar uma regra familiar. · Outra.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `BARREIRAS_INTERNAS` |

#### `B12.07` — Regra de espera

**COND** · *Seleção única*

> Para compras que não estavam planejadas, qual regra de espera você considera realmente capaz de cumprir?

**Opções:** Esperar 24 horas. · Esperar 48 horas. · Esperar 7 dias. · Quero definir outro prazo. · Não quero utilizar uma regra de espera.

| Campo | Valor |
|---|---|
| Condição de exibição | RISCO_IMPULSO ≠ NENHUMA OU "Aplicar uma regra de espera" marcada em B12.06 OU RISCO_PRINCIPAL_RECAIDA = IMPULSO |
| Variável gravada | `REGRA_ESPERA` |
| Valor interno / mapeamento | 24H · 48H · 7D · OUTRA (→ texto curto OPT) · NENHUMA |
| UX / observação | Não impor a mesma regra para todos. |

#### `B12.08` — Regra do cartão

**COND** · *Seleção única*

> Qual regra para o cartão de crédito faz mais sentido para sua nova fase?

**Opções:** Não utilizar cartão por enquanto. · Usar somente para gastos planejados. · Usar apenas quando o dinheiro para pagar a compra já estiver reservado. · Reduzir o limite. · Não fazer novas compras parceladas. · Usar cartão apenas para uma finalidade específica. · Outra regra.

| Campo | Valor |
|---|---|
| Condição de exibição | Cartão relevante: dívida de cartão no B5, CARTAO em MECANISMO_DEFICIT, RISCO_PRINCIPAL_RECAIDA = CARTAO ou B12.01 inclui cartão |
| Variável gravada | `REGRA_CARTAO` |

#### `B12.09` — Regra de parcelamento

**COND** · *Seleção única*

> Qual destas regras melhor representa o que você quer adotar para novas compras parceladas?

**Opções:** Não vou fazer novas compras parceladas enquanto houver dívida no PIQ. · Só vou parcelar compras já previstas no orçamento e cujo valor total eu teria condições de pagar. · Não vou utilizar parcelamento para fazer caber no mês algo que o orçamento não comporta. · Quero definir outra regra.

| Campo | Valor |
|---|---|
| Condição de exibição | Parcelamento relevante: NOVO_PARCELAMENTO_PREVISTO ≠ NAO, PARCELAMENTO em MECANISMO_DEFICIT, RISCO_PRINCIPAL_RECAIDA = PARCELAMENTO ou B12.01 inclui parcelamentos |
| Variável gravada | `REGRA_PARCELAMENTO` |
| Valor interno / mapeamento | A = SEM_PARCELAMENTO · B = SO_PLANEJADO · C = NAO_PARA_CABER · D = OUTRA (→ texto curto OPT) |

#### `B12.10` — Emergência

**OBR** · *Seleção única*

> Se surgisse hoje uma despesa realmente necessária e inesperada, qual seria sua principal forma de pagá-la?

**Opções:** Reserva financeira. · Renda do mês. · Cortaria/adaptaria outros gastos. · Cartão de crédito. · Empréstimo. · Ajuda de terceiro. · Não sei como pagaria.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `RESPOSTA_EMERGENCIA` |
| Valor interno / mapeamento | RESERVA · RENDA · CORTE · CARTAO · EMPRESTIMO · TERCEIRO · NAO_SEI |
| Salto / consequência | CARTAO/EMPRESTIMO/TERCEIRO/NAO_SEI → vulnerabilidade → B12.11. |

#### `B12.11` — Plano de emergência

**COND** · *Seleção única*

> Você aceita incluir essa proteção no seu plano?

**Opções:** Sim. · Quero ajustar. · Não neste momento.

| Campo | Valor |
|---|---|
| Condição de exibição | B12.10 ∈ {CARTAO, EMPRESTIMO, TERCEIRO, NAO_SEI} |
| Variável gravada | `PLANO_EMERGENCIA` |
| Valor interno / mapeamento | SIM · AJUSTAR · NAO |
| UX / observação | Não impor percentual ou valor universal de reserva. |

#### `B12.12` — Ajuda a terceiros

**COND** · *Seleção única*

> Você quer estabelecer uma regra para ajuda financeira a familiares ou outras pessoas?

**Opções:** Sim. · Não considero necessário. · Quero avaliar.

| Campo | Valor |
|---|---|
| Condição de exibição | Ajuda a terceiros relevante: B12.01 inclui ajuda, RISCO_PRINCIPAL_RECAIDA = AJUDA_FAMILIAR, CAUSA_RECAIDA = AJUDA_TERCEIRO ou TERCEIRO em MECANISMO_DEFICIT |
| Variável gravada | `REGRA_AJUDA_TERCEIROS_EXISTE` |
| Salto / consequência | Sim → B12.12A. |

#### `B12.12A` — Regra de ajuda

**COND** · *Seleção única*

> Qual regra faz sentido?

**Opções:** Definir um teto mensal. · Não utilizar cartão, empréstimo ou limite para ajudar terceiros. · Ajudar apenas quando houver dinheiro disponível no orçamento. · Outra regra.

| Campo | Valor |
|---|---|
| Condição de exibição | B12.12 = Sim |
| Variável gravada | `REGRA_AJUDA_TERCEIROS` |
| Salto / consequência | Teto mensal → campo R$ (OPT). |

#### `B12.13` — Alinhamento familiar

**COND** · *Seleção única*

> Você aceita incluir uma conversa de alinhamento financeiro como uma ação do PIQ?

**Opções:** Sim. · Já estamos alinhados. · Ainda não. · Não se aplica mais.

| Campo | Valor |
|---|---|
| Condição de exibição | PARTICIPACAO_FAMILIAR ∈ {PARCIALMENTE_ALINHADA, ALINHAMENTO_NECESSARIO} |
| Variável gravada | `ACAO_ALINHAMENTO_FAMILIAR` |
| Valor interno / mapeamento | SIM · JA_ALINHADOS · AINDA_NAO · NAO_APLICA |

#### `B12.14` — Sinais de recaída

**OBR** · *Checklist (múltipla)*

> Quais destes sinais devem funcionar como um alerta de que seu plano está começando a sair da rota?

**Opções:** Usar cartão para despesas básicas por falta de dinheiro. · Voltar a parcelar repetidamente. · Parar de registrar os gastos. · Entrar no cheque especial. · Não conseguir pagar a fatura integral. · Aumentar limite para continuar gastando. · Começar a esconder compras ou dívidas. · Fazer empréstimo para fechar a conta corrente. · Minha renda cair e eu não ajustar os gastos. · Contrair uma nova dívida. · Parar de fazer as revisões financeiras. · Outro.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `SINAIS_RECAIDA` |

#### `B12.15` — Plano de resposta

**COND** · *Seleção única*

> Você aceita esta regra de resposta?

*O motor seleciona risco/sinal e apresenta: "SE [sinal], ENTÃO [resposta]." Uma pergunta por regra proposta.*

**Opções:** Sim. · Quero ajustar. · Não.

| Campo | Valor |
|---|---|
| Condição de exibição | Para cada regra SE→ENTÃO proposta pelo motor |
| Variável gravada | `PLANO_RESPOSTA_RECAIDA` |
| Valor interno / mapeamento | ACEITA · AJUSTAR (→ texto curto OPT) · RECUSA |
| UX / observação | Cada risco relevante deve possuir BARREIRA_ASSOCIADA ou PLANO_RESPOSTA_RECAIDA. |

#### `B12.16` — Regra pessoal

**OBR** · *Seleção única*

> Qual destas frases você quer adotar como sua regra principal?

*O motor apresenta 2 ou 3 regras coerentes com o caso; as frases acima são exemplos, exibidos somente se aderentes.*

**Opções:** “Eu não contrato crédito para pagar despesas recorrentes do meu mês.” · “Se o orçamento não comporta a compra, a parcela também não cabe.” · “Parcela liberada não vira aumento de padrão de vida enquanto houver dívida.” · Quero escrever minha própria regra.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `REGRA_PESSOAL` |
| Salto / consequência | "Quero escrever" → B12.16A. |

#### `B12.16A` — Regra pessoal — própria

**COND** · *Texto curto*

> Escreva sua regra pessoal em uma frase curta.

| Campo | Valor |
|---|---|
| Condição de exibição | B12.16 = Quero escrever |
| Variável gravada | `REGRA_PESSOAL (texto)` |
| UX / observação | Texto curto; única entrada livre obrigatória do bloco. |

#### `B12.17` — Compromisso pós-quitação

**OBR** · *Checklist (múltipla)*

> Quando o PIQ terminar, quais hábitos você quer manter para proteger sua vida financeira?

**Opções:** Continuar registrando os gastos. · Manter uma revisão financeira semanal. · Construir/manter reserva. · Reduzir exposição a crédito. · Manter limites de crédito controlados. · Continuar usando minha regra de espera. · Fazer planejamento financeiro familiar. · Outro.

| Campo | Valor |
|---|---|
| Condição de exibição | Sempre |
| Variável gravada | `COMPROMISSO_POS_QUITACAO` |
| Uso pelo motor | NIVEL_BLINDAGEM é derivado pelo motor. Não perguntar diretamente. |
<a id="sec-12"></a>

## 12. Índice de variáveis

270 variáveis coletadas, em ordem alfabética. Para variáveis derivadas pelo motor, ver a seção 9.

| Variável | Coletada em | Bloco | Tipo | Cardinalidade | Domínio / mapeamento |
|---|---|---|---|---|---|
| `ACAO_ALINHAMENTO_FAMILIAR` | `B12.13` | 12 | Seleção única | única | SIM · JA_ALINHADOS · AINDA_NAO · NAO_APLICA |
| `ACAO_DATA_CONCLUSAO` | `B11.02` | 11 | Data | única |  |
| `ACAO_STATUS` | `B11.01` | 11 | Seleção única | única | PENDENTE · EM_EXECUCAO · AGUARDANDO_TERCEIRO · BLOQUEADA · CONCLUIDA · DESCARTADA |
| `ACEITA_REDUCAO_GASTOS_FANTASMAS` | `B2.10A` | 2 | Seleção única | única | SIM · TALVEZ · NAO |
| `ACESSO_MARGENS` | `B3.S05` | 3 | Seleção única | única | SIM · PARCIAL · NAO |
| `ATAQUE_ADICIONAL_REALIZADO` | `B11.A01A` | 11 | Moeda R$ | única | R$ ______ |
| `ATAQUE_ADICIONAL_REALIZADO_STATUS` | `B11.A01` | 11 | Seleção única | única | INTEGRAL · PARCIAL · NENHUM · MAIOR |
| `ATAQUE_IMEDIATO_APROVADO` | `B10.C01` · `B10.C01A` · `B11.RE03` · `B11.RE03A` | 10 | Seleção única | única | TODO → = RECOMENDADO · PARTE → B10.C01A · NAO → 0 · REVISAR → pendente (0 até decidir) |
| `AUTOPERCEPCAO_CONTROLE` | `B2.13` | 2 | Escala 0–10 | única | 0 = Tenho muito pouca visibilidade. · 10 = Sei com bastante clareza para onde meu dinheiro vai. |
| `BARREIRAS_EXTERNAS` | `B12.05` | 12 | Checklist (múltipla) | única | Reduzir limite do cartão. · Cancelar cartão que não preciso. · Bloquear cheque especial. · Remover cartões salvos em aplicativos/sites. · Retirar apli |
| `BARREIRAS_INTERNAS` | `B12.06` | 12 | Checklist (múltipla) | única | Aplicar uma regra de espera. · Consultar o orçamento antes da compra. · Não parcelar consumo. · Falar com uma pessoa de confiança antes de uma decisão |
| `CAPACIDADE_ATAQUE_DECLARADA` | `B3.C01` | 3 | Moeda R$ | única | valor · 0 · DESCONHECIDA |
| `CAUSAS_ENDIVIDAMENTO` | `B12.01` | 12 | Checklist (múltipla) | única | Minhas despesas ficaram maiores que minha renda. · Emergência ou imprevisto. · Perda ou redução de renda. · Falta de reserva financeira. · Uso do cart |
| `CAUSA_PRINCIPAL_ENDIVIDAMENTO` | `B12.02` | 12 | Seleção única | única | (mostrar somente as opções escolhidas em B12.01) |
| `CAUSA_RECAIDA` | `B1.11` | 1 | Seleção única | única | RENDA_INSUFICIENTE · EMERGENCIA · SEM_RESERVA · COMPRA_CREDITO · IMPULSO · PADRAO_VIDA · AJUDA_TERCEIRO · DIVIDA_PARA_DIVIDA · FALTA_CONTROLE · OUTRO  |
| `CERTEZA_RECURSO_EXTRAORDINARIO` | `B3.05D` | 3 | Seleção única | REP | CONFIRMADO · PROVAVEL · POSSIVEL |
| `CET` | `B5.D03A` | 5 | Percentual % | REP | ____ % · + periodicidade: ao mês / ao ano |
| `CLASSIFICACAO_FIXA_VARIAVEL` | `B3.DF02` | 3 | Seleção única | REP | FIXA · VARIAVEL · NAO_SEI |
| `CLASSIFICACAO_OBRIGATORIA` | `B3.DF03` | 3 | Seleção única | REP | OBRIGATORIA · NAO_OBRIGATORIA · NAO_SEI |
| `COBERTURA_MEIOS_PAGAMENTO` | `B2.05` | 2 | Seleção única | única | TOTAL · QUASE_TOTAL · PARCIAL · NAO_SEI |
| `COBERTURA_PEQUENOS_GASTOS` | `B2.04` | 2 | Seleção única | única | TODOS · MAIORIA · ALGUNS · QUASE_NENHUM · NAO_ENTRAM |
| `COBRANCA_ATIVA` | `B5.E04` | 5 | Seleção única | REP | FREQUENTE · EVENTUAL · NAO · NAO_SEI |
| `COBRANCA_JUDICIAL_INFORMADA` | `B5.E05` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `COMPROMISSO_POS_QUITACAO` | `B12.17` | 12 | Checklist (múltipla) | única | Continuar registrando os gastos. · Manter uma revisão financeira semanal. · Construir/manter reserva. · Reduzir exposição a crédito. · Manter limites  |
| `COMPROVANTE_QUITACAO` | `B11.Q05` | 11 | Seleção única | única | Sim. · Não. · Ainda não. |
| `CONDICOES_CONFORME_ANALISE` | `B7.EX03` | 7 | Sim / Não / Não sei | única | Sim · Não · Não sei |
| `CONFIRMACAO_FIM_CADASTRO` | `B5.FIM02` | 5 | Seleção única | única | SIM · NAO · NAO_SEI. SYS: QUANTIDADE_DIVIDAS_CADASTRADA; QUANTIDADE_DIVIDAS_DECLARADA (final confirmada, separada da inicial). |
| `CONFIRMACAO_MAPEAMENTO_DESPESAS` | `B3.C00` | 3 | Seleção única | única | SIM · FALTA_DESPESA · VALOR_ERRADO · NAO_SEI |
| `CONFIRMACAO_MAPEAMENTO_PATRIMONIAL` | `B4.F01` | 4 | Seleção única | única | COMPLETO · FALTA · NAO_SEI |
| `CONFIRMACAO_SALDO_ZERO` | `B11.Q04` | 11 | Seleção única | única | ZERADO · RESIDUO · NAO_CONFIRMADO |
| `CONHECIMENTO_GASTO` | `B2.06` | 2 | Seleção única | única | BOA_APROXIMACAO · RAZOAVEL · NOCAO_GERAL · NAO_SEI |
| `CONSEQUENCIA_INADIMPLEMENTO` | `B5.F04` | 5 | Checklist (múltipla) | REP | Risco sobre um bem dado em garantia · Negativação · Cobrança · Desconto em folha · Outra consequência informada pelo credor/documento · Não sei · Nenh |
| `CONTRIBUICAO_FAMILIAR` | `B3.04A` | 3 | Moeda R$ | única | R$ ______ · Não sei. |
| `CONTRIBUICAO_FAMILIAR_EXISTE` | `B3.04` | 3 | Sim / Não | única | Sim · Não |
| `CREDOR` | `B5.A01` | 5 | Busca/seleção + nome do credor | REP |  |
| `CUSTOS_ESTIMADOS_DESMOBILIZACAO` | `B4.I09` · `B4.V09` · `B4.O09` | 4 | Moeda R$ ou Percentual % | REP | R$ ______ · ____ % · Não sei. |
| `CUSTO_DESMOBILIZACAO_INVESTIMENTOS` | `B4.06A` | 4 | Moeda R$ ou Percentual % | REP | R$ ______ · ____ % · Não sei |
| `CUSTO_DESMOBILIZACAO_INVESTIMENTOS_EXISTE` | `B4.06` | 4 | Seleção única | REP | NAO · SIM · TALVEZ · NAO_SEI |
| `CUSTO_IMOVEL` | `B4.I06` | 4 | Moeda R$ | REP | R$ ______ · Não possui custo relevante. · Não sei. |
| `CUSTO_OUTRO_ATIVO` | `B4.O06` | 4 | Sim / Não | REP | Sim · Não → se Sim: R$ ______ por mês |
| `CUSTO_RECORRENTE_VEICULO` | `B4.V05` | 4 | Moeda R$ | REP | R$ ______ · Não sei. |
| `CUSTO_SEGURO` | `B5.D05A` | 5 | Seleção única | REP | R$ ___ por mês · R$ ___ no total · Não sei |
| `DATA_EXECUCAO_RENEGOCIACAO` | `B7.EX02` | 7 | Data | única |  |
| `DATA_QUITACAO_REAL` | `B11.Q02` | 11 | Data | única |  |
| `DATA_REFERENCIA_MARGEM` | `B3.S06E` | 3 | Data | REP | Data · Não sei |
| `DATA_REFERENCIA_SALDO` | `B5.B04` | 5 | Seleção única | REP | Data (dd/mm/aaaa) · Este mês · Mês passado · Há mais tempo · Não sei |
| `DATA_TERMINO_CONTRATUAL` | `B5.C04` | 5 | Mês/ano | REP | Mês/ano · Não sei. |
| `DATA_ULTIMA_RENEGOCIACAO` | `B7.02` | 7 | Seleção única | única | Data · últimos 30 dias · 1–3 meses · 4–6 meses · 7–12 meses · há mais de 1 ano · não lembro |
| `DATA_VALIDADE_PROPOSTA` | `B5.B05B` | 5 | Seleção única | REP | data · VALIDADE_DESCONHECIDA. STATUS_VALIDADE_PROPOSTA derivado (VIGENTE · EXPIRADA · VALIDADE_DESCONHECIDA). |
| `DEFASAGEM_REGISTRO` | `B2.03` | 2 | Seleção única | única | NA_HORA · MESMO_DIA · DIAS_DEPOIS · FIM_SEMANA · FIM_MES · SEM_PADRAO |
| `DESCONTO_CONTRACHEQUE_NAO_RECONHECIDO` | `B3.S08` | 3 | Sim / Não / Não sei | única | Sim · Não · Não sei |
| `DESPESAS_NAO_MENSAIS_EXISTE` | `B3.NM01` | 3 | Seleção única | única | SIM · NAO · NAO_SEI |
| `DESPESA_EXTRA_EXISTE` | `B3.D11` | 3 | Sim / Não | única | Sim · Não |
| `DESPESA_NAO_MENSAL_JA_CONTABILIZADA` | `B3.NM02D` | 3 | Seleção única | REP | Sim · Não · Não sei |
| `DINHEIRO_DISPONIVEL` | `B4.01A` | 4 | Moeda R$ | única | R$ ______ |
| `DINHEIRO_DISPONIVEL_EXISTE` | `B4.01` | 4 | Seleção única | única | SIM · NAO · NAO_SEI |
| `DINHEIRO_NOVO` | `B8.05` | 8 | Sim / Não / Não sei | única | Sim → Quanto? R$ ______ · Não · Não sei |
| `DISCIPLINA_EXECUCAO` | `B9.03` | 9 | Escala 0–10 | única | 0 = Tenho muita dificuldade de manter. · 10 = Normalmente mantenho até o objetivo. |
| `DISPOSICAO_USO_INVESTIMENTO` | `B4.06B` | 4 | Seleção única | REP | SIM · TALVEZ · NAO |
| `DISPOSICAO_USO_RESERVA` | `B4.03` | 4 | Seleção única | única | PARTE · GRANDE_PARTE · TALVEZ · NAO |
| `DIVIDA_ANTERIOR_SUBSISTE` | `B5.A05A` | 5 | Seleção única | REP | SUBSTITUIDA · SUBSISTE · NAO_SEI |
| `DIVIDA_ANTIGA_ENCERRADA` | `B8.EX02` | 8 | Sim / Não / Não sei | única | Sim · Não · Não sei |
| `DOCUMENTACAO_DISPONIVEL` | `B5.I01` | 5 | Checklist (múltipla) | REP | Contrato · Extrato/demonstrativo atualizado · Documento Descritivo de Crédito — DDC ou equivalente · Fatura · Proposta de negociação · Comprovante/pri |
| `ECONOMIA_REALIZADA` | `B11.03-E` | 11 | Moeda R$ | única | R$ ______ |
| `ECONOMIA_RECORRENTE_SUBSTITUICAO_VEICULO` | `B4.V08C` | 4 | Moeda R$ | REP | R$ ______ · Não sei. |
| `EXISTE_PROPOSTA_RENEGOCIACAO` | `B7.04` | 7 | Seleção única | única | VIGENTE · VALIDADE_DESCONHECIDA · EXPIRADA · NAO |
| `FALTA_PERCEBIDA` | `B3.C02B` | 3 | Moeda R$ | única | R$ ______ |
| `FINALIDADE_DINHEIRO_NOVO` | `B8.05A` | 8 | Seleção única | única | OUTRA_DIVIDA · EMERGENCIA · DESPESA_PREVISTA · CONSUMO · CAIXA · OUTRA |
| `FINALIDADE_DIVIDA` | `B5.A03` | 5 | Seleção única | REP | Pagar despesas do mês · Emergência ou imprevisto · Saúde · Moradia · Veículo · Educação · Compra de bem ou serviço · Reforma · Viagem/lazer · Ajudar o |
| `FINALIDADE_NOVA_DIVIDA` | `B1.03` | 1 | Seleção única | única | NECESSIDADE · CONSUMO · EMERGENCIA · REESTRUTURACAO_DIVIDA · OUTRA |
| `FINALIDADE_NOVA_DIVIDA_OUTRA` | `B1.03A` | 1 | Texto curto | única |  |
| `FONTE_DADO` | `B5.I02` · `B7.16` · `B8.15` | 5 | Seleção única | REP | ORIGEM_DADO = DOCUMENTO (documento/app/contracheque) ou USUARIO (memória/atendimento/combinação) |
| `FREQUENCIA_DESPESA_NAO_MENSAL` | `B3.NM02C` | 3 | Seleção única | REP | ANUAL · SEMESTRAL · TRIMESTRAL · OUTRA |
| `FREQUENCIA_REGISTRO` | `B2.02` | 2 | Seleção única | única | DIARIA · VARIAS_SEMANA · SEMANAL · VARIAS_MES · SOB_DEMANDA · INDEFINIDA |
| `GARANTIA_ESSENCIAL` | `B5.F03` | 5 | Seleção única | REP | ESSENCIAL · IMPORTANTE · NAO · NAO_SEI |
| `GASTOS_FANTASMAS` | `B2.09` | 2 | Seleção única | única | SIM · TALVEZ · NAO |
| `GASTOS_NAO_IDENTIFICADOS` | `B2.07` | 2 | Seleção única | única | NUNCA · RARAMENTE · ALGUMAS_MES · FREQUENTE · NAO_CONFERE |
| `GATILHOS_RECAIDA` | `B12.04` | 12 | Checklist (múltipla) | única | Promoções · Redes sociais · Estresse · Ansiedade · Cansaço · Vontade de me recompensar · Pressão familiar/social · Quando recebo dinheiro extra · Quan |
| `HISTORICO_ABANDONO` | `B9.04` | 9 | Seleção única | única | MAIS_DE_UMA · UMA · NAO · SEM_PLANO · NAO_SEI (HISTORICO_ABANDONO = SIM para A ou B) |
| `HISTORICO_RECAIDA` | `B1.10` | 1 | Seleção única | única | HISTORICO_RECAIDA: SIM (A ou B) · NAO · NAO_SEI. Auxiliar FREQUENCIA_RECAIDA_RECENTE: MAIS_DE_UMA · UMA · NENHUMA · NAO_SEI |
| `IMOVEL_ESSENCIAL` | `B4.I07` | 4 | Seleção única | REP | ESSENCIAL · IMPORTANTE · NAO_ESSENCIAL |
| `IMOVEL_EXISTE` | `B4.I01` | 4 | Sim / Não | única | Sim · Não |
| `IMOVEL_GERA_RENDA` | `B4.I05` | 4 | Sim / Não | REP | Sim · Não |
| `IMOVEL_POSSUI_PASSIVO` | `B4.I04` | 4 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `INVESTIMENTOS_EXISTE` | `B4.04` | 4 | Seleção única | única | SIM · NAO · NAO_SEI |
| `ITENS_DESPESA_ALIMENTACAO` | `B3.D02` | 3 | Checklist (múltipla) | única | lista de itens marcados; cada item → ficha B3.DF |
| `ITENS_DESPESA_COMPRAS` | `B3.D09` | 3 | Checklist (múltipla) | única | lista de itens marcados; cada item → ficha B3.DF |
| `ITENS_DESPESA_CUIDADOS` | `B3.D10` | 3 | Checklist (múltipla) | única | lista de itens marcados; cada item → ficha B3.DF |
| `ITENS_DESPESA_EDUCACAO` | `B3.D05` | 3 | Checklist (múltipla) | única | lista de itens marcados; cada item → ficha B3.DF |
| `ITENS_DESPESA_FILHOS` | `B3.D06` | 3 | Checklist (múltipla) | única | lista de itens marcados; cada item → ficha B3.DF |
| `ITENS_DESPESA_LAZER` | `B3.D08` | 3 | Checklist (múltipla) | única | lista de itens marcados; cada item → ficha B3.DF |
| `ITENS_DESPESA_MORADIA` | `B3.D01` | 3 | Checklist (múltipla) | única | lista de itens marcados; cada item → ficha B3.DF |
| `ITENS_DESPESA_SEGUROS` | `B3.D07` | 3 | Checklist (múltipla) | única | lista de itens marcados; cada item → ficha B3.DF |
| `ITENS_DESPESA_TRANSPORTE` | `B3.D03` | 3 | Checklist (múltipla) | única | lista de itens marcados; cada item → ficha B3.DF |
| `JANELA_LIBERACAO_MARGEM` | `B3.S07B` | 3 | Seleção única | única | 1–3 meses · 4–6 meses · 7–12 meses · Não sei |
| `JANELA_NOVA_DIVIDA` | `B1.05` | 1 | Seleção única | única | ATE_30D · 1_3M · 4_6M · 7_12M · APOS_12M · NAO_SEI. DATA_NOVA_DIVIDA gravada somente quando houver data concreta. |
| `JANELA_OBRIGACAO_FUTURA` | `B1.06C` | 1 | Seleção única | REP | Próximos 30 dias · 1–3 meses · 4–6 meses · 7–12 meses · Não sei |
| `JANELA_RECURSO_EXTRAORDINARIO` | `B3.05C` | 3 | Seleção única | REP | Próximos 30 dias · 1–3 meses · 4–6 meses · 7–12 meses · Ainda não sei |
| `JA_RENEGOCIADA` | `B5.G02` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `JA_TENTOU_RENEGOCIAR` | `B7.01` | 7 | Seleção única | única | SIM · NAO · NAO_SEI |
| `LINHA_CONTINUA_SENDO_UTILIZADA` | `B5.C07` | 5 | Seleção única | REP | SIM · AS_VEZES · NAO · NAO_APLICA |
| `LIQUIDEZ_INVESTIMENTOS` | `B4.05` | 4 | Seleção única | REP | D0 · D1 · D7 · D30 · MAIS_30 · BLOQUEADO · NAO_SEI |
| `LOCAL_RESERVA` | `B4.02B` | 4 | Checklist (múltipla) | única | Conta corrente · Conta remunerada · Poupança · CDB/RDB · Tesouro Direto · Fundo de renda fixa · Outro investimento · Dinheiro em espécie · Outro · Não |
| `MARGEM_A_LIBERAR_EXISTE` | `B3.S07` | 3 | Sim / Não / Não sei | única | Sim · Não · Não sei |
| `MECANISMO_DEFICIT` | `B1.09` | 1 | Checklist (múltipla) | única | CORTE · RESERVA · CARTAO · CHEQUE_ESPECIAL · EMPRESTIMO · PARCELAMENTO · ATRASO · TERCEIRO · RENDA_EXTRA · NAO_OCORRE · OUTRA |
| `MEIOS_PAGAMENTO_FORA_CONTROLE` | `B2.05A` | 2 | Checklist (múltipla) | única | Pix · Cartão de crédito · Cartão de débito · Dinheiro · Débito automático · Transferências · Compras parceladas · Outra |
| `MOTIVO_ABANDONO` | `B9.04A` | 9 | Checklist (múltipla) | única | Demorei a perceber resultado. · O plano era difícil demais de acompanhar. · Surgiu um imprevisto financeiro. · Minha renda caiu. · Voltei a fazer nova |
| `MOTIVO_BLOQUEIO_ACAO` | `B11.05` | 11 | Seleção única | única | Não consegui contato com o credor. · O credor recusou. · Não consegui o documento necessário. · A condição oferecida foi diferente. · Não tenho o recu |
| `MOTIVO_DIFERENCA_ATAQUE` | `B11.A02` | 11 | Seleção única | única | Renda menor. · Despesa maior. · Emergência. · Nova dívida. · Gasto não previsto. · Decidi preservar caixa. · Recebi recurso adicional. · Consegui econ |
| `MOTIVO_PESO_EMOCIONAL` | `B5.H02` | 5 | Checklist (múltipla) | REP | Juros muito altos · Parcela pesada · Está atrasada · Cobranças · Risco sobre algum bem · Envolve familiar ou pessoa próxima · Quero me livrar dela há  |
| `NATUREZA_TAXA` | `B5.D02` | 5 | Seleção única | REP | EFETIVA · NOMINAL · NAO_INDICADO · NAO_SEI |
| `NECESSIDADE_VITORIA` | `B9.02` | 9 | Escala 0–10 | única | 0 = Isso faria pouca diferença para mim. · 10 = Uma primeira quitação rápida faria muita diferença para eu continuar. |
| `NEGATIVACAO` | `B5.E03` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `NOVAS_TARIFAS` | `B8.11` | 8 | Sim / Não / Não sei | única | Sim → R$ ______ · Não · Não sei |
| `NOVA_DIVIDA_PREVISTA` | `B1.02` | 1 | Seleção única | única | SIM · TALVEZ · NAO |
| `NOVA_GARANTIA` | `B8.13A` | 8 | Seleção única | única | Imóvel · Veículo · Investimento · Outro bem · Aval/fiança · Outra |
| `NOVA_GARANTIA_ESSENCIAL` | `B8.13B` | 8 | Seleção única | única | SIM · PARCIAL · NAO · NAO_SEI |
| `NOVA_GARANTIA_EXISTE` | `B8.13` | 8 | Sim / Não / Não sei | única | Sim · Não · Não sei |
| `NOVA_INSTITUICAO` | `B8.02` | 8 | Busca / texto curto | única |  |
| `NOVA_PARCELA` | `B8.08` | 8 | Moeda R$ | única | R$ ______ · Não sei. |
| `NOVA_TAXA` | `B8.06` | 8 | Percentual % | única | ____ % + periodicidade (ao mês / ao ano) · Não sei. |
| `NOVO_CET` | `B8.07` | 8 | Sim / Não / Não sei | única | Sim → ____ % + periodicidade · Não · Não sei |
| `NOVO_CUSTO_TOTAL` | `B8.10` | 8 | Sim / Não / Não sei | única | Sim → R$ ______ · Não · Não sei |
| `NOVO_PARCELAMENTO_PREVISTO` | `B1.07` | 1 | Seleção única | única | SIM · TALVEZ · NAO |
| `NOVO_PRAZO` | `B8.09` | 8 | Número | única | ___ parcelas · Não sei. |
| `NOVO_SEGURO` | `B8.12A` | 8 | Seleção única | única | R$ ___ por mês · R$ ___ total · Não sei |
| `NOVO_SEGURO_EXISTE` | `B8.12` | 8 | Sim / Não / Não sei | única | Sim · Não · Não sei |
| `NOVO_SEGURO_INCLUIDO_PARCELA` | `B8.12B` | 8 | Sim / Não / Não sei | única | Sim · Não · Não sei |
| `NOVO_USO` | `B5.C07A` | 5 | Moeda R$ | REP | R$ ______ · Não sei. |
| `OBJETIVO_RENEGOCIACAO` | `B7.05` | 7 | Checklist (múltipla) | única | Quitar a dívida à vista · Dar desconto · Reduzir juros · Reduzir CET · Reduzir custo total · Reduzir parcela · Reduzir prazo · Regularizar valores em  |
| `OBRIGACAO_FUTURA_INEVITAVEL` | `B1.06` | 1 | Seleção única | única | SIM · NAO · NAO_SEI |
| `ORGAO_FONTE_PAGADORA` | `B3.S03` | 3 | Busca / texto curto | única |  |
| `ORIGEM_RENDA_EXTRA_POTENCIAL` | `B3.06A` | 3 | Seleção única | única | Trabalho extra · Novo vínculo ou atividade · Horas extras/adicional · Aluguel · Negócio · Serviço autônomo · Outra |
| `ORIGEM_RENEGOCIACAO` | `B5.A05` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `OUTROS_CUSTOS` | `B5.D04A` | 5 | Moeda R$ | REP | R$ ______ · Não sei. |
| `OUTROS_CUSTOS_EXISTE` | `B5.D04` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `OUTRO_ATIVO_ESSENCIAL` | `B4.O07` | 4 | Seleção única | REP | ESSENCIAL · PARCIAL · NAO_ESSENCIAL |
| `OUTRO_ATIVO_EXISTE` | `B4.O01` | 4 | Sim / Não | única | Sim · Não |
| `OUTRO_ATIVO_POSSUI_PASSIVO` | `B4.O04` | 4 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `PACTO` | `B1.01` | 1 | Seleção única | única | A = ESTABELECIDO · B = EM_CONSTRUCAO · C = NAO_ESTABELECIDO |
| `PAGAMENTO_MENSAL_EFETIVO` | `B5.C06` · `B5.C06A` | 5 | Moeda R$ | REP | valor · 0 (não pagando) · VARIA · DESCONHECIDA |
| `PAGAMENTO_MINIMO_INFORMADO` | `B5.C05A` | 5 | Moeda R$ | REP | R$ ______ · Não sei. |
| `PARCELAS_RESTANTES` | `B5.C03` | 5 | Número | REP | ___ parcelas · Não sei. |
| `PARCELA_CONTRATUAL` | `B5.C02` | 5 | Moeda R$ | REP | R$ ______ · Não sei. |
| `PARTICIPACAO_FAMILIAR` | `B1.12` | 1 | Seleção única | única | A = NAO_APLICAVEL · B = ALINHADA · C = PARCIALMENTE_ALINHADA · D = ALINHAMENTO_NECESSARIO |
| `PERCEPCAO_FECHAMENTO_MES` | `B3.C02` | 3 | Seleção única | única | SOBRA · ZERO · FALTA · VARIA · NAO_SEI |
| `PERIODICIDADE_TAXA` | `B5.D01B` | 5 | Seleção única | REP | MENSAL · ANUAL · OUTRA · NAO_SEI |
| `PESO_EMOCIONAL` | `B5.H01` | 5 | Escala 0–10 | REP | 0 = praticamente não me incomoda. · 10 = é uma das dívidas que mais me preocupa ou desgasta. |
| `PLANO_EMERGENCIA` | `B12.11` | 12 | Seleção única | única | SIM · AJUSTAR · NAO |
| `PLANO_RESPOSTA_RECAIDA` | `B12.15` | 12 | Seleção única | única | ACEITA · AJUSTAR (→ texto curto OPT) · RECUSA |
| `PORTABILIDADE_CONSULTADA` | `B5.G03` | 5 | Seleção única | REP | SIM · NAO · NAO_SEI |
| `POSSIBILIDADE_SUBSTITUICAO` | `B4.V08` | 4 | Seleção única | REP | SIM · TALVEZ · NAO · NAO_APLICA |
| `POSSIBILIDADE_VENDA_IMOVEL` | `B4.I08` | 4 | Seleção única | REP | NAO · EXTREMO · TALVEZ · SIM · JA_PRETENDE |
| `POSSIBILIDADE_VENDA_OUTRO_ATIVO` | `B4.O08` | 4 | Seleção única | REP | NAO · EXTREMO · TALVEZ · SIM · JA_PRETENDE |
| `POSSIBILIDADE_VENDA_VEICULO` | `B4.V07` | 4 | Seleção única | REP | NAO · EXTREMO · TALVEZ · SIM · JA_PRETENDE |
| `POSSUI_CET` | `B5.D03` | 5 | Seleção única | REP | SIM · NAO · NAO_SEI |
| `POSSUI_GARANTIA` | `B5.F01` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `POSSUI_PAGAMENTO_MINIMO` | `B5.C05` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `POSSUI_PARCELA_DEFINIDA` | `B5.C01` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `PREFERENCIA_METODO` | `B9.05` | 9 | Seleção única | única | A = AVALANCHE · B = BOLA_DE_NEVE · C = HIBRIDO · D = SEM_PREFERENCIA |
| `PREFERENCIA_QUITACAO` | `B5.H04` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `PROPOSTA_ATUAL` | `B5.G01` | 5 | Seleção única | REP | SIM · NAO · EXPIRADA · NAO_SEI |
| `PROPOSTA_CET` | `B7.11` | 7 | Sim / Não / Não sei | única | Sim → ____ % + periodicidade · Não · Não sei |
| `PROPOSTA_CUSTOS_ADICIONAIS` | `B7.14` | 7 | Sim / Não / Não sei | única | Sim → tipo + valor R$ · Não · Não sei |
| `PROPOSTA_CUSTO_TOTAL` | `B7.12` | 7 | Sim / Não / Não sei | única | Sim → R$ ______ · Não · Não sei |
| `PROPOSTA_DESCONTO` | `B7.13A` | 7 | Seleção única | única | R$ ______ · ____ % · O credor informou apenas que existe desconto, sem detalhar. · Não sei. |
| `PROPOSTA_DESCONTO_EXISTE` | `B7.13` | 7 | Sim / Não / Não sei | única | Sim · Não · Não sei |
| `PROPOSTA_ENTRADA` | `B7.06` | 7 | Sim / Não / Não sei | única | Sim → R$ ______ · Não · Não sei |
| `PROPOSTA_PARCELA` | `B7.07` | 7 | Moeda R$ | única | valor · A_VISTA · DESCONHECIDA |
| `PROPOSTA_PRAZO` | `B7.09` | 7 | Seleção única | única | Não · Sim → informar prazo (meses) · Não sei |
| `PROPOSTA_QTD_PARCELAS` | `B7.08` | 7 | Número | única | ___ parcelas · Não sei |
| `PROPOSTA_SEGURO` | `B7.S01` | 7 | Seleção única | única | MANTEM · RETIRA · NOVO · NAO_SEI |
| `PROPOSTA_TAXA` | `B7.10` | 7 | Sim / Não / Não sei | única | Sim → ____ % + periodicidade (ao mês / ao ano) · Não · Não sei |
| `QUALIDADE_TAXA_INFORMADA` | `B5.D01` | 5 | Seleção única | REP | CONFIRMADA · ESTIMADA · DESCONHECIDA |
| `QUALIDADE_VALOR_DESPESA` | `B3.DF04` | 3 | Seleção única | REP | CONFIRMADA · ESTIMADA · DESCONHECIDA Parte C — Despesas não mensais |
| `QUALIDADE_VALOR_ORIGINAL` | `B5.B01` | 5 | Seleção única | REP | CONFIRMADA · ESTIMADA · DESCONHECIDA |
| `QUANTIDADE_DIVIDAS_DECLARADA_INICIAL` | `B5.00` | 5 | Número | única | inteiro · DESCONHECIDA |
| `QUITACAO_CONSULTADA` | `B5.B05` | 5 | Seleção única | REP | SIM · NAO · EXPIROU · NAO_SEI |
| `RECURSOS_EXTRAORDINARIOS_EXISTE` | `B3.05` | 3 | Seleção única | única | SIM · TALVEZ · NAO |
| `REGIME_MARGEM` | `B3.S02` | 3 | Checklist (múltipla) | única | FEDERAL · ESTADUAL · MUNICIPAL · MILITAR · APOSENTADO_PUBLICO · INSS · OUTRO (permitir mais de um vínculo) |
| `REGISTRO_GASTOS` | `B2.01` | 2 | Seleção única | única | TUDO · MAIORIA · PARTE · RARAMENTE · NAO_REGISTRA |
| `REGRA_AJUDA_TERCEIROS` | `B12.12A` | 12 | Seleção única | única | Definir um teto mensal. · Não utilizar cartão, empréstimo ou limite para ajudar terceiros. · Ajudar apenas quando houver dinheiro disponível no orçame |
| `REGRA_AJUDA_TERCEIROS_EXISTE` | `B12.12` | 12 | Seleção única | única | Sim. · Não considero necessário. · Quero avaliar. |
| `REGRA_CARTAO` | `B12.08` | 12 | Seleção única | única | Não utilizar cartão por enquanto. · Usar somente para gastos planejados. · Usar apenas quando o dinheiro para pagar a compra já estiver reservado. · R |
| `REGRA_ESPERA` | `B12.07` | 12 | Seleção única | única | 24H · 48H · 7D · OUTRA (→ texto curto OPT) · NENHUMA |
| `REGRA_PARCELAMENTO` | `B12.09` | 12 | Seleção única | única | A = SEM_PARCELAMENTO · B = SO_PLANEJADO · C = NAO_PARA_CABER · D = OUTRA (→ texto curto OPT) |
| `REGRA_PESSOAL` | `B12.16` · `B12.16A` | 12 | Seleção única | única | “Eu não contrato crédito para pagar despesas recorrentes do meu mês.” · “Se o orçamento não comporta a compra, a parcela também não cabe.” · “Parcela  |
| `RENDA_BRUTA_VINCULO` | `B3.S04` | 3 | Moeda R$ | única | R$ ______ · Não sei. |
| `RENDA_EXTRA_RECORRENTE_POTENCIAL` | `B3.06B` | 3 | Moeda R$ | única | R$ ______ · Ainda não sei. |
| `RENDA_EXTRA_RECORRENTE_POTENCIAL_EXISTE` | `B3.06` | 3 | Seleção única | única | CONCRETA · INDEFINIDA · NAO |
| `RENDA_IMOVEL` | `B4.I05A` | 4 | Moeda R$ | REP | R$ ______ · Não sei. |
| `RENDA_OUTRO_ATIVO` | `B4.O05` | 4 | Sim / Não | REP | Sim · Não → se Sim: R$ ______ por mês |
| `RENDA_PRINCIPAL` | `B3.01` | 3 | Moeda R$ | única | R$ ______ · Minha renda é variável e não consigo representá-la por um único valor. |
| `RENDA_RECORRENTE_ADICIONAL` | `B3.03B` | 3 | Moeda R$ | REP | R$ ______ · Não sei. |
| `RENDA_RECORRENTE_ADICIONAL_EXISTE` | `B3.03` | 3 | Sim / Não | única | SIM · NAO |
| `RENDA_VARIAVEL_MEDIA_HISTORICA` | `B3.02A` | 3 | Moeda R$ | única | R$ ______ · Não consigo estimar. |
| `RENDA_VARIAVEL_PISO_DECLARADO` | `B3.02B` | 3 | Moeda R$ | única | R$ ______ · Não consigo estimar. |
| `RESERVA_EXISTE` | `B4.02` | 4 | Seleção única | única | SIM · INFORMAL · NAO |
| `RESERVA_MOBILIZAVEL` | `B4.03A` | 4 | Moeda R$ | única | R$ ______ · Prefiro decidir somente depois de ver a análise. · Não sei. |
| `RESERVA_TOTAL` | `B4.02A` | 4 | Moeda R$ | única | R$ ______ · Não sei. |
| `RESPOSTA_EMERGENCIA` | `B12.10` | 12 | Seleção única | única | RESERVA · RENDA · CORTE · CARTAO · EMPRESTIMO · TERCEIRO · NAO_SEI |
| `RESULTADO_ACAO_ECONOMIA` | `B11.03-ECO` | 11 | Seleção única | única | Sim, integralmente. · Sim, parcialmente. · Não. |
| `RESULTADO_ACAO_INFORMACAO` | `B11.03-INF` | 11 | Seleção única | única | Sim. · Parcialmente. · Não. |
| `RESULTADO_ACAO_RENEGOCIACAO` | `B11.03-REN` | 11 | Seleção única | única | Sim. · Não. · Ainda estou aguardando. |
| `RESULTADO_ACAO_TROCA` | `B11.03-TRO` | 11 | Seleção única | única | Sim. · Não. · Ainda estou aguardando. |
| `RESULTADO_DIVERGENTE` | `B11.04` | 11 | Sim / Não / Não sei | única | Sim · Não · Não sei |
| `RESULTADO_RENEGOCIACAO_ANTERIOR` | `B7.03` | 7 | Seleção única | única | RECUSEI · EXECUTADA · SEM_OFERTA · NAO_CONCLUIDA · EXPIROU · OUTRO · NAO_SEI |
| `REVISAO_SEMANAL` | `B2.12` | 2 | Seleção única | única | SEMPRE · MAIORIA · ALGUMAS · RARAMENTE · NUNCA |
| `RISCO_IMPULSO` | `B2.11` | 2 | Seleção única | única | NENHUMA · UMA · DUAS_TRES · QUATRO_MAIS · NAO_SEI |
| `RISCO_PRINCIPAL_RECAIDA` | `B12.03` | 12 | Seleção única | única | CARTAO · PARCELAMENTO · LIMITE · EMERGENCIA · AJUDA_FAMILIAR · FALTA_CONTROLE · RENDA_INSUFICIENTE · IMPULSO · PADRAO_VIDA · OUTRO · NAO_IDENTIFICA |
| `SALDO_DEVEDOR_ATUAL` | `B5.B03` · `B11.Q04A` | 5 | Moeda R$ | REP | R$ ______ · Não sei. |
| `SALDO_FINANCIAMENTO_IMOVEL` | `B4.I04A` | 4 | Moeda R$ | REP | R$ ______ · Não sei. |
| `SALDO_FINANCIAMENTO_VEICULO` | `B4.V04A` | 4 | Moeda R$ | REP | R$ ______ · Não sei. |
| `SALDO_PASSIVO_VINCULADO` | `B4.O04A` | 4 | Moeda R$ | REP | R$ ______ · Não sei. |
| `SEGURO_INCLUIDO_PARCELA` | `B5.D05B` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `SEGURO_PRESTAMISTA` | `B5.D05` | 5 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `SINAIS_RECAIDA` | `B12.14` | 12 | Checklist (múltipla) | única | Usar cartão para despesas básicas por falta de dinheiro. · Voltar a parcelar repetidamente. · Parar de registrar os gastos. · Entrar no cheque especia |
| `SOBRA_PERCEBIDA` | `B3.C02A` | 3 | Moeda R$ | única | R$ ______ |
| `STATUS_DIVIDA` | `B5.A04` | 5 | Seleção única | REP | ATIVA · EM_ACORDO · COBRANCA_SEM_PAGAMENTO · QUITADA_A_CONFIRMAR · OUTRA |
| `STATUS_PROCESSO_RENEGOCIACAO` | `B7.EX01` | 7 | Seleção única | única | Sim = EXECUTADA · Não = ENCERRADA_SEM_ACORDO · Ainda não = mantém estado |
| `STATUS_QUITACAO_REAL` | `B11.Q01` | 11 | Seleção única | única | Sim = QUITADA · Ainda não = NAO · Acredito = A_CONFIRMAR |
| `STATUS_RECURSO_EXTRAORDINARIO` | `B11.RE01` | 11 | Seleção única | única | RECEBIDO · PENDENTE · CANCELADO · ALTERADO |
| `STATUS_TROCA` | `B8.00` · `B8.EX01` | 8 | Seleção única | única | Sim = PROPOSTA_RECEBIDA · Não = AGUARDANDO_PROPOSTA (gera ação) · Consultando = PROPOSTA_INCOMPLETA |
| `SUBSTITUICAO_REDUZ_CUSTO` | `B4.V08B` | 4 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `TAXA_INFORMADA` | `B5.D01A` | 5 | Percentual % | REP | ____ % |
| `TEMPO_ATRASO` | `B5.E02` | 5 | Seleção única | REP | Menos de 30 dias · 1–3 meses · 4–6 meses · 7–12 meses · Mais de 12 meses · Não sei |
| `TIPOS_DIVIDA_DECLARADOS` | `B5.00A` | 5 | Checklist (múltipla) | única | Empréstimo consignado · Empréstimo pessoal · Financiamento de veículo · Financiamento imobiliário · Cartão com saldo rotativo · Parcelamento de fatura |
| `TIPO_DESPESA_NAO_MENSAL` | `B3.NM02A` | 3 | Seleção única | REP | IPTU · IPVA/licenciamento · Matrícula · Material escolar · Seguro anual · Manutenção programada · Imposto/taxa · Assinatura anual · Outra |
| `TIPO_DIVIDA` | `B5.A02` | 5 | Seleção única | REP | CONSIGNADO · PESSOAL · FIN_VEICULO · FIN_IMOBILIARIO · CARTAO_ROTATIVO · CARTAO_PARCELADO · CHEQUE_ESPECIAL · PARCELAMENTO_COMPRA · TRIBUTARIA · PESSO |
| `TIPO_GARANTIA` | `B5.F02` | 5 | Seleção única | REP | Imóvel · Veículo · Outro bem · Aval/fiança · Saldo/aplicação financeira · Outra · Não sei |
| `TIPO_IMOVEL` | `B4.I02` | 4 | Seleção única | REP | Casa/apartamento onde moro · Outro imóvel residencial · Imóvel alugado · Terreno · Imóvel comercial · Imóvel de lazer · Outro |
| `TIPO_INVESTIMENTO` | `B4.04A` | 4 | Seleção única | REP | Poupança · CDB/RDB · Tesouro Direto · LCI/LCA · Fundo de renda fixa · Previdência privada · Fundo de investimento · Ações · ETF · Fundo imobiliário ·  |
| `TIPO_MARGEM` | `B3.S06A` | 3 | Seleção única | REP | EMPRESTIMO · CARTAO_CONSIGNADO · CARTAO_BENEFICIO · OUTRA_DO_REGIME. SYS: MARGEM_ID por ficha. |
| `TIPO_OBRIGACAO_FUTURA` | `B1.06A` | 1 | Seleção única | REP | Imposto ou obrigação anual · Educação · Saúde · Moradia · Veículo · Despesa familiar · Mudança · Viagem necessária · Outra |
| `TIPO_OUTRO_ATIVO` | `B4.O02` | 4 | Seleção única | REP | Equipamento profissional · Joias/objetos de valor · Participação societária · Embarcação · Bem de coleção · Outro |
| `TIPO_RECURSO_EXTRAORDINARIO` | `B3.05A` | 3 | Seleção única | REP | 13º salário · Férias/abono · Bônus ou gratificação · Restituição de imposto · Precatório/RPV · Venda já prevista · Valor a receber de terceiro · Outro |
| `TIPO_RENDA` | `B3.02` | 3 | Seleção única | única | A = FIXA · B = RELATIVAMENTE_ESTAVEL · C = VARIAVEL |
| `TIPO_RENDA_ADICIONAL` | `B3.03A` | 3 | Seleção única | REP | Segundo trabalho ou vínculo · Trabalho autônomo/freelance · Aluguel · Pensão recebida · Benefício · Comissão · Renda de negócio · Outra renda recorren |
| `TIPO_RENDA_ADICIONAL_ESTABILIDADE` | `B3.03C` | 3 | Seleção única | REP | FIXA · RELATIVAMENTE_ESTAVEL · VARIAVEL (guardar como qualidade) |
| `TIPO_TROCA` | `B8.01` | 8 | Seleção única | única | A = A_PORTABILIDADE_VERDADEIRA · B = B_CREDITO_SUBSTITUTIVO · C = C_DINHEIRO_NOVO · D = NAO_SEI |
| `TIPO_VEICULO` | `B4.V02` | 4 | Seleção única | REP | Carro · Moto · Utilitário · Outro |
| `TOLERANCIA_ESPERA` | `B9.01` | 9 | Escala 0–10 | única | 0 = Eu teria muita dificuldade. · 10 = Consigo esperar se souber que a estratégia faz sentido. |
| `TROCA_DEPENDE_DE_OUTRA` | `B8.P01` | 8 | Sim / Não / Não sei | única | Sim · Não · Não sei |
| `URGENCIA_PERCEBIDA` | `B5.H03` | 5 | Escala 0–10 | REP | URGENCIA_PERCEBIDA = inteiro 0–10 |
| `USO_CREDITO_PREVISTO` | `B1.08` | 1 | Checklist (múltipla) | única | DESPESAS_MES · CONSUMO · EMERGENCIA · OUTRA_DIVIDA · REESTRUTURACAO · INDEFINIDO · NAO_PRETENDE |
| `VALOR_A_LIBERAR_MARGEM` | `B3.S07A` | 3 | Moeda R$ | única | R$ ______ · Não sei. |
| `VALOR_DESPESA` | `B3.DF01` | 3 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VALOR_DESPESA_NAO_MENSAL` | `B3.NM02B` | 3 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VALOR_ESTIMADO_ATIVO` | `B4.04B` · `B4.O03` | 4 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VALOR_FLUXO_LIBERADO` | `B11.Q06` | 11 | Seleção única | única | X · outro valor · 0 · DESCONHECIDA |
| `VALOR_GASTOS_FANTASMAS` | `B2.10` | 2 | Moeda R$ | única | R$ ______ · Ainda não sei quanto. |
| `VALOR_GASTOS_NAO_IDENTIFICADOS` | `B2.08` | 2 | Moeda R$ | única | R$ ______ · Não consigo estimar. |
| `VALOR_IMOVEL` | `B4.I03` | 4 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VALOR_JA_PAGO` | `B5.B02` | 5 | Moeda R$ | REP | R$ ______ · Tenho apenas uma estimativa. · Não sei. |
| `VALOR_LIVRE_MARGEM` | `B3.S06D` | 3 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VALOR_NOVA_DIVIDA` | `B1.04` | 1 | Moeda R$ | única | R$ ______ · Ainda não sei o valor. |
| `VALOR_NOVA_OPERACAO` | `B8.03` | 8 | Moeda R$ | única | R$ ______ · Não sei. |
| `VALOR_OBRIGACAO_FUTURA` | `B1.06B` | 1 | Moeda R$ | REP | R$ ______ · Ainda não sei. |
| `VALOR_PAGO_QUITACAO` | `B11.Q03` | 11 | Moeda R$ | única | R$ ______ · Não sei com segurança. |
| `VALOR_QUITACAO_HOJE` | `B5.B05A` | 5 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VALOR_RECURSO_EXTRAORDINARIO` | `B3.05B` · `B11.RE02` | 3 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VALOR_SUBSTITUICAO` | `B8.04` | 8 | Moeda R$ | única | valor · = VALOR_NOVA_OPERACAO · DESCONHECIDA |
| `VALOR_TOTAL_MARGEM` | `B3.S06B` | 3 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VALOR_UTILIZADO_MARGEM` | `B3.S06C` | 3 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VALOR_VEICULO` | `B4.V03` | 4 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VALOR_VEICULO_SUBSTITUTO` | `B4.V08A` | 4 | Moeda R$ | REP | R$ ______ · Não sei. |
| `VEICULO_ESSENCIAL` | `B4.V06` | 4 | Seleção única | REP | ESSENCIAL · IMPORTANTE · NAO_ESSENCIAL |
| `VEICULO_EXISTE` | `B4.V01` | 4 | Sim / Não | única | Sim · Não |
| `VEICULO_POSSUI_PASSIVO` | `B4.V04` | 4 | Sim / Não / Não sei | REP | Sim · Não · Não sei |
| `VINCULO_CONSIGNAVEL` | `B3.S01` | 3 | Seleção única | única | SIM · NAO · NAO_SEI |

<a id="sec-13"></a>

## 13. Errata — o que mudou dos PDFs

Oito correções aplicadas. Rastreabilidade completa: para cada uma, a redação revogada, a vigente, a origem da decisão e o motivo.

### `E-01` — Tipo e alternativas · B5.H03

| | |
|---|---|
| ❌ Revogado | Seleção única: Baixa · Média · Alta · Muito alta · Não sei |
| ✅ Vigente v1.0.1 | Escala 0–10, com âncoras "0 = pode esperar" e "10 = máxima urgência". URGENCIA_PERCEBIDA = inteiro 0–10. |
| Origem | Seção 23 · Resolução V1 |

O cartão e a linha da Tabela Mestra do PDF mantinham a escala qualitativa já revogada pela própria Seção 23.

### `E-02` — PERCENTUAL_LIMITE · Q44 · sub-bloco Servidor

| | |
|---|---|
| ❌ Revogado | Parâmetro [P] de calibração: VALOR_TOTAL_MARGEM = RENDA_BRUTA × PERCENTUAL_LIMITE |
| ✅ Vigente v1.0.1 | Metadado regulatório externo, não decisório e não bloqueante. O dado canônico é o valor de margem declarado pela fonte pagadora, por VINCULO_ID e MARGEM_ID. |
| Origem | Devolutiva do especialista · item 2 |

Não existe tabela legal universal confiável por regime. Validação obrigatória passa a ser interna: VALOR_UTILIZADO_MARGEM ≤ VALOR_TOTAL_MARGEM.

### `E-03` — Tabela de parâmetros · Matriz §19

| | |
|---|---|
| ❌ Revogado | Oito parâmetros exibidos como "—" / A_CALIBRAR |
| ✅ Vigente v1.0.1 | Valores fechados conforme D.3 (ver aba PARAMETROS) |
| Origem | D.3 |

A §19 e a D.3 coexistiam no PDF com valores conflitantes. Nesta especificação só existe a redação vigente.

### `E-04` — ORDEM_HIBRIDA · Matriz · Bloco 9

| | |
|---|---|
| ❌ Revogado | "Híbrido deve especificar regra" — sem algoritmo de construção |
| ✅ Vigente v1.0.1 | Regra determinística em seis etapas (ver aba ENGINE, regras H-01 a H-08) |
| Origem | Devolutiva do especialista · item 3 |

A Matriz mandava simular CENARIO_HIBRIDO sem definir como construí-lo. Lacuna real, agora fechada.

### `E-05` — Resíduo do ataque · Matriz · engine

| | |
|---|---|
| ❌ Revogado | Convenção não escrita; os gabaritos originais assumiam descarte |
| ✅ Vigente v1.0.1 | Resíduo cascateia para a próxima dívida elegível no mesmo mês (REGRA_RESIDUO_ATAQUE = CASCATA) |
| Origem | Devolutiva final §2 |

O descarte fazia dinheiro do usuário desaparecer e produzia cenário alternativo dominando a Avalanche em prazo.

### `E-06` — Gatilho de recálculo · Matriz · engine

| | |
|---|---|
| ❌ Revogado | Ambíguo entre "a cada quitação" e "no encerramento de todo mês" |
| ✅ Vigente v1.0.1 | Evento-dirigido: quitação de qualquer dívida ou EVENTO_RECALCULO externo. Passagem de mês nunca recalcula. |
| Origem | Devolutiva final §1 · Confirmação A.1 |

Testado em 400 carteiras: a leitura mensal divergia da event-driven em 8,5% dos casos, chegando a trocar o método recomendado.

### `E-07` — Valores numéricos · Gabarito C

| | |
|---|---|
| ❌ Revogado | Avalanche 7m/23.781,46 · Bola de Neve 6m/24.610,92 · Híbrido 7m/24.238,74 |
| ✅ Vigente v1.0.1 | Avalanche 6m/23719.46 · Bola de Neve 6m/24463.97 · Híbrido 6m/24107.20 |
| Origem | Devolutiva final §10 |

Consequência de E-05. A conclusão metodológica não mudou: D* = D003 e METODO_RECOMENDADO_PIQ = HIBRIDO.

### `E-08` — Gabaritos de casos-limite · §25

| | |
|---|---|
| ❌ Revogado | Exigidos, porém inexistentes |
| ✅ Vigente v1.0.1 | Cinco invariantes definidos (GAB-01 a GAB-05, aba GABARITOS) |
| Origem | Devolutiva final · bloco B |

Sem eles, "zero erro conhecido de dupla contagem" não era verificável.

<a id="sec-14"></a>

## 14. Pendências

O que segue aberto e **não pode ser decidido pelo desenvolvedor**.

| Item | Tema | Situação | Responsável |
|---|---|---|---|
| [`PEND-01`](#pend-01) | Jurídico / LGPD | ABERTO — bloqueia piloto | Jurídico + especialista |
| [`PEND-02`](#pend-02) | P_CAIXA_VS_ESTRUTURAL | ABERTO — não bloqueia | Especialista |
| [`PEND-03`](#pend-03) | P_AUTOPERCEPCAO | ABERTO — não bloqueia | Especialista |
| [`PEND-04`](#pend-04) | Regra D.4 | VERIFICAR | Especialista |
| [`PEND-05`](#pend-05) | Arquitetura de coleta | DECISÃO DE PRODUTO | Produto + desenvolvimento |
| [`PEND-06`](#pend-06) | Fila de revisão humana | A IMPLEMENTAR | Produto |

<a id="pend-01"></a>

### `PEND-01` — Jurídico / LGPD

**Situação:** ABERTO — bloqueia piloto

Texto de consentimento, política de privacidade, prazo de retenção, procedimento de exclusão e disclaimer não foram redigidos.

*Origem:* Matriz §26 e tela de consentimento reservam o ponto e travam expressamente o piloto com usuários reais.

**Encaminhamento.** Não bloqueia especificar nem programar. Bloqueia coletar dado de pessoa real. Decidir também onde os dados residem e quem acessa a base.

<a id="pend-02"></a>

### `PEND-02` — P_CAIXA_VS_ESTRUTURAL

**Situação:** ABERTO — não bloqueia

Corte de materialidade do GAP_CAIXA_VS_ESTRUTURAL segue sem valor.

*Origem:* Matriz §19 · A_CALIBRAR

**Encaminhamento.** Motor pode rodar com o parâmetro nomeado e valor provisório, desde que registrado como A_CALIBRAR na aba PARAMETROS.

<a id="pend-03"></a>

### `PEND-03` — P_AUTOPERCEPCAO

**Situação:** ABERTO — não bloqueia

Regra de divergência relevante entre autopercepção e cálculo segue sem definição.

*Origem:* Matriz §19 · A_CALIBRAR

**Encaminhamento.** Idem PEND-02.

<a id="pend-04"></a>

### `PEND-04` — Regra D.4

**Situação:** VERIFICAR

P_LIMIAR_RISCO_RECAIDA e P_LIMIAR_RISCO_COMPORTAMENTAL_GERAL remetem à regra D.4.

*Origem:* D.3

**Encaminhamento.** Confirmar que a redação de D.4 está disponível ao desenvolvedor na forma determinística. Se não estiver, é bloqueio de motor.

<a id="pend-05"></a>

### `PEND-05` — Arquitetura de coleta

**Situação:** DECISÃO DE PRODUTO

Google Forms puro não comporta ficha repetível (115 perguntas REP), condicional composta, texto dinâmico nem a etapa de motor entre coletas.

*Origem:* Análise de viabilidade

**Encaminhamento.** Recomendação: Sheets como base, Apps Script Web App para Bloco 5 e para tudo com texto dinâmico, motor em .gs lendo a aba PARAMETROS, relatório via template Docs → PDF.

<a id="pend-06"></a>

### `PEND-06` — Fila de revisão humana

**Situação:** A IMPLEMENTAR

A §24 exige revisão humana de 100% dos relatórios no piloto.

*Origem:* Matriz §24

**Encaminhamento.** Precisa existir como etapa de processo antes do primeiro envio a usuário real.

> **PEND-01 — atenção.** O jurídico não bloqueia especificar nem programar, mas bloqueia coletar dado de pessoa real. Se ficar para o fim, o projeto chega com o sistema pronto e sem poder ligar. Deve correr em paralelo, fora do caminho crítico.

<a id="sec-15"></a>

## 15. Arquitetura de implementação recomendada

A metodologia não pode ser mutilada pela tecnologia. As restrições abaixo decorrem da especificação, não de preferência de ferramenta.

### 15.1. Por que Google Forms puro não comporta o PIQ

| Restrição | Consequência |
|---|---|
| Ficha repetível | 115 das 291 perguntas são REP, aplicadas uma vez por dívida, vínculo, despesa ou ativo. O Forms não repete blocos. |
| Condicional composta | Várias perguntas dependem de mais de uma variável, de blocos diferentes. O Forms ramifica apenas por resposta única de seção. |
| Texto dinâmico | Cartões exigem interpolar valores já coletados, como o identificador da dívida ou totais declarados. |
| Validação entre campos | Por exemplo `VALOR_UTILIZADO_MARGEM ≤ VALOR_TOTAL_MARGEM`, por `MARGEM_ID`. |
| Motor entre coletas | O Bloco 6 roda entre a Etapa B e a Etapa D, o que obriga a múltiplos formulários encadeados de qualquer forma. |

### 15.2. Desenho recomendado

- **Google Sheets como base de dados**, com abas separadas por escopo: respostas, dívidas, vínculos, margens, despesas, ativos, ações, eventos e auditoria.
- **Aba PARAMETROS** replicando a seção 8. O motor lê os valores em execução; nenhum número ajustável no código.
- **Aba SPEC como fonte do renderizador**: a interface é gerada a partir dos registros da seção 11, não codificada pergunta a pergunta.
- **Apps Script Web App (HTML Service)** para o Bloco 5 e para tudo que exija ficha repetível, texto dinâmico ou validação entre campos.
- **Motor em Apps Script puro**, uma função por camada, na ordem, sem pular etapas do ciclo mensal.
- **Relatório** gerado a partir de template do Google Docs com placeholders, exportado em PDF.
- **Fila de revisão humana obrigatória**: no piloto, 100% dos relatórios revisados antes do envio.

### 15.3. Ordem de construção sugerida

1. Parâmetros e especificação de coleta (seções 8 e 11 — já prontas).
2. Motor, validado contra os três gabaritos numéricos e os cinco invariantes.
3. Camada de coleta, renderizada a partir da seção 11.
4. Relatório e fila de revisão.

Motor errado com formulário bonito é pior do que o contrário. A classificação de erros da §25 — TEXTO, PARÂMETRO, DADO, REGRA, CÁLCULO, UX — só funciona se o motor já existir para ser testado.

---

## Declaração final

As regras deste documento constituem a especificação definitiva do PIQ v1.0.1 para: permanência do alvo, gatilhos de recálculo, reaproveitamento do resíduo do ataque, incorporação do fluxo liberado, comportamento da Avalanche, da Bola de Neve e do Híbrido, publicação da `ORDEM_QUITACAO`, versionamento da ordem, conteúdo e domínio das 291 perguntas, e valores de todos os parâmetros.

Nenhuma dessas decisões fica a critério do desenvolvedor. Qualquer alteração futura deverá ocorrer por nova versão formal da especificação.

*Os valores do Gabarito C foram recomputados mês a mês, com precisão decimal integral, a partir das regras aqui especificadas.*
