# Spec — Motor de Cálculo do PIQ

| Campo    | Valor                                                       |
| -------- | ----------------------------------------------------------- |
| Slug     | `motor-calculo`                                             |
| Status   | `em revisão`                                                |
| Autor    | virtushold@gmail.com                                        |
| Data     | 2026-09-10 (Rodada 4, fatia 4C — ligação de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (fatia 4B) e da classificação de ativos/investimentos (fatia 4A) em `calcular_diagnostico`, fazendo `ATAQUE_IMEDIATO_RECOMENDADO` sair do placeholder `dinheiro(0)` — **última fatia do documento do especialista**, fecha `OQ-29` por completo · fatia 4B (necessidade financeira imediata, `RF-61`–`RF-65`) concluída e verificada 2026-09-09 · fatia 4A (classificação de investimentos/ativos e valor líquido realizável, `RF-53`–`RF-60`) concluída e verificada 2026-09-09 · Rodada 3 em 2026-09-07 · Rodada 2 em 2026-09-04 · backlog original 78/78 concluído em 2026-09-01/02) |
| Fonte    | [`specs/piq-app-spec.md`](piq-app-spec.md) — Matriz Canônica v1.0.1 |
| Fonte    | [`specs/piq-definicoes-engine.md`](piq-definicoes-engine.md) — Fechamento das Definições Remanescentes da Engine |
| Fonte    | Devolutiva do especialista de 2026-09-01 — fecha `OQ-01` a `OQ-08` |
| Fonte    | [`specs/motor-calculo.discovery.md`](motor-calculo.discovery.md) — Rodada 2, pedido do slug `app-aluno` |
| Fonte    | [`specs/app-aluno.spec.md`](app-aluno.spec.md) §10 — `OQ-10`, `OQ-13`, `OQ-14`, `OQ-15`, `OQ-17`, `OQ-18` (decisões do especialista, `respondida`) |
| Fonte    | Documento canônico *"PIQ v1.0.1 — Definição Canônica de `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO`"*, entregue em 2026-09-07 — transcrito na íntegra em §13 (Rodada 3) |
| Fonte    | Documento canônico *"PIQ v1.0.1 — Fechamento Canônico — Necessidade Financeira Imediata e Classificação de Ativos"*, entregue em 2026-09-09 — transcrito na íntegra em §14 (Rodada 4) |

> **Esta spec não substitui as fontes — ela as endereça.** Cada requisito aponta
> para os IDs de regra e as seções que o definem. Nenhuma regra é parafraseada
> aqui.
>
> **Ordem de precedência, do mais forte ao mais fraco:**
>
> 1. **Fechamento das Definições Remanescentes da Engine** — para os oito temas
>    que trata, prevalece sobre qualquer redação anterior conflitante.
> 2. **Matriz Canônica v1.0.1** — soberana para todos os demais temas.
> 3. **Seção 11 desta spec** — apenas para o que a devolutiva de 2026-09-01
>    fechou e ainda não foi consolidado em documento normativo próprio.

---

## 1. Overview

O motor é a peça que transforma o retrato financeiro de uma pessoa endividada em
um plano de quitação: quanto sobra por mês para atacar dívidas, qual dívida
atacar primeiro, em que ordem as demais caem, quanto tempo leva e quanto custa.
Ele calcula os três métodos previstos — Avalanche, Bola de Neve e Híbrido — e
recomenda um, com justificativa por posição.

É a primeira coisa a ser construída. A seção 15.3 da canônica é explícita quanto
à ordem, e a razão é verificabilidade: *"motor errado com formulário bonito é
pior do que o contrário"*. O motor tem gabaritos numéricos fechados; a interface
não tem. Enquanto o motor não reproduzir os três gabaritos e satisfazer os cinco
invariantes, nada construído em cima dele pode ser confiável.

O motor não coleta dado e não desenha relatório. Ele recebe um estado
financeiro completo e devolve um plano carimbado com versão.

## 2. Functional Requirements

> **Rodada 2 (2026-09-04) — ver seção 12.** `RF-28` a `RF-35` estendem o
> contrato de saída de `engine/gates.py::AcaoRequerida` e
> `engine/diagnostico.py::Diagnostico` a pedido do slug `app-aluno`
> (`T-77`/`T-78`/`T-79` bloqueadas). A decisão de metodologia já foi tomada
> pelo especialista e está registrada em `specs/app-aluno.spec.md` §10
> (`OQ-10`, `OQ-13`, `OQ-14`, `OQ-15`, `OQ-17`, `OQ-18`, todas `respondida`).
> Este slug apenas transcreve para código e revalida gabaritos/invariantes.

| ID | Requisito | Regras / seções da canônica | Prioridade |
| --- | --- | --- | --- |
| `RF-01` | Executar o ciclo mensal canônico em 12 passos, na ordem, sem pular etapa | `M-01`..`M-12` · §2 | essencial |
| `RF-02` | Recalcular a ordem apenas por quitação confirmada de qualquer dívida ou por evento externo material — nunca por virada de mês | `R-01`..`R-05` · §3 | essencial |
| `RF-03` | Cascatear o resíduo do ataque para a próxima dívida elegível ainda no mês corrente, repetidamente, e registrar o que sobrar como `ATAQUE_NAO_UTILIZADO` | `A-01`..`A-04` · §4.1 · §11.1 | essencial |
| `RF-04` | Incorporar o fluxo liberado à capacidade somente a partir de *m+1*, sem liberação retroativa e sem dupla contagem | `F-01`..`F-03` · §4.2 · §11.7 | essencial |
| `RF-05` | Calcular o método Avalanche ordenando por `BENEFICIO_MARGINAL_AMORTIZACAO` decrescente, com alvo fixo até quitação ou evento | `O-01`..`O-03` · §5.1 · §11.1 | essencial |
| `RF-06` | Calcular o método Bola de Neve pelo menor `VALOR_RELEVANTE_PARA_QUITACAO`, com a cadeia de desempate na ordem definida | `O-04`, `O-05` · §5.2 · §11.2 | essencial |
| `RF-07` | Construir o método Híbrido pelas seis etapas determinísticas, incluindo as três tolerâncias cumulativas e o desempate lexicográfico de seis níveis | `H-01`..`H-08` · §5.3 | essencial |
| `RF-08` | Classificar cenários como `NAO_CALCULAVEL` ou `NAO_APLICAVEL` e derivar `STATUS_METODO`, acionando revisão humana quando a regra exigir | `S-01`..`S-05` · §6 | essencial |
| `RF-09` | Publicar a `ORDEM_QUITACAO` como sequência projetada, com `JUSTIFICATIVA_POSICAO` obrigatória para cada dívida | `Q-01`..`Q-05` · §7 | essencial |
| `RF-10` | Versionar a ordem por snapshot a cada quitação real ou evento de recálculo, preservando o estado anterior, a data e o motivo | `V-01`..`V-03` · §7.1 | essencial |
| `RF-11` | Tratar troca e portabilidade com `DINHEIRO_NOVO > 0` pelo cenário de substituição equivalente | `T-01`, `T-02` · `GAB-05` | importante |
| `RF-12` | Manter precisão decimal integral em todo o cálculo, arredondando apenas na exibição | `G-01`, `G-02` · §2, §10.3 | essencial |
| `RF-13` | Carregar os parâmetros ajustáveis de fonte externa em tempo de execução, sem nenhum valor escrito no código | §8 · §11.9 | essencial |
| `RF-14` | Calcular o diagnóstico financeiro e a capacidade de ataque: resultado observado, resultado estrutural, piso de capacidade, fator de segurança e as três capacidades | `GAB-A`, `GAB-B` · §11.8 | essencial |
| `RF-15` | Entrar em `MODO_ESTABILIZACAO` quando o resultado estrutural for negativo, zerando a capacidade de ataque e rebaixando o cronograma a fase condicional | `GAB-A`, `GAB-04` | essencial |
| `RF-16` | Bloquear o que depende de dado ausente, marcando `INFORMACAO_PENDENTE`, sem jamais estimar saldo, parcela ou pagamento | `GAB-02`, `GAB-03` | essencial |
| `RF-17` | Aplicar os quatro gates de elegibilidade **antes** da ordem-base, derivando `DIVIDA_STATUS_ESTRATEGICO` e `GATE_PENDENTE`, e desviando para `ORDEM_ACOES` o que exigir ação prévia | `O-04`, `H-02` · §11.3 · Definições §6, §7 | essencial |
| `RF-18` | Classificar `RISCO_RECAIDA` e `RISCO_COMPORTAMENTAL_GERAL` pela contagem de sinais da regra D.4, sem contar dado desconhecido como risco | §8 · §11.4 | essencial |
| `RF-23` | Derivar `NIVEL_CONTROLE` e `CONFIABILIDADE_DADOS` a partir das oito variáveis do Bloco 2, pelas regras determinísticas e na ordem de avaliação obrigatória | Definições §4, §5 | essencial |
| `RF-24` | Derivar `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` pela conjunção de `NECESSIDADE_VITORIA` com pelo menos um dos três sinais comportamentais | Definições §1 | essencial |
| `RF-25` | Compor o `FATOR_SEGURANCA` de forma **subtrativa**, somando as quatro reduções antes de aplicar o piso | Definições §3 | essencial |
| `RF-26` | Classificar `STATUS_FINANCEIRO` em `DEFICIT`, `EQUILIBRIO_FRAGIL` ou `CAPACIDADE_POSITIVA`, sem que o `PISO_CAPACIDADE` altere a capacidade | Definições §8 | essencial |
| `RF-27` | Respeitar a ordem de derivação das variáveis do motor, sem a qual o resultado é silenciosamente errado | §11.10 | essencial |
| `RF-19` | Eleger `CENARIO_ECONOMICAMENTE_SUPERIOR` pelo menor custo, com empate material de 1% desempatado pelo menor `PRAZO_TOTAL` | §8 `P_DIFERENCA_ECONOMICA_MATERIAL` · §11.5 | essencial |
| `RF-20` | Avaliar `ECONOMICAMENTE_PROXIMO` por custo **e** prazo cumulativamente, contra o cenário economicamente superior | `S-04`, `S-05` · §11.5 | essencial |
| `RF-21` | Rebaixar a ordem a `PROVISORIA` e usar o fallback por taxa quando a simulação marginal da Avalanche for impossível por insuficiência de dados | `S-01` · §11.1 | importante |
| `RF-22` | Manter fora da projeção-base todo evento futuro apenas provável, tratando nova dívida prevista como insumo de risco e de alerta, nunca como dívida do inventário | `R-01` · §11.6 | essencial |
| `RF-28` | Adicionar `AcaoRequerida.ACAO_ID: str` como identidade estável da ação, idêntica entre snapshots enquanto a ação for a mesma | `app-aluno.spec.md` §10 `OQ-10` · §12.1 | essencial |
| `RF-29` | Adicionar `AcaoRequerida.TIPO_ACAO: str` com domínio fechado `{"INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"}` | `app-aluno.spec.md` §10 `OQ-13` · §12.1 | essencial |
| `RF-30` | Derivar `TIPO_ACAO` a partir de `GATE_PENDENTE` (nunca de `gate_origem`), pelo mapeamento Gate 1→`INFORMACAO`, Gate 3+`RENEGOCIACAO_PENDENTE`→`RENEGOCIACAO`, Gate 3+`TROCA_PENDENTE`→`TROCA`, fora do fluxo de gates→`ECONOMIA` | `app-aluno.spec.md` §10 `OQ-14` · §12.2 | essencial |
| `RF-31` | Relaxar `AcaoRequerida.DIVIDA_ID` de `str` para `str \| None`, e atualizar todo consumidor interno do motor que hoje presume `str` para tratar `None` | `app-aluno.spec.md` §10 `OQ-15` · §12.3 | essencial |
| `RF-32` | Fazer `aplicar_gate_1_informacao` emitir uma `AcaoRequerida` de `TIPO_ACAO="INFORMACAO"` nos dois ramos de bloqueio (`STATUS_DIVIDA == QUITADA_A_CONFIRMAR`; `SALDO_DEVEDOR_ATUAL is DESCONHECIDO`), em vez de `acao=None` | `app-aluno.spec.md` §10 `OQ-14` · §12.4 | essencial |
| `RF-33` | Emitir uma `AcaoRequerida` de `TIPO_ACAO="ECONOMIA"` e `DIVIDA_ID=None`, fora do fluxo de gates, quando `ECONOMIA_POTENCIAL_IMEDIATA > 0` | `app-aluno.spec.md` §10 `OQ-14`, `OQ-15` · §12.5 | essencial |
| `RF-34` | Adicionar `AcaoRequerida.CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"]`, nomeando o campo de `Divida` do contrato do motor que gerou o bloqueio do Gate 1 — nunca um `RegistroPergunta.ID` de coleta | `app-aluno.spec.md` §10 `OQ-18` · §12.6 | essencial |
| `RF-35` | Adicionar `Diagnostico.RESERVA_MOBILIZAVEL: Dinheiro` e `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro`, no mesmo bloco de campos comportamentais extras já existente | `app-aluno.spec.md` §10 `OQ-17` · §12.6 | essencial |

### Rodada 3 (2026-09-07) — fatias 3A e 3B — ver seção 13

> **`OQ-23` foi respondida** em 2026-09-07 pelo documento canônico do
> especialista, transcrito integralmente em **§13** e marcado **congelado**
> (*"Nenhuma dessas decisões fica a critério do desenvolvedor"*). O escopo
> desta rodada é o recorte **3A (modelagem de estado)** + **3B (cálculo
> puro)** do fatiamento recomendado em `specs/motor-calculo.discovery.md`
> §13 (rodada de 2026-09-07). A fatia **3C (integração no cronograma-base)
> está fora de escopo** — justificativa técnica na seção 9.
>
> `RF-36` a `RF-42` são **3A**; `RF-43` a `RF-52` são **3B**.

| ID | Requisito | Regras / seções da canônica | Prioridade |
| --- | --- | --- | --- |
| `RF-36` | Modelar em `EstadoFinanceiro` os quatro campos escalares de reserva que a §13.1 consome — `RESERVA_EXISTE`, `RESERVA_TOTAL`, `DISPOSICAO_USO_RESERVA` e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` — com `RESERVA_TOTAL` e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` admitindo o estado desconhecido (`DinheiroTalvez`), exigido pela Regra 3 | §13.1 · §13.9 `deriveReservaMobilizavel` · §13.11 | essencial |
| `RF-37` | Modelar `EstadoFinanceiro.DINHEIRO_DISPONIVEL: Dinheiro` como valor já qualificado na coleta como livre e não comprometido, sem que o motor o revalide | §13.2 · §13.3 (`CAIXA_RECOMENDADO`) · §13.8 | essencial |
| `RF-38` | Modelar investimentos e ativos como **coleções tipadas de itens** (`tuple[...]`, no padrão de `EstadoFinanceiro.dividas: tuple[Divida, ...]`), cada item carregando individualmente seu valor líquido realizável e sua classificação de mobilização — nunca como um total agregado escalar | §13.2 · §13.3 (`Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`) · §13.7 | essencial |
| `RF-39` | Modelar recursos extraordinários como coleção tipada de itens, cada um carregando valor, janela de recebimento e grau de certeza, de modo que "confirmado, disponível e apto no momento atual" seja decidível sobre o item | §13.2 · §13.3 (`EXTRAORDINARIOS_RECOMENDADOS`) · §13.7 | essencial |
| `RF-40` | Criar em `engine/tipos.py` o domínio fechado de classificação de mobilização com exatamente os quatro valores `MOBILIZACAO_POSSIVEL`, `MOBILIZACAO_RECOMENDAVEL`, `MOBILIZACAO_COM_RESSALVAS` e `NAO_MOBILIZAR`, e recebê-lo **já classificado** por item de entrada — a *regra de derivação* da classificação não é implementada nesta rodada (`OQ-26`, seção 9) | §13.2 · §13.3 · §13.7 · `piq-app-spec.md:2614` | essencial |
| `RF-41` | Migrar `Diagnostico.RESERVA_MOBILIZAVEL` de `Dinheiro` para o tipo que admite desconhecido (`DinheiroTalvez`), exigido pela §13.1 Regra 3, tratando-a como **quebra de contrato** (não adição): varrer todo consumidor interno e sinalizar o impacto em `hash_inputs` e no hash congelado de `app-aluno` | §13.1 Regra 3 · §13.9 · discovery `OQ-36` | essencial |
| `RF-42` | Corrigir a colisão de nome renomeando `VARIAVEL_GRAVADA` de `RESERVA_MOBILIZAVEL` para `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` no registro de `B4.03A` (`collection/registros/bloco-04.yaml:156`), preservando o `ID` da pergunta, de modo que `RESERVA_MOBILIZAVEL` passe a designar exclusivamente o valor **derivado** | §13.1 · discovery `OQ-24` (resolvida 2026-09-07) | essencial |
| `RF-43` | Derivar `RESERVA_MOBILIZAVEL` por função **pura**, aplicando as três regras da §13.1 **na ordem registrada**, com `MIN(RESERVA_TOTAL, MAX(0, VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO))` na Regra 2 e o estado desconhecido na Regra 3 — nunca convertido silenciosamente em zero como informação | §13.1 · §13.9 `deriveReservaMobilizavel` | essencial |
| `RF-44` | Calcular `ATAQUE_IMEDIATO_POTENCIAL` por função pura, como a soma das cinco parcelas da §13.2, incluindo os ativos líquidos classificados `MOBILIZACAO_POSSIVEL` **ou** `MOBILIZACAO_RECOMENDAVEL` | §13.2 · §13.11 | essencial |
| `RF-45` | Calcular por funções puras os quatro componentes não protetivos da §13.3 — `CAIXA_RECOMENDADO`, `INVESTIMENTOS_RECOMENDADOS`, `ATIVOS_RECOMENDADOS` e `EXTRAORDINARIOS_RECOMENDADOS` — respeitando que só `MOBILIZACAO_RECOMENDAVEL` entra automaticamente e que recurso apenas previsto para o futuro não compõe o recomendado atual | §13.3 · §13.7 | essencial |
| `RF-46` | Calcular `NECESSIDADE_RESIDUAL` e `RESERVA_RECOMENDADA` por função pura conforme §13.4, com a reserva como **último** componente, `RESERVA_RECOMENDADA = 0` quando `RESULTADO_MENSAL_ATUAL < 0` (trava `MODO_ESTABILIZACAO`) e `= 0` enquanto `RESERVA_MOBILIZAVEL` for desconhecida | §13.4 · §13.7 · §13.9 `deriveReservaRecomendada` | essencial |
| `RF-47` | Calcular `ATAQUE_IMEDIATO_RECOMENDADO` por função pura como `MIN(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL, soma dos cinco componentes recomendados)` | §13.3 · §13.9 `deriveAtaqueImediatoRecomendado` | essencial |
| `RF-48` | Receber `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` **por parâmetro** nas funções de `RF-46` e `RF-47`, como entrada do cálculo, jamais derivada internamente nesta rodada — a §13.5 a define só em prosa (`OQ-29`) e os gabaritos `GAB-AI-06`/`GAB-AI-07` fornecem o valor no enunciado | §13.5 · §13.9 · §13.10 | essencial |
| `RF-49` | Garantir que **nenhuma** das três fórmulas expressamente proibidas pela §13.1 (percentual automático de `RESERVA_TOTAL`, em qualquer das três formas) exista no código do motor | §13.1 TRAVA CANÔNICA | essencial |
| `RF-50` | Verificar, sobre os valores calculáveis nesta rodada, a parte da hierarquia da §13.6 que não depende do aprovado: `ATAQUE_IMEDIATO_POTENCIAL >= ATAQUE_IMEDIATO_RECOMENDADO >= 0` | §13.6 HIERARQUIA CANÔNICA · §13.5 | essencial |
| `RF-51` | Substituir o placeholder `dinheiro(0)` de `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO` (`engine/diagnostico.py:764-765`, deixado por `T-90`) pelo cálculo real de `RF-43`/`RF-47`, e reescrever a justificativa da docstring (`engine/diagnostico.py:674-687`), que cita `OQ-23` como aberta — factualmente desatualizada desde 2026-09-07 | §13.1 · §13.3 · §10 `OQ-23` | essencial |
| `RF-52` | Impedir dupla contagem entre componentes do ataque na parte verificável **sem** a fatia 3C: cada item de investimento, ativo ou recurso extraordinário compõe no máximo um componente do recomendado, e valor declarado como reserva não é recontado como investimento | §13.8 | essencial |

### Rodada 4 (2026-09-09) — fatia 4A — ver seção 14

> **`OQ-29`, `OQ-26` e `OQ-27` (Rodada 3) foram respondidas** pelo documento
> canônico transcrito integralmente em **§14** e marcado **congelado**. O
> escopo desta fatia é **4A** do fatiamento recomendado em
> `specs/motor-calculo.discovery.md`, Rodada 4 (2026-09-09): classificação
> determinística de investimentos e de ativos físicos
> (`classificar_investimento`, `classificar_ativo_fisico`, §14.3–§14.9,
> §14.14) e a fórmula do valor líquido realizável (`VALOR_LIQUIDO_REALIZAVEL_ATIVO`/
> `_DISPONIVEL`, §14.12). As fatias **4B** (`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`/
> `NECESSIDADE_IMEDIATA_DIVIDA`) e **4C** (ligação em `calcular_diagnostico`)
> **estão fora de escopo** — justificativa na seção 9.
>
> `RF-53` a `RF-60` são **4A**.

| ID | Requisito | Regras / seções da canônica | Prioridade |
| --- | --- | --- | --- |
| `RF-53` | Derivar `CLASSIFICACAO_ATIVO` de um investimento pelas seis regras da §14.3.1, avaliadas **em ordem estrita de precedência** (bloqueio → dado desconhecido → disposição condicional → líquido/disponível/sem custo → custo conhecido/D30 → liquidez longa/indeterminado), sem que nenhum tipo de investimento determine a classificação isoladamente | §14.3, §14.3.1, §14.3.1.1 · §14.14 `classifyInvestment` | essencial |
| `RF-54` | Derivar `CLASSIFICACAO_ATIVO` de um ativo físico (imóvel, veículo, outro ativo) pelas regras de `POSSIBILIDADE_VENDA`, essencialidade (`ESSENCIAL`, `IMPORTANTE`/`PARCIAL`, `NAO_ESSENCIAL`) e efeito financeiro recorrente da §14.4 a §14.9, avaliadas **em ordem estrita de precedência**, garantindo que ativo `ESSENCIAL` nunca seja `MOBILIZACAO_RECOMENDAVEL` automaticamente | §14.4–§14.9 · §14.14 `classifyPhysicalAsset` | essencial |
| `RF-55` | Tratar o ramo de ativo `NAO_ESSENCIAL` com `POSSIBILIDADE_VENDA` em `{SIM, JA_PRETENDE}` e `FLUXO_LIQUIDO_RECORRENTE_ATIVO` desconhecido produzindo `MOBILIZACAO_POSSIVEL` — nunca `MOBILIZACAO_RECOMENDAVEL` enquanto o efeito recorrente for desconhecido — para imóvel e para outro ativo, onde `RENDA_RECORRENTE_ATIVO`/`CUSTO_RECORRENTE_ATIVO` são deriváveis da coleta | §14.7, §14.8, §14.9 | essencial |
| `RF-56` | Para veículo, no mesmo ramo de `RF-55` (`ESSENCIALIDADE=NAO_ESSENCIAL` + `POSSIBILIDADE_VENDA em {SIM, JA_PRETENDE}`), **não** produzir `CLASSIFICACAO_ATIVO` — nem `MOBILIZACAO_POSSIVEL`, nem `MOBILIZACAO_RECOMENDAVEL`, nem qualquer outro valor do domínio — porque `FLUXO_LIQUIDO_RECORRENTE_ATIVO` não é derivável pela §14.8 por ausência estrutural de variável de renda de veículo na coleta, não por ausência de resposta do usuário; bloqueado por `OQ-38`, permanece sem classificação até resposta do especialista, e **não** se adota a leitura de tratar a ausência da variável como "efeito desconhecido" para produzir `MOBILIZACAO_POSSIVEL` por essa via (ver seção 9, decisão explícita de não contornar `OQ-38`) | §14.8, §14.9 · `OQ-38` | essencial |
| `RF-57` | Derivar `VALOR_LIQUIDO_REALIZAVEL_ATIVO = VALOR_ESTIMADO_ATIVO − SALDO_PASSIVO_VINCULADO − CUSTOS_ESTIMADOS_DESMOBILIZACAO`, podendo o resultado ser **negativo**, e `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL = MAX(0, VALOR_LIQUIDO_REALIZAVEL_ATIVO)`, que **nunca** pode ser negativo — as duas são variáveis distintas, não sinônimos | §14.12.1, §14.12.2, §14.12.3 · §14.14 `deriveValorLiquidoRealizavelAtivo`/`_Disponivel` | essencial |
| `RF-58` | Normalizar `SALDO_PASSIVO_VINCULADO` e `CUSTOS_ESTIMADOS_DESMOBILIZACAO` pelas regras da §14.12.4/§14.12.5 (inexistente → 0; conhecido → valor direto; percentual → `VALOR_ESTIMADO_ATIVO × PERCENTUAL_CUSTO_DESMOBILIZACAO`; existente porém desconhecido → propagar desconhecido para `VALOR_LIQUIDO_REALIZAVEL_ATIVO`), nunca assumindo zero para um valor desconhecido | §14.12.4, §14.12.5 · `sdd.config.md` §4 ("não inventar dado") | essencial |
| `RF-59` | Mudar `ItemAtivo.CLASSIFICACAO_MOBILIZACAO` e `ItemInvestimento.CLASSIFICACAO_MOBILIZACAO` de campo de entrada obrigatório sem default (decisão da Rodada 3, `EC-31`) para campo **derivado** pelas regras de `RF-53`/`RF-54`, varrendo e corrigindo todo consumidor interno do motor que hoje presume `CLASSIFICACAO_MOBILIZACAO` como argumento de construção de `ItemAtivo`/`ItemInvestimento` — o mecanismo concreto (campo recalculado via `object.__setattr__` ou função separada não armazenada na dataclass) não é decidido por esta spec | §14.3–§14.9 · discovery Rodada 4 §2 (`OQ-40`, decisão técnica) · `sdd.config.md` §4/§8 no padrão de `RF-31`/`RF-41` | essencial |
| `RF-60` | Reescrever `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` — não apenas relaxar — para provar o oposto do que provava antes: que toda derivação de `CLASSIFICACAO_MOBILIZACAO` existente no código segue exatamente as seis regras de `RF-53` (investimento) e as regras de `RF-54`/`RF-55`/`RF-56` (ativo físico), documentando a data e a fonte (§14) em que a derivação passou a ser permitida | discovery Rodada 4 §2 · `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py:57-58` (docstring já previa este momento) | essencial |

### Rodada 4 (2026-09-09) — fatia 4B — ver seção 14

> **Fatia 4A (`RF-53` a `RF-60`) está concluída e verificada** (classificação
> de investimentos/ativos e valor líquido realizável). Esta fatia é **4B** do
> fatiamento recomendado em `specs/motor-calculo.discovery.md`, Rodada 4,
> §8: a fórmula de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`/
> `NECESSIDADE_IMEDIATA_DIVIDA` (§14.1) e o tratamento monetário de
> `ORDEM_ACOES` via `VALOR_ACAO_FINANCEIRA_IMEDIATA` (§14.2), incluindo a
> trava de dupla contagem (§14.2.3). A fatia **4C** (ligação em
> `calcular_diagnostico`, substituindo o placeholder de
> `ATAQUE_IMEDIATO_RECOMENDADO`) **está fora de escopo** — justificativa na
> seção 9; depende desta fatia e de 4A.
>
> `RF-61` a `RF-64` são **4B**.

| ID | Requisito | Regras / seções da canônica | Prioridade |
| --- | --- | --- | --- |
| `RF-61` | Adicionar a `AcaoRequerida` um campo monetário novo, capaz de representar o valor da ação financeira imediata (valor conhecido, ausência de desembolso, ou desconhecido), tratando a mudança como **quebra de contrato** — não adição neutra — com a mesma exigência de varredura de todo consumidor interno já aplicada a `RF-31`/`RF-41`/`RF-59`, incluindo sinalização explícita ao slug `app-aluno` (que já consome `AcaoRequerida` desde a Rodada 2). O nome exato do campo e o mecanismo de derivação (campo em `AcaoRequerida` vs. campo em `Divida` consultado antes do gate) são decisão técnica do plano (`OQ-39`, seção 9), não desta spec | §14.2.1 · discovery Rodada 4 §1.2 (`OQ-39`) · `sdd.config.md` §4/§8 no padrão de `RF-31`/`RF-41`/`RF-59` | essencial |
| `RF-62` | Derivar `VALOR_ACAO_FINANCEIRA_IMEDIATA` pela regra da §14.2.1: `0` quando a ação não exige desembolso financeiro imediato; o valor monetário conhecido quando a ação exige desembolso e o valor é conhecido (derivado de valor já conhecido na operação, proposta, acordo, oportunidade, regularização ou intervenção — nunca de nova pergunta ao usuário) | §14.2.1 | essencial |
| `RF-63` | Quando a ação exige desembolso financeiro imediato e o valor é desconhecido, produzir `VALOR_ACAO_FINANCEIRA_IMEDIATA = DESCONHECIDO` (§14.2.2) e, se essa ação tiver precedência material sobre o uso do caixa, sinalizar o status de ataque imediato correspondente como provisório — usando o mecanismo de status provisório já existente no modelo (`STATUS_METODO = PROVISORIO`, `ORDEM_STATUS`, ou equivalente investigado pelo plano), nunca permitindo que o motor use recursos em outra dívida e só depois descubra que precisava reservar para a ação prioritária | §14.2.2 | essencial |
| `RF-64` | Derivar `NECESSIDADE_IMEDIATA_DIVIDA(divida)` por função pura avaliando, **em ordem estrita de precedência**, exatamente os cinco ramos da §14.1.1 — Gate 1 pendente → `0`; senão Gate 3 pendente → `0`; senão ação financeira imediata de Gate 2/4 executável agora com valor conhecido → `VALOR_ACAO_FINANCEIRA_IMEDIATA`; senão `DIVIDA_STATUS_ESTRATEGICO` em `{PRONTA_PARA_ORDENACAO, EM_ATAQUE}` → `VALOR_RELEVANTE_PARA_QUITACAO` integral (nunca fração); senão `0` — e derivar `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = Σ NECESSIDADE_IMEDIATA_DIVIDA(d)` sobre todas as dívidas do inventário, sinalizando incompletude material (nunca somando como `0`) sempre que qualquer `NECESSIDADE_IMEDIATA_DIVIDA(d)` for `DESCONHECIDO`. O módulo onde a função por-dívida vive (`engine/gates.py` ou `engine/ataque_imediato.py`) é decisão técnica do plano (`OQ-41`, seção 9), não desta spec | §14.1, §14.1.1 · §14.14 `deriveNecessidadeImediataDivida`/`deriveNecessidadeFinanceiraImediataElegivel` · discovery Rodada 4 §3 (`OQ-41`) | essencial |
| `RF-65` | Impedir dupla contagem entre `VALOR_ACAO_FINANCEIRA_IMEDIATA` e `VALOR_RELEVANTE_PARA_QUITACAO` para a mesma dívida: enquanto a dívida estiver temporariamente direcionada a uma ação financeira imediata de Gate 2/4 (terceiro ramo de `RF-64`), ela contribui a `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` exclusivamente via `VALOR_ACAO_FINANCEIRA_IMEDIATA`, nunca somando também `VALOR_RELEVANTE_PARA_QUITACAO` para a mesma dívida naquele estado; resolvido o gate, a dívida volta ao estoque ordinário elegível e passa a contribuir por `VALOR_RELEVANTE_PARA_QUITACAO` | §14.2.3 TRAVA DE DUPLA CONTAGEM | essencial |

### Rodada 4 (2026-09-10) — fatia 4C — ver seção 14

> **Fatias 4A (`RF-53` a `RF-60`) e 4B (`RF-61` a `RF-65`) estão concluídas e
> verificadas** (build limpo em 298 arquivos, 594 testes passando, 47
> gabaritos de homologação). Esta é a fatia **4C** do fatiamento recomendado
> em `specs/motor-calculo.discovery.md`, Rodada 4, §8 — **a última fatia do
> documento do especialista**: liga o resultado de 4A e 4B em
> `calcular_diagnostico`, fazendo `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`
> sair do placeholder `dinheiro(0)` (`engine/diagnostico.py:850`) e valer de
> verdade, pela fórmula já preservada da Rodada 3 e reafirmada em §14.2.4 —
> `MIN(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL,
> RECURSOS_ESTRATEGICAMENTE_RECOMENDADOS)`. Fecha `OQ-29` por completo e
> resolve formalmente `AMB-R3-01` (R3.10.1 do plano), reaberta por esta
> fatia porque sua premissa original — "a fórmula não existe ainda" — deixou
> de ser verdadeira em 2026-09-09.
>
> `RF-66` a `RF-69` são **4C**.

| ID | Requisito | Regras / seções da canônica | Prioridade |
| --- | --- | --- | --- |
| `RF-66` | Fazer `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` carregar o valor calculado pela fórmula `MIN(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL, RECURSOS_ESTRATEGICAMENTE_RECOMENDADOS)` — com `RECURSOS_ESTRATEGICAMENTE_RECOMENDADOS = CAIXA_RECOMENDADO + INVESTIMENTOS_RECOMENDADOS + EXTRAORDINARIOS_RECOMENDADOS + ATIVOS_RECOMENDADOS + RESERVA_RECOMENDADA` — em vez do placeholder `dinheiro(0)` deixado por `T-114`/`AMB-R3-01`, para **todo** `Diagnostico` emitido pelo motor a partir desta fatia, sem exceção de caminho de chamada | §14.2.4 · §13.3 · §13.9 `deriveAtaqueImediatoRecomendado` | essencial |
| `RF-67` | Garantir que o valor de `RF-66` seja produzido exclusivamente pelas funções puras já existentes e verificadas — `derivar_RESERVA_MOBILIZAVEL`, `calcular_ATAQUE_IMEDIATO_POTENCIAL`, `calcular_CAIXA_RECOMENDADO`, `calcular_INVESTIMENTOS_RECOMENDADOS`, `calcular_EXTRAORDINARIOS_RECOMENDADOS`, `calcular_ATIVOS_RECOMENDADOS`, `calcular_NECESSIDADE_RESIDUAL`, `derivar_RESERVA_RECOMENDADA`, `calcular_ATAQUE_IMEDIATO_RECOMENDADO` (`engine/ataque_imediato.py`, Rodada 3) e `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (`engine/gates.py`, fatia 4B) — nenhuma fórmula nova é escrita nesta fatia; a integração apenas compõe funções já homologadas | §14.2.4 (fórmula do "documento anterior... integralmente preservada") · §13.9 · §14.14 | essencial |
| `RF-68` | Resolver formalmente `AMB-R3-01` (plano, R3.10.1) — decidir e registrar **onde** e **como** `calcular_diagnostico`/`calcular_plano` obtêm, na ordem correta de execução, os dois insumos que `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` exige (`ParticaoElegibilidade` e `Mapping[str, AcaoRequerida]`, produzidos por `particionar_elegibilidade`, hoje chamada **depois** de `calcular_diagnostico` em `engine/motor.py::calcular_plano`) — o mecanismo concreto (nova assinatura pública de `calcular_diagnostico`; segunda passada fora dela, preenchendo o campo depois via `dataclasses.replace`; ou outro desenho) é decisão técnica do plano (`OQ-44`, seção 10), não desta spec, mas o requisito de que a decisão **seja tomada e documentada** — não deixada em `dinheiro(0)` por omissão — é desta fatia | §14.2.4 · discovery Rodada 4 §5 (`OQ-43`) · plano `motor-calculo.plan.md` R3.10.1 (`AMB-R3-01`) | essencial |
| `RF-69` | Reescrever a docstring de `engine/diagnostico.py::calcular_diagnostico` e a declaração de campo de `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO`, removendo toda afirmação de que o campo é placeholder, que `OQ-29` está aberta, ou que nenhuma decisão do motor o lê — essas três afirmações ficam factualmente desatualizadas a partir desta fatia (`engine/diagnostico.py:649-653`, `:712-727`) — e documentando, no lugar, a fórmula real aplicada e a referência a `RF-66`/`RF-67`/§14.2.4 | §14.2.4 · `engine/diagnostico.py` (docstring atual, `T-114`/`OQ-29`/`AMB-R3-01`) | essencial |

## 3. User Stories

### `US-01` — Saber por onde começar

> Como **servidor endividado**, quero **saber qual dívida atacar primeiro e
> quanto isso encurta minha saída**, para **parar de decidir no achismo**.

Atende: `RF-05`, `RF-06`, `RF-07`, `RF-09`, `RF-19`

### `US-02` — Não perder dinheiro na virada

> Como **servidor endividado**, quero que **o dinheiro que sobra ao quitar uma
> dívida vá para a próxima no mesmo mês**, para **não perder um mês inteiro de
> avanço por convenção de cálculo**.

Atende: `RF-03`, `RF-04`

### `US-03` — Um plano que não muda sozinho

> Como **servidor endividado**, quero que **o alvo só mude quando algo real
> acontecer**, para **conseguir executar sem recomeçar todo mês**.

Atende: `RF-02`, `RF-10`, `RF-22`

### `US-04` — Enxergar o buraco antes do plano

> Como **servidor endividado em déficit**, quero que **o sistema me diga que
> ainda não há capacidade de ataque**, para **não receber um cronograma que
> depende de um dinheiro que não existe**.

Atende: `RF-14`, `RF-15`, `RF-18`

### `US-05` — Revisar antes de assinar embaixo

> Como **revisor humano do piloto**, quero **ver a justificativa de cada posição
> e a versão do motor e dos parâmetros que produziram aquele plano**, para
> **conseguir auditar e reproduzir o resultado**.

Atende: `RF-09`, `RF-10`, `RF-13`

### `US-06` — Mudar parâmetro sem mexer em código

> Como **especialista responsável pela metodologia**, quero **ajustar os valores
> calibráveis sem depender de alteração de código**, para **evoluir o método por
> versão paramétrica formal**.

Atende: `RF-13`

### `US-07` — Não receber número inventado

> Como **revisor humano**, quero que **dívida sem saldo ou sem parcela conhecida
> apareça como pendente**, para **não aprovar um plano construído sobre chute**.

Atende: `RF-16`, `RF-21`

### `US-08` — Resolver o que precede o ataque

> Como **servidor endividado**, quero que **dívida em renegociação ou sob risco
> patrimonial saia da fila comum e vire uma ação**, para **não atacar hoje algo
> que muda de valor amanhã**.

Atende: `RF-17`

### `US-09` — Saber que ação é a mesma de antes

> Como **camada de aplicação (`app-aluno`)**, quero **identificar uma
> `AcaoRequerida` de forma estável entre recálculos**, para **vincular uma
> pergunta de acompanhamento à mesma ação vista antes, mesmo depois de
> recalcular**.

Atende: `RF-28`

### `US-10` — Ramificar pelo tipo de ação, não por texto livre

> Como **camada de aplicação (`app-aluno`)**, quero **ler um campo tipado que
> diz que espécie de ação é aquela**, para **ramificar a tela sem fazer
> parsing de `descricao`**.

Atende: `RF-29`, `RF-30`

### `US-11` — Não perder ação de dívida travada por informação

> Como **servidor endividado com dívida travada por dado ausente**, quero que
> **o motor produza uma ação a resolver em vez de simplesmente ficar sem
> nada**, para **saber exatamente o que fazer para destravar minha própria
> dívida**.

Atende: `RF-32`, `RF-34`

### `US-12` — Ver a economia como ação, não como número solto

> Como **servidor endividado com gasto fantasma identificado**, quero **que a
> economia potencial vire uma ação explícita**, para **saber que aquilo
> também é algo a executar, não só um número exibido**.

Atende: `RF-31`, `RF-33`

### `US-13` — Ver quanto já posso atacar sem esperar o cronograma

> Como **servidor endividado**, quero **ver, no diagnóstico, quanto tenho
> disponível para atacar imediatamente e quanto de reserva é mobilizável**,
> para **decidir sobre o Bloco 10 sem depender de cálculo feito fora do
> motor**.

Atende: `RF-35`

### Rodada 3 (2026-09-07) — fatias 3A e 3B

### `US-14` — Declarar o que tenho parado, item a item

> Como **servidor endividado com reserva, investimentos e bens**, quero que
> **o sistema receba cada aplicação e cada bem separadamente, com o quanto vale
> e o quanto dá para mobilizar**, para **não ter meu patrimônio reduzido a um
> número único que esconde o que é resgatável e o que não é**.

Atende: `RF-36`, `RF-37`, `RF-38`, `RF-39`, `RF-40`

### `US-15` — Decidir sobre a reserva sem ser empurrado

> Como **servidor endividado que tem reserva**, quero que **só entre em análise
> o valor que eu mesmo disse aceitar**, e que **"prefiro decidir depois" seja
> registrado como pendência e não como zero**, para **não ter minha proteção
> consumida por um percentual que o sistema arbitrou sozinho**.

Atende: `RF-41`, `RF-43`, `RF-49`

### `US-16` — Ver o teto do que dá para atacar hoje

> Como **servidor endividado**, quero **ver quanto do meu dinheiro parado é
> potencialmente utilizável e quanto o método considera adequado usar agora**,
> para **entender a diferença entre o que eu posso e o que faz sentido**.

Atende: `RF-44`, `RF-45`, `RF-46`, `RF-47`, `RF-48`, `RF-50`, `RF-51`

### `US-17` — Não ver o mesmo dinheiro contado duas vezes

> Como **revisor humano do piloto**, quero que **cada valor apareça em um único
> componente do ataque imediato**, para **não aprovar um plano que soma o mesmo
> CDB como reserva e como investimento**.

Atende: `RF-52`

### `US-18` — Nome que quer dizer a mesma coisa nos dois lados

> Como **desenvolvedor do motor**, quero que **`RESERVA_MOBILIZAVEL` designe o
> mesmo valor na coleta e no motor**, para **não perder a regra na tradução
> entre resposta crua e valor derivado**.

Atende: `RF-42`

### Rodada 4 (2026-09-09) — fatia 4A

### `US-19` — Saber o que realmente dá para mobilizar, sem chutar

> Como **servidor endividado com investimentos e bens declarados**, quero que
> **o sistema classifique cada um deles pelas mesmas seis regras, na mesma
> ordem, sempre**, para **confiar que a classificação não depende de qual
> item foi avaliado primeiro nem de interpretação caso a caso**.

Atende: `RF-53`, `RF-54`, `RF-55`, `RF-56`

### `US-20` — Ver o valor líquido de um bem sem esconder o que ele deve

> Como **servidor endividado com um imóvel ou veículo financiado**, quero que
> **o valor líquido do bem já desconte o que ainda devo e o custo de vender**,
> e que **esse valor líquido nunca apareça negativo quando for usado como
> dinheiro disponível**, para **não ser induzido a achar que tenho mais
> liquidez do que realmente tenho**.

Atende: `RF-57`, `RF-58`

### `US-21` — Confiar que a classificação não virou palpite do código

> Como **desenvolvedor do motor**, quero que **a mudança de `ItemAtivo`/
> `ItemInvestimento` de "recebe classificação pronta" para "deriva a
> classificação" seja auditável e coberta por teste que prove a regra, não
> apenas a ausência dela**, para **não reintroduzir silenciosamente uma
> classificação inventada onde antes havia um teste que a proibia**.

Atende: `RF-59`, `RF-60`

### Rodada 4 (2026-09-09) — fatia 4B

### `US-22` — Saber quanto dá para usar agora, sem estimativa otimista

> Como **servidor endividado**, quero que **o sistema me diga exatamente
> quanto do meu dinheiro pode ser aplicado agora nas dívidas, somando só o
> que já passou pelos gates e nunca inventando um valor para o que ainda
> depende de informação ou de ação**, para **não ser induzido a achar que
> tenho mais para atacar do que realmente tenho disponível neste momento**.

Atende: `RF-61`, `RF-62`, `RF-64`

### `US-23` — Não ver a mesma dívida contar duas vezes

> Como **servidor endividado com uma dívida em negociação ativa**, quero que
> **o valor da proposta de quitação em andamento e o valor "normal" da
> mesma dívida nunca sejam somados ao mesmo tempo**, para **confiar que o
> total que o sistema me mostra como disponível para atacar dívidas é real,
> não inflado por contagem repetida**.

Atende: `RF-65`

### `US-24` — Saber quando um valor prioritário ainda não está confirmado

> Como **servidor endividado com uma ação de Gate 2/4 pendente cujo valor
> exato ainda não é conhecido**, quero que **o sistema sinalize que aquele
> valor é provisório, em vez de tratá-lo como zero ou como se já estivesse
> disponível para outra dívida**, para **não correr o risco de o sistema
> recomendar usar aquele dinheiro em outro lugar e descobrir depois que ele
> era necessário para a ação prioritária**.

Atende: `RF-63`

### `US-25` — Confiar que a mudança em `AcaoRequerida` não quebra quem já a consome

> Como **desenvolvedor do motor e do app que já consome `AcaoRequerida`
> (`app-aluno`)**, quero que **a adição do campo monetário seja tratada como
> mudança de contrato, com varredura explícita de todo consumidor interno e
> sinalização ao slug que já depende dessa dataclass**, para **não introduzir
> uma quebra silenciosa num contrato que já está em produção de outro
> slug**.

Atende: `RF-61`

### Rodada 4 (2026-09-10) — fatia 4C

### `US-26` — Ver o número real, não mais o zero de espera

> Como **servidor endividado**, quero que **o valor de "quanto tenho
> disponível para atacar imediatamente" no diagnóstico seja o número real
> calculado pelo método, não um zero que só existe porque a fórmula ainda
> não estava ligada**, para **decidir com base em informação verdadeira, em
> vez de um placeholder que parecia dado e não era**.

Atende: `RF-66`, `RF-67`, `RF-68`, `RF-69`

## 4. Acceptance Criteria

> Os critérios `AC-01` a `AC-18` são reprodução literal de gabaritos da seção 10
> da canônica. Os critérios `AC-19` em diante derivam da devolutiva de
> 2026-09-01 e cobrem regras ainda ausentes da canônica.

| ID | Story | Critério verificável |
| --- | --- | --- |
| `AC-01` | `US-01` | Dado o cenário `GAB-C`, quando o motor calcular a Avalanche, então o resultado é 6 meses, custo futuro total R$ 23719,46, primeira vitória no mês 4 e sequência D001 → D002 → D003 |
| `AC-02` | `US-01` | Dado o cenário `GAB-C`, quando o motor calcular a Bola de Neve, então o resultado é 6 meses, R$ 24463,97, primeira vitória no mês 1 e sequência D003 → D002 → D001 |
| `AC-03` | `US-01` | Dado o cenário `GAB-C`, quando o motor calcular o Híbrido, então o resultado é 6 meses, R$ 24107,20, primeira vitória no mês 1, sequência D003 → D001 → D002, `D*` = D003, penalidade econômica 1,635% e atraso de prazo 0 mês |
| `AC-04` | `US-01` | Dado o cenário `GAB-C`, quando o motor escolher o método, então `METODO_RECOMENDADO_PIQ` = `HIBRIDO`, com `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` = SIM, `ECONOMICAMENTE_PROXIMO(HIBRIDO)` = SIM e `VITORIA_RAPIDA(HIBRIDO)` = SIM |
| `AC-05` | `US-04` | Dado o cenário `GAB-A`, quando o motor diagnosticar, então `PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES` = 2.000, `PAGAMENTOS_EFETIVOS_DIVIDAS` = 800, `RESULTADO_CAIXA_OBSERVADO` = +200, `RESULTADO_MENSAL_ATUAL` = −1.000, `GAP_CAIXA_VS_ESTRUTURAL` = 1.200, `DEFICIT_MENSAL` = 1.000, `CAPACIDADE_ATAQUE_ATUAL` = 0 e `MODO_ESTABILIZACAO` = SIM |
| `AC-06` | `US-04` | Dado o cenário `GAB-B`, quando o motor calcular a capacidade, então `PISO_CAPACIDADE` = 300, `STATUS_FINANCEIRO` = `EQUILIBRIO_FRAGIL`, `CAPACIDADE_ATAQUE_ATUAL` = 200, `BASE_CONSERVADORA` = 200, `FATOR_SEGURANCA` = 1,00, `CAPACIDADE_ATAQUE_CONSERVADORA` = 200 e `CAPACIDADE_ATAQUE_POTENCIAL` = 600 |
| `AC-07` | `US-04` | Dado o cenário `GAB-B`, quando o cronograma-base for montado, então ele usa no máximo R$ 200 por mês — nunca os R$ 600 potenciais, enquanto a economia de R$ 400 não estiver implementada |
| `AC-08` | `US-07` | Dado `GAB-01`, parcela R$ 1.000 com seguro de R$ 50 já incluído, quando o pagamento mensal for computado, então ele permanece R$ 1.000 e nunca vira R$ 1.050 |
| `AC-09` | `US-07` | Dado `GAB-02`, com `INVENTARIO_COMPLETO` = FALSO, quando o plano for emitido, então os totais saem marcados como parciais, `ORDEM_STATUS` ≠ `DEFINITIVA_NA_DATA` e `STATUS_METODO` é no máximo `PROVISORIO` |
| `AC-10` | `US-07` | Dado `GAB-03`, dívida rotativa com saldo e pagamento desconhecidos, quando o motor processar, então a dívida é marcada `INFORMACAO_PENDENTE`, sua trajetória fica `BLOQUEADO`, e nenhum valor é estimado |
| `AC-11` | `US-04` | Dado `GAB-04`, quando o relatório for gerado em modo estabilização, então os R$ 200 observados nunca são chamados de sobra, e método, ordem e cronograma aparecem como fase 2 condicional à estabilização |
| `AC-12` | `US-01` | Dado `GAB-05`, quitação de R$ 30.000 por nova operação de R$ 40.000, quando a troca for avaliada, então o cenário de substituição equivalente é calculado apenas sobre os R$ 30.000, e os R$ 10.000 são tratados como novo endividamento, jamais como economia |
| `AC-13` | `US-03` | Dado um mês sem quitação e sem evento material, quando o mês virar, então `DIVIDA_ALVO_ATUAL` permanece a mesma e nenhum reranqueamento ocorre |
| `AC-14` | `US-02` | Dado que a dívida-alvo é quitada consumindo parte do ataque, quando houver resíduo, então a ordem é recalculada e o delta do teste passa a ser `DELTA_TESTE_AVALANCHE_RESIDUO` = `MIN(RESIDUO_ATAQUE_M, VALOR_RELEVANTE_PARA_QUITACAO)`, nunca a capacidade cheia |
| `AC-15` | `US-02` | Dado que uma dívida com pagamento efetivo de R$ 700 é quitada no mês 4, quando o mês 4 encerrar, então os R$ 700 reforçam a capacidade apenas a partir do mês 5, nunca dentro do mês 4 |
| `AC-16` | `US-05` | Dado qualquer plano emitido, quando a saída for produzida, então ela carrega `ENGINE_VERSION` e `PARAMETROS_VERSION` |
| `AC-17` | `US-06` | Dado o código-fonte do motor, quando for auditado, então nenhum valor `P_*` aparece escrito nele, e alterar o valor na fonte externa muda o resultado sem recompilar regra |
| `AC-18` | `US-05` | Dada uma quitação real ou evento de recálculo, quando a ordem mudar, então a anterior é preservada em snapshot com data, `MOTIVO_RECALCULO`, inputs, método, dívida-alvo e justificativas |
| `AC-19` | `US-01` | Dada uma dívida elegível, quando a Avalanche ranquear, então o benefício marginal é `(DESEMBOLSO_FUTURO_SEM_DELTA − DESEMBOLSO_FUTURO_COM_DELTA) ÷ DELTA_REALMENTE_APLICADO`, com `DELTA_TESTE_AVALANCHE` = `MIN(CAPACIDADE_ATAQUE_CONSERVADORA, VALOR_RELEVANTE_PARA_QUITACAO)` |
| `AC-20` | `US-07` | Dada uma dívida com `QUITACAO_CONSULTADA` = NAO, ou com `STATUS_VALIDADE_PROPOSTA` ∈ {`EXPIRADA`, `VALIDADE_DESCONHECIDA`}, quando `VALOR_RELEVANTE_PARA_QUITACAO` for composto, então ele usa `SALDO_DEVEDOR_ATUAL` |
| `AC-21` | `US-07` | Dada uma dívida sem valor de quitação vigente **e** com `SALDO_DEVEDOR_ATUAL` = `DESCONHECIDO`, quando o motor compuser, então `VALOR_RELEVANTE_PARA_QUITACAO` = `DESCONHECIDO` e a decisão que dependa dele fica bloqueada ou provisória conforme a materialidade |
| `AC-22` | `US-08` | Dada uma dívida em renegociação ou troca pendente, quando os gates forem aplicados, então `DIVIDA_STATUS_ESTRATEGICO` = `INTERVENCAO_PENDENTE`, ela não entra na ordem ordinária, e volta a entrar quando a intervenção for executada, rejeitada ou encerrada |
| `AC-23` | `US-08` | Dada uma dívida com risco material iminente que exija ação anterior, quando os gates forem aplicados, então ela sai da ordem-base e entra em `ORDEM_ACOES` — e risco alto, por si só, nunca a torna automaticamente a primeira dívida |
| `AC-24` | `US-04` | Dado `PACTO` = `EM_CONSTRUCAO`, `HISTORICO_RECAIDA` = SIM e `NOVA_DIVIDA_PREVISTA` = TALVEZ, quando a regra D.4 for aplicada, então `RISCO_RECAIDA` conta 3 sinais e classifica como `ALTO` |
| `AC-25` | `US-04` | Dado um sinal da regra D.4 cujo dado é desconhecido, quando a contagem for feita, então ele **não** conta como risco positivo, e a confiabilidade do dado é reduzida se for material |
| `AC-26` | `US-04` | Dado `RISCO_COMPORTAMENTAL_GERAL` = `ALTO` e `HISTORICO_RECAIDA` = SIM, quando o fator de segurança for calculado, então `P_REDUCAO_RISCO_COMPORTAMENTAL_ALTO` e `P_REDUCAO_HISTORICO_RECAIDA` são aplicadas **separadamente**, sem que uma absorva a outra |
| `AC-27` | `US-01` | Dados dois cenários cujos custos diferem em menos de 1%, quando o cenário economicamente superior for eleito, então há empate material e vence o de menor `PRAZO_TOTAL` |
| `AC-28` | `US-01` | Dado o cenário `GAB-C`, quando o superior econômico for eleito, então é a Avalanche — Híbrido a 1,6347% e Bola de Neve a 3,1388% ficam ambos fora do empate material de 1% |
| `AC-29` | `US-01` | Dado um cenário alternativo, quando `ECONOMICAMENTE_PROXIMO` for avaliado, então ele exige **cumulativamente** penalidade de custo ≤ 5% **e** atraso de prazo ≤ 2 meses contra o cenário superior |
| `AC-30` | `US-03` | Dado `NOVA_DIVIDA_PREVISTA` = SIM com `JANELA_NOVA_DIVIDA` definida, quando a projeção-base for produzida, então nenhuma dívida hipotética entra na `ORDEM_QUITACAO` e nenhum saldo futuro é alterado; o dado alimenta apenas `RISCO_RECAIDA`, alerta e revisão futura |
| `AC-31` | `US-03` | Dada a contratação efetiva da nova dívida, quando ela for registrada, então `EVENTO_RECALCULO` = `NOVA_DIVIDA` e um novo snapshot é gerado |
| `AC-32` | `US-02` | Dada uma dívida com pagamento contratual de R$ 1.200 mas `PAGAMENTO_MENSAL_EFETIVO` = 0, quando ela for quitada, então `VALOR_FLUXO_LIBERADO` = 0 — nunca os R$ 1.200 contratuais |
| `AC-33` | `US-07` | Dada a impossibilidade de simular o benefício marginal por insuficiência de dados, quando a Avalanche ordenar, então `BENEFICIO_MARGINAL_AMORTIZACAO` = `NAO_CALCULAVEL`, usa-se o fallback por taxa efetiva mensal normalizada e depois `CET` comparável, e `ORDEM_STATUS` = `PROVISORIA` — sem jamais fabricar um benefício marginal artificial |
| `AC-34` | `US-04` | Dado `NECESSIDADE_VITORIA` = 8, `HISTORICO_ABANDONO` = SIM, `RISCO_RECAIDA` = BAIXO e `NIVEL_CONTROLE` = FORTE, então `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` = SIM |
| `AC-35` | `US-04` | Dado `NECESSIDADE_VITORIA` = 6 e `HISTORICO_ABANDONO` = SIM, então `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` = NAO — o sinal comportamental isolado não basta |
| `AC-36` | `US-04` | Dadas reduções 0,20 + 0,15 + 0,10 e piso 0,60, então `FATOR_SEGURANCA` = 0,60 — soma primeiro, piso depois |
| `AC-37` | `US-04` | Dado `RESULTADO_MENSAL_ATUAL` = −500, então `STATUS_FINANCEIRO` = `DEFICIT` e `CAPACIDADE_ATAQUE_ATUAL` = 0 |
| `AC-38` | `US-04` | Dado `RESULTADO_MENSAL_ATUAL` = 200 e `PISO_CAPACIDADE` = 300, então `STATUS_FINANCEIRO` = `EQUILIBRIO_FRAGIL` e `CAPACIDADE_ATAQUE_ATUAL` = 200 — não 0, não 300 |
| `AC-39` | `US-04` | Dado `RESULTADO_MENSAL_ATUAL` = 500 e `PISO_CAPACIDADE` = 300, então `STATUS_FINANCEIRO` = `CAPACIDADE_POSITIVA` e `CAPACIDADE_ATAQUE_ATUAL` = 500 |
| `AC-40` | `US-05` | Dado o valor 10,125, quando exibido em 2 casas, então resulta 10,13 (`ROUND_HALF_UP`) |
| `AC-41` | `US-08` | Dada dívida `EM_ACORDO` com acordo já executado, estrutura vigente conhecida e gates resolvidos, então ela pode atingir `PRONTA_PARA_ORDENACAO` |
| `AC-42` | `US-08` | Dada dívida `COBRANCA_SEM_PAGAMENTO` com saldo conhecido, sem parcela mensal conhecida e gates resolvidos, então ela pode atingir `PRONTA_PARA_ORDENACAO`, e `PAGAMENTO_MENSAL_DEVIDO_VIGENTE` não é inventado |
| `AC-43` | `US-08` | Dada dívida desviada pelo Gate 2, então `DIVIDA_STATUS_ESTRATEGICO` = `INTERVENCAO_PENDENTE` e `GATE_PENDENTE` = `CONTENCAO_RISCO` |
| `AC-44` | `US-08` | Dada dívida `QUITADA_A_CONFIRMAR`, então ela é inelegível, fica `INFORMACAO_PENDENTE` com `GATE_PENDENTE` = `INFORMACAO`, e não é ordenada nem atacada até a confirmação |
| `AC-45` | `US-08` | Dada dívida `STATUS_DIVIDA` = `OUTRA`, então `DIVIDA_STATUS_ESTRATEGICO` = `EM_ANALISE` e ela não recebe ataque até a situação ser normalizada |
| `AC-46` | `US-04` | Dado `NIVEL_CONTROLE` = FRAGIL, então `CONFIABILIDADE_DADOS` = BAIXA — a ordem de avaliação testa BAIXA antes de ALTA |
| `AC-47` | `US-01` | Dadas as trajetórias A e B com prazos diferentes, quando `DESEMBOLSO_FUTURO` for apurado, então cada uma é somada até seu próprio `SALDO = 0` — sem truncar no menor prazo nem usar horizonte fixo |
| `AC-48` | `US-09` | Dado um mesmo caso recalculado em dois snapshots consecutivos sem que a ação pendente mude de natureza, quando `ORDEM_ACOES` for comparada entre os dois snapshots, então o `ACAO_ID` da ação correspondente é idêntico nos dois |
| `AC-49` | `US-10` | Dada qualquer `AcaoRequerida` emitida pelo motor, quando `TIPO_ACAO` for lido, então o valor é exatamente um de `{"INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"}` — nenhum outro literal, nenhum acento, nenhum parêntese |
| `AC-50` | `US-10` | Dada uma dívida bloqueada no Gate 1 (`GATE_PENDENTE.INFORMACAO`), quando a `AcaoRequerida` correspondente for emitida, então `TIPO_ACAO` = `"INFORMACAO"` |
| `AC-51` | `US-10` | Dada uma dívida em Gate 3 com `RENEGOCIACAO_PENDENTE`, quando a `AcaoRequerida` correspondente for emitida, então `TIPO_ACAO` = `"RENEGOCIACAO"` |
| `AC-52` | `US-10` | Dada uma dívida em Gate 3 com `TROCA_PENDENTE`, quando a `AcaoRequerida` correspondente for emitida, então `TIPO_ACAO` = `"TROCA"` |
| `AC-53` | `US-12` | Dado `ECONOMIA_POTENCIAL_IMEDIATA > 0`, quando o motor montar `ORDEM_ACOES`, então ela contém uma `AcaoRequerida` com `TIPO_ACAO = "ECONOMIA"` e `DIVIDA_ID = None` |
| `AC-54` | `US-12` | Dado `ECONOMIA_POTENCIAL_IMEDIATA = 0`, quando o motor montar `ORDEM_ACOES`, então nenhuma `AcaoRequerida` de `TIPO_ACAO = "ECONOMIA"` é emitida |
| `AC-55` | `US-12` | Dado o código-fonte do motor após esta mudança, quando todo ponto interno que lê `AcaoRequerida.DIVIDA_ID` for auditado, então nenhum deles presume `str` sem antes checar `None` |
| `AC-56` | `US-11` | Dada uma dívida com `STATUS_DIVIDA == QUITADA_A_CONFIRMAR`, quando `aplicar_gate_1_informacao` processar essa dívida, então `ResultadoGates.acao` não é `None`: é uma `AcaoRequerida` com `TIPO_ACAO = "INFORMACAO"` e `CAMPO_PENDENTE = "STATUS_DIVIDA"` |
| `AC-57` | `US-11` | Dada uma dívida cujo `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` dentro de `compor_VALOR_RELEVANTE_PARA_QUITACAO`, quando `aplicar_gate_1_informacao` processar essa dívida, então `ResultadoGates.acao` não é `None`: é uma `AcaoRequerida` com `TIPO_ACAO = "INFORMACAO"` e `CAMPO_PENDENTE = "SALDO_DEVEDOR_ATUAL"` |
| `AC-58` | `US-11` | Dado o gabarito `GAB-03` (dívida rotativa sem saldo/pagamento, `INFORMACAO_PENDENTE`) reexecutado após esta mudança, quando `ORDEM_ACOES` for inspecionada, então ela reflete a `AcaoRequerida` agora emitida pelo Gate 1, com tolerância zero em relação ao valor esperado — nenhuma divergência absorvível por arredondamento |
| `AC-59` | `US-11` | Dado o cenário `EC-17` (todas as dívidas bloqueadas pelos gates) reexecutado após esta mudança, quando `ORDEM_ACOES` for inspecionada, então ela vem preenchida com as ações de informação correspondentes, em vez de vazia, com tolerância zero |
| `AC-60` | `US-11` | Dados os cinco invariantes (`GAB-01` a `GAB-05`) reexecutados após esta mudança, quando cada um for verificado, então todos continuam satisfeitos |
| `AC-61` | `US-13` | Dado qualquer `SnapshotOrdem` emitido pelo motor, quando `diagnostico.RESERVA_MOBILIZAVEL` e `diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` forem lidos, então ambos existem como campo de `Diagnostico`, tipados como `Dinheiro`, no mesmo bloco dos demais campos comportamentais extras (`NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS`, `RISCO_RECAIDA`, `RISCO_COMPORTAMENTAL_GERAL`, `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`) |

### Rodada 3 (2026-09-07) — fatias 3A e 3B

> **Os gabaritos `GAB-AI-01` a `GAB-AI-07` (§13.10) são critérios desta rodada**
> — `AC-70` a `AC-76`, um por gabarito, com os números literais do documento
> canônico. `GAB-AI-08` **não** é critério desta rodada: depende de
> `ATAQUE_IMEDIATO_APROVADO`, que exige o passo de confirmação do usuário
> (`OQ-30`) e a injeção no cronograma-base (`OQ-32`, `OQ-35`) — fatia 3C, fora
> de escopo (seção 9). Ele é registrado abaixo, sem ID `AC-NN`, como critério
> **da rodada futura**.
>
> **Tolerância.** Os `GAB-AI` são valores exatos de `MIN`/`MAX`/soma, sem
> acumulação de arredondamento; a régua aplicável é a de tolerância **zero** da
> seção 5, não a de `± R$ 0,05` para monetário acumulado.

| ID | Story | Critério verificável |
| --- | --- | --- |
| `AC-62` | `US-14` | Dado um `EstadoFinanceiro` construído, quando seus campos forem inspecionados, então existem `RESERVA_EXISTE`, `RESERVA_TOTAL`, `DISPOSICAO_USO_RESERVA` e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`, escritos com esses nomes caractere por caractere, e `RESERVA_TOTAL` e `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` aceitam tanto valor monetário quanto o estado desconhecido |
| `AC-63` | `US-14` | Dado um `EstadoFinanceiro` construído, quando `DINHEIRO_DISPONIVEL` for lido, então ele existe como campo monetário sempre presente (nunca desconhecido) e o motor o consome sem executar nenhuma revalidação de "livre / não comprometido" |
| `AC-64` | `US-14` | Dado um estado com 3 investimentos e 2 ativos, quando as coleções forem lidas, então cada item é um elemento distinto de uma coleção tipada imutável, cada um com seu próprio valor líquido realizável e sua própria classificação de mobilização — e não existe nenhum campo escalar de total agregado de investimentos ou de ativos em `EstadoFinanceiro` |
| `AC-65` | `US-14` | Dado um estado com 2 recursos extraordinários, quando a coleção for lida, então cada item carrega valor, janela de recebimento e grau de certeza, permitindo decidir por item se ele é "confirmado, disponível e apto no momento atual" sem consultar nenhum outro campo |
| `AC-66` | `US-14` | Dado o enum de classificação de mobilização em `engine/tipos.py`, quando seus membros forem enumerados, então são exatamente quatro — `MOBILIZACAO_POSSIVEL`, `MOBILIZACAO_RECOMENDAVEL`, `MOBILIZACAO_COM_RESSALVAS`, `NAO_MOBILIZAR` — sem quinto valor, sem acento e sem sinônimo |
| `AC-67` | `US-14` | Dado o código do motor após esta rodada, quando for auditado, então não existe nenhuma função que **derive** a classificação de mobilização a partir de liquidez, custo de desmobilização, disposição de uso ou passivo vinculado: a classificação chega exclusivamente como dado de entrada por item (`OQ-26` em aberto) — **revogado pela Rodada 4 (2026-09-09)**: `OQ-26` foi respondida (§14), `RF-53`/`RF-54` passam a exigir exatamente a função de derivação que este critério proibia, e `RF-59`/`RF-60`/`AC-97` substituem este critério a partir da fatia 4A. Mantido aqui apenas como registro histórico do que valia antes de 2026-09-09 |
| `AC-68` | `US-15` | Dado `Diagnostico.RESERVA_MOBILIZAVEL` após esta rodada, quando seu tipo for verificado, então ele admite o estado desconhecido além do valor monetário, e `mypy --strict` acusa todo consumidor interno que trate apenas o ramo monetário sem cobrir o ramo desconhecido |
| `AC-69` | `US-18` | Dado `collection/registros/bloco-04.yaml`, quando o registro de `B4.03A` for lido, então `VARIAVEL_GRAVADA` é `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`, o campo `ID` continua sendo `B4.03A`, e nenhum outro registro de coleta grava em `RESERVA_MOBILIZAVEL` |
| `AC-70` | `US-15` | Dado `GAB-AI-01` (`RESERVA_TOTAL = 20.000`; usuário aceita analisar `5.000`), quando `RESERVA_MOBILIZAVEL` for derivada, então o resultado é exatamente `5.000` |
| `AC-71` | `US-15` | Dado `GAB-AI-02` (`RESERVA_TOTAL = 20.000`; usuário informa máximo de `30.000`), quando `RESERVA_MOBILIZAVEL` for derivada, então o resultado é exatamente `20.000` — limitado pelo total, nunca `30.000` |
| `AC-72` | `US-15` | Dado `GAB-AI-03` (`DISPOSICAO_USO_RESERVA = NAO`), quando `RESERVA_MOBILIZAVEL` for derivada, então o resultado é exatamente `0`, independentemente de `RESERVA_TOTAL` e do valor informado pelo usuário |
| `AC-73` | `US-15` | Dado `GAB-AI-04` (usuário responde "prefiro decidir depois"), quando `RESERVA_MOBILIZAVEL` for derivada, então o resultado é o estado **desconhecido** — não `0` — e nenhum valor de reserva entra numericamente em `RESERVA_RECOMENDADA` nem em `ATAQUE_IMEDIATO_RECOMENDADO` |
| `AC-74` | `US-16` | Dado `GAB-AI-05` (`RESULTADO_MENSAL_ATUAL = -1.000`; `RESERVA_MOBILIZAVEL = 20.000`), quando `RESERVA_RECOMENDADA` for derivada, então `MODO_ESTABILIZACAO = SIM` e `RESERVA_RECOMENDADA = 0` — mesmo havendo 20.000 mobilizáveis |
| `AC-75` | `US-16` | Dado `GAB-AI-06` (`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = 20.000` recebida por parâmetro; `CAIXA_RECOMENDADO = 5.000`; `INVESTIMENTOS_RECOMENDADOS = 7.000`; `EXTRAORDINARIOS_RECOMENDADOS = 0`; `ATIVOS_RECOMENDADOS = 0`; `RESERVA_MOBILIZAVEL = 10.000`; `RESULTADO_MENSAL_ATUAL >= 0`), quando o cálculo rodar, então `NECESSIDADE_RESIDUAL = 8.000`, `RESERVA_RECOMENDADA = 8.000` e `ATAQUE_IMEDIATO_RECOMENDADO = 20.000` |
| `AC-76` | `US-16` | Dado `GAB-AI-07` (`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = 10.000` recebida por parâmetro; recursos recomendáveis totais `= 25.000`), quando `ATAQUE_IMEDIATO_RECOMENDADO` for calculado, então o resultado é exatamente `10.000` — nunca `25.000` |
| `AC-77` | `US-16` | Dado um conjunto de itens com as quatro classificações presentes, quando `ATAQUE_IMEDIATO_POTENCIAL` for calculado, então ele soma `DINHEIRO_DISPONIVEL`, `RESERVA_MOBILIZAVEL`, os investimentos líquidos mobilizáveis, os recursos extraordinários potenciais e os ativos líquidos classificados `MOBILIZACAO_POSSIVEL` **ou** `MOBILIZACAO_RECOMENDAVEL` — e nenhum item `MOBILIZACAO_COM_RESSALVAS` ou `NAO_MOBILIZAR` entra na soma |
| `AC-78` | `US-16` | Dado um ativo classificado `MOBILIZACAO_POSSIVEL` e outro `MOBILIZACAO_RECOMENDAVEL`, quando `ATIVOS_RECOMENDADOS` for calculado, então apenas o `MOBILIZACAO_RECOMENDAVEL` compõe a soma — e o `MOBILIZACAO_POSSIVEL` permanece contando apenas em `ATAQUE_IMEDIATO_POTENCIAL` |
| `AC-79` | `US-16` | Dado um recurso extraordinário previsto para o futuro e não confirmado, quando `EXTRAORDINARIOS_RECOMENDADOS` for calculado, então ele não compõe a soma, ainda que componha `RECURSOS_EXTRAORDINARIOS_POTENCIAIS` |
| `AC-80` | `US-16` | Dado que os cinco componentes recomendados somam mais que `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`, quando `ATAQUE_IMEDIATO_RECOMENDADO` for calculado, então o resultado é o menor dos dois, e a chamada recebe `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` como argumento explícito — a função não a busca em `EstadoFinanceiro` nem em `Diagnostico` |
| `AC-81` | `US-15` | Dado o código-fonte de `engine/` após esta rodada, quando for auditado, então nenhuma multiplicação de `RESERVA_TOTAL` por percentual e nenhuma subtração de reserva mínima padrão produz `RESERVA_MOBILIZAVEL` — as três fórmulas proibidas da §13.1 não existem em nenhuma forma |
| `AC-82` | `US-16` | Dado qualquer conjunto de entradas válido das funções desta rodada, quando `ATAQUE_IMEDIATO_POTENCIAL` e `ATAQUE_IMEDIATO_RECOMENDADO` forem calculados sobre o mesmo estado, então `ATAQUE_IMEDIATO_POTENCIAL >= ATAQUE_IMEDIATO_RECOMENDADO >= 0` — com tolerância zero |
| `AC-83` | `US-17` | Dado um item de investimento, ativo ou recurso extraordinário, quando os componentes da §13.3 forem calculados, então esse item compõe no máximo **um** deles — nenhum item aparece simultaneamente em `INVESTIMENTOS_RECOMENDADOS` e `ATIVOS_RECOMENDADOS`, nem em `ATIVOS_RECOMENDADOS` e `CAIXA_RECOMENDADO` |
| `AC-84` | `US-17` | Dado o registro `B4.04` da coleta, quando seu enunciado for lido, então ele continua excluindo explicitamente os valores já informados como reserva ("além dos valores que você já informou como reserva"), de modo que o primeiro caso vedado da §13.8 permanece prevenido na origem |
| `AC-85` | `US-16` | Dado qualquer `Diagnostico` emitido após esta rodada, quando `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO` forem lidos, então ambos carregam o valor derivado por `RF-43`/`RF-47`, e não existe mais nenhum `dinheiro(0)` de placeholder para esses dois campos em `engine/diagnostico.py` |
| `AC-86` | `US-16` | Dada a docstring de `calcular_diagnostico` (`engine/diagnostico.py`), quando for lida após esta rodada, então ela não afirma que `OQ-23` está aberta nem que a derivação está bloqueada por ela — registra que `OQ-23` foi respondida em 2026-09-07 e aponta para §13 |
| `AC-87` | `US-16` | Dados `GAB-A`, `GAB-B`, `GAB-C` e os cinco invariantes `GAB-01` a `GAB-05` reexecutados após esta rodada, quando cada um for verificado, então todos continuam satisfeitos com as mesmas tolerâncias da seção 5 — a substituição do placeholder e a mudança de tipo de `RF-41` não alteram método recomendado, ordem, prazo nem custo |

> **Critério da rodada futura (fatia 3C, não desta rodada).** `GAB-AI-08`:
> dado `ATAQUE_IMEDIATO_RECOMENDADO = 15.000` e o usuário confirmando apenas
> `9.000`, então `ATAQUE_IMEDIATO_APROVADO = 9.000` e o cronograma-base utiliza
> apenas 9.000. Depende de `OQ-30` (onde vive o passo de confirmação), `OQ-32`
> (conciliação com `RF-14`/`RF-15`) e `OQ-35` (momento da aplicação no
> cronograma) — nenhuma delas resolvida. Não recebe ID `AC-NN` aqui para não
> criar critério não verificável nesta rodada.

### Rodada 4 (2026-09-09) — fatia 4A

> **Os gabaritos `GAB-NFI-06` a `GAB-NFI-12` (§14.16) são critérios desta
> rodada** — `AC-88` a `AC-94`, um por gabarito, com os valores literais do
> documento canônico. `GAB-NFI-01` a `GAB-NFI-05` (necessidade financeira
> imediata por dívida) **não são desta fatia** — são a fatia 4B (seção 9).
>
> **Tolerância.** Classificação (`CLASSIFICACAO_ATIVO`) segue a régua de
> tolerância **zero** da seção 5. Valores monetários de `GAB-NFI-12` seguem a
> mesma régua zero dos `GAB-AI` — são subtração/`MAX` exatos, sem acumulação
> de arredondamento.

| ID | Story | Critério verificável |
| --- | --- | --- |
| `AC-88` | `US-19` | Dado `GAB-NFI-06` (`DISPOSICAO_USO_INVESTIMENTO=SIM`, `LIQUIDEZ_INVESTIMENTOS=BLOQUEADO`), quando `classificar_investimento` for aplicada, então o resultado é `NAO_MOBILIZAR` — a Regra 1 (bloqueio) vence independentemente da disposição ser `SIM` |
| `AC-89` | `US-19` | Dado `GAB-NFI-07` (`DISPOSICAO_USO_INVESTIMENTO=SIM`, `LIQUIDEZ_INVESTIMENTOS=D1`, sem custo relevante conhecido, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=10.000`), quando `classificar_investimento` for aplicada, então o resultado é `MOBILIZACAO_RECOMENDAVEL` |
| `AC-90` | `US-19` | Dado `GAB-NFI-08` (`DISPOSICAO_USO_INVESTIMENTO=TALVEZ`, investimento efetivamente resgatável), quando `classificar_investimento` for aplicada, então o resultado é `MOBILIZACAO_POSSIVEL` |
| `AC-91` | `US-19` | Dado `GAB-NFI-09` (`ESSENCIALIDADE=ESSENCIAL`, `POSSIBILIDADE_VENDA=SIM`), quando `classificar_ativo_fisico` for aplicada, então o resultado é `MOBILIZACAO_COM_RESSALVAS` — **nunca** `MOBILIZACAO_RECOMENDAVEL`, por mais favorável que seja `POSSIBILIDADE_VENDA` |
| `AC-92` | `US-19` | Dado `GAB-NFI-10` (`ESSENCIALIDADE=NAO_ESSENCIAL`, `POSSIBILIDADE_VENDA=SIM`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=30.000`, `FLUXO_LIQUIDO_RECORRENTE_ATIVO=-500`), quando `classificar_ativo_fisico` for aplicada, então o resultado é `MOBILIZACAO_RECOMENDAVEL` |
| `AC-93` | `US-19` | Dado `GAB-NFI-11` (mesmo cenário de `AC-92` exceto `FLUXO_LIQUIDO_RECORRENTE_ATIVO=+700`), quando `classificar_ativo_fisico` for aplicada, então o resultado é `MOBILIZACAO_POSSIVEL` — fluxo recorrente positivo impede `MOBILIZACAO_RECOMENDAVEL` mesmo com o mesmo valor líquido disponível de `AC-92` |
| `AC-94` | `US-20` | Dado `GAB-NFI-12` (`VALOR_ESTIMADO_ATIVO=100.000`, `SALDO_PASSIVO_VINCULADO=105.000`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO=5.000`), quando `VALOR_LIQUIDO_REALIZAVEL_ATIVO` e `_DISPONIVEL` forem derivados, então `VALOR_LIQUIDO_REALIZAVEL_ATIVO = -10.000` e `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL = 0` — o primeiro é negativo, o segundo nunca é |
| `AC-95` | `US-19` | Dadas as seis regras de `classificar_investimento` (`RF-53`) aplicadas em sequência a um investimento que satisfaz simultaneamente as condições de mais de uma regra, quando a classificação for derivada, então prevalece a **primeira** regra da ordem de precedência que se aplica — nunca uma regra posterior, ainda que também seria satisfeita isoladamente |
| `AC-96` | `US-19` | Dado um ativo físico que satisfaz simultaneamente a condição de bloqueio (`POSSIBILIDADE_VENDA=NAO`) e a condição de dado desconhecido, quando `classificar_ativo_fisico` for aplicada, então o resultado é `NAO_MOBILIZAR` — a ordem de precedência da §14.4.1 (bloqueio primeiro) prevalece sobre a §14.4.2 |
| `AC-97` | `US-21` | Dado `tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py` após esta fatia, quando for lido, então ele não reprova mais a existência de `classificar_investimento`/`classificar_ativo_fisico`, e em vez disso verifica positivamente — por execução dos sete `GAB-NFI-06` a `GAB-NFI-12` ou equivalente — que toda derivação de `CLASSIFICACAO_MOBILIZACAO` no código segue exatamente as regras de `RF-53`/`RF-54`/`RF-55`/`RF-56`, documentando a data (2026-09-09) e a fonte (§14) da liberação |
| `AC-98` | `US-21` | Dado o código-fonte de `engine/` após esta fatia, quando todo ponto que hoje constrói `ItemAtivo(...)` ou `ItemInvestimento(...)` passando `CLASSIFICACAO_MOBILIZACAO` como argumento de construtor for auditado, então nenhum deles sobrevive sem correção — ou o argumento foi removido do construtor (classificação derivada internamente), ou o consumidor passou a chamar a função de classificação explicitamente antes de construir o item |
| `AC-99` | `US-20` | Dado um ativo cujo `SALDO_PASSIVO_VINCULADO` existe mas é desconhecido, quando `VALOR_LIQUIDO_REALIZAVEL_ATIVO` for derivado, então o resultado é o estado **desconhecido** — nunca `0` como se o passivo não existisse — e a mesma regra vale para `CUSTOS_ESTIMADOS_DESMOBILIZACAO` desconhecido |
| `AC-100` | `US-19` | Dado um ativo físico do tipo veículo, `ESSENCIALIDADE=NAO_ESSENCIAL`, `POSSIBILIDADE_VENDA=SIM`, sem variável de renda recorrente disponível na entrada, quando `classificar_ativo_fisico` for aplicada, então o resultado **não** é um valor do domínio de `CLASSIFICACAO_ATIVO` — é sinalizado como pendente/bloqueado por `OQ-38` — e em nenhum ponto do código um valor de renda é inventado, assumido como zero, ou tratado como "desconhecido" para produzir `MOBILIZACAO_POSSIVEL` por essa via (`RF-56`) |

### Rodada 4 (2026-09-09) — fatia 4B

> **Os gabaritos `GAB-NFI-01` a `GAB-NFI-05` (§14.16) são critérios desta
> rodada** — `AC-101` a `AC-105`, um por gabarito, com os valores literais do
> documento canônico. `GAB-NFI-06` a `GAB-NFI-12` já foram cobertos pela
> fatia 4A (`AC-88` a `AC-94`).
>
> **Tolerância.** Valores monetários de `NECESSIDADE_IMEDIATA_DIVIDA`/
> `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` seguem a régua de tolerância
> **zero** da seção 5 — são seleção condicional e soma exatas, sem
> acumulação de arredondamento; não a faixa de `± R$ 0,05` de monetário
> acumulado ao longo de meses.

| ID | Story | Critério verificável |
| --- | --- | --- |
| `AC-101` | `US-22` | Dado `GAB-NFI-01` (dívida ordinária elegível: `VALOR_RELEVANTE_PARA_QUITACAO=20.000`, `DIVIDA_STATUS_ESTRATEGICO=PRONTA_PARA_ORDENACAO`, nenhum gate pendente, nenhuma ação financeira imediata), quando `NECESSIDADE_IMEDIATA_DIVIDA` for derivada, então o resultado é exatamente `20.000` — o valor integral, não uma fração |
| `AC-102` | `US-22` | Dado `GAB-NFI-02` (`VALOR_RELEVANTE_PARA_QUITACAO=20.000`, `Gate1=PENDENTE`), quando `NECESSIDADE_IMEDIATA_DIVIDA` for derivada, então o resultado é exatamente `0` — Gate 1 pendente vence antes de qualquer outra condição ser avaliada |
| `AC-103` | `US-22` | Dado `GAB-NFI-03` (`Gate3=PENDENTE`, `Gate1` resolvido, `VALOR_RELEVANTE_PARA_QUITACAO` positivo), quando `NECESSIDADE_IMEDIATA_DIVIDA` for derivada, então o resultado é exatamente `0` — Gate 3 pendente vence sobre o status estratégico e sobre qualquer ação financeira imediata, mesmo com `Gate1` já resolvido |
| `AC-104` | `US-23` | Dado `GAB-NFI-04` (oportunidade de Gate 4 com `VALOR_ACAO_FINANCEIRA_IMEDIATA=8.000` e, para a mesma dívida, `VALOR_RELEVANTE_PARA_QUITACAO=15.000`), quando `NECESSIDADE_IMEDIATA_DIVIDA` for derivada, então o resultado é exatamente `8.000` — nunca `8.000 + 15.000` = `23.000`; a trava de dupla contagem (`RF-65`) impede somar os dois valores da mesma dívida |
| `AC-105` | `US-22` | Dado `GAB-NFI-05` (ação prioritária = "solicitar proposta", sem exigência de desembolso financeiro imediato), quando `VALOR_ACAO_FINANCEIRA_IMEDIATA` for derivado, então o resultado é exatamente `0` |
| `AC-106` | `US-22` | Dadas as cinco condições de `NECESSIDADE_IMEDIATA_DIVIDA` (`RF-64`) avaliadas sobre uma dívida que satisfaz simultaneamente mais de uma — por exemplo, Gate 1 pendente **e**, ao mesmo tempo, status estratégico em `{PRONTA_PARA_ORDENACAO, EM_ATAQUE}` —, quando o valor for derivado, então prevalece a **primeira** condição da ordem de precedência estrita que se aplica (Gate 1 vence Gate 3 vence ação financeira imediata vence status estratégico), nunca uma condição posterior mesmo que também seria satisfeita isoladamente |
| `AC-107` | `US-22` | Dado o texto normativo da §14.1.2 ("REGRA CANÔNICA"), quando `VALOR_RELEVANTE_PARA_QUITACAO` for usado no quarto ramo de `NECESSIDADE_IMEDIATA_DIVIDA`, então ele entra **integral**, nunca como fração "estrategicamente vantajosa" — essa segunda pergunta (quanto vale a pena disponibilizar) pertence a `ATAQUE_IMEDIATO_RECOMENDADO` (fatia 4C), não a esta fórmula |
| `AC-108` | `US-22` | Dado um inventário de dívidas em que ao menos uma tem `NECESSIDADE_IMEDIATA_DIVIDA(d) = DESCONHECIDO` (ação financeira imediata prioritária com valor desconhecido, `RF-63`), quando `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` for derivada, então o resultado sinaliza incompletude material — a dívida de valor desconhecido **não** é somada como `0`, e o total não é apresentado como definitivo |
| `AC-109` | `US-24` | Dado uma ação de Gate 2/4 com desembolso financeiro imediato exigido e valor desconhecido, e essa ação tendo precedência material sobre o uso do caixa, quando `VALOR_ACAO_FINANCEIRA_IMEDIATA` for derivado, então o resultado é o estado desconhecido **e** o status de ataque imediato correspondente é sinalizado como provisório (mecanismo concreto de sinalização definido pelo plano técnico) — o motor não aplica recursos a outra dívida silenciosamente enquanto essa reserva não estiver resolvida |
| `AC-110` | `US-25` | Dado o código-fonte de `engine/` após esta fatia, quando todo ponto que constrói `AcaoRequerida(...)` ou lê seus campos for auditado, então o novo campo monetário está presente em toda construção (ou tipado de forma que `mypy --strict` acuse a ausência), e existe registro explícito de que o slug `app-aluno` — consumidor de `AcaoRequerida` desde a Rodada 2 (`RF-28` a `RF-35`) — foi sinalizado sobre a mudança de contrato, no mesmo padrão de coordenação já usado para `RF-31`/`RF-41`/`RF-59` |
| `AC-111` | `US-23` | Dado o código-fonte de `engine/` após esta fatia, quando `deriveNecessidadeImediataDivida`/`deriveNecessidadeFinanceiraImediataElegivel` forem auditadas, então nenhuma delas soma `VALOR_ACAO_FINANCEIRA_IMEDIATA` e `VALOR_RELEVANTE_PARA_QUITACAO` da mesma dívida no mesmo cálculo — a função retorna exatamente um dos dois valores por dívida, nunca os dois somados (`RF-65`) |

### Rodada 4 (2026-09-10) — fatia 4C

> **`AC-85` (Rodada 3) fica totalmente satisfeito a partir desta fatia.**
> Desde 2026-09-07 ele estava parcialmente satisfeito: cumprido para
> `RESERVA_MOBILIZAVEL`, pendente para `ATAQUE_IMEDIATO_RECOMENDADO`
> (`AMB-R3-01`). `AC-112` a `AC-117` cobrem a parte que faltava.
>
> **Tolerância.** O valor de `ATAQUE_IMEDIATO_RECOMENDADO` dentro de
> `Diagnostico` segue a régua de tolerância **zero** já fixada para os
> `GAB-AI`/`GAB-NFI` (seção 5) — é composição exata de `MIN`/soma sobre
> funções já homologadas, sem acumulação de arredondamento. Os demais campos
> de `Diagnostico` (método recomendado, ordem, custo, prazo, gates, status,
> `D*`) seguem sob tolerância zero **por não poderem mudar de todo** — ver
> `AC-116`.

| ID | Story | Critério verificável |
| --- | --- | --- |
| `AC-112` | `US-26` | Dado qualquer `Diagnostico` emitido pelo motor após esta fatia, quando `ATAQUE_IMEDIATO_RECOMENDADO` for lido, então ele carrega o valor calculado por `MIN(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL, RECURSOS_ESTRATEGICAMENTE_RECOMENDADOS)` (§14.2.4) — e não existe mais nenhum `dinheiro(0)` de placeholder para este campo em `engine/diagnostico.py` |
| `AC-113` | `US-26` | Dado um cenário equivalente a `GAB-AI-06` (§13.10) — `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` calculada por `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (fatia 4B, não mais recebida por parâmetro de teste) resultando em `20.000`; `CAIXA_RECOMENDADO=5.000`; `INVESTIMENTOS_RECOMENDADOS=7.000`; `EXTRAORDINARIOS_RECOMENDADOS=0`; `ATIVOS_RECOMENDADOS=0`; `RESERVA_MOBILIZAVEL=10.000` —, quando `calcular_plano` for executado ponta a ponta, então `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO = 20.000`, reproduzindo o mesmo resultado que `GAB-AI-06` já provava como função pura isolada |
| `AC-114` | `US-26` | Dado um cenário equivalente a `GAB-AI-07` — `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` real resultando em `10.000` e recursos estrategicamente recomendados somando `25.000` —, quando `calcular_plano` for executado ponta a ponta, então `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO = 10.000`, nunca `25.000` |
| `AC-115` | `US-26` | Dado o código-fonte desta fatia, quando for auditado, então `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` é produzido exclusivamente por composição das funções puras já existentes e verificadas de `engine/ataque_imediato.py` (Rodada 3) e `engine/gates.py` (fatia 4B) — nenhuma fórmula nova, nenhuma reimplementação paralela da §14.2.4/§13.3 é escrita nesta fatia |
| `AC-116` | `US-26` | Dados `GAB-A`, `GAB-B`, `GAB-C` e os cinco invariantes reexecutados após esta fatia, quando cada um for verificado, então método recomendado, `ORDEM_QUITACAO`, gates, `STATUS_METODO`, número de meses, `mes_primeira_vitoria`, custo total e prazo total permanecem **idênticos** aos valores anteriores a esta fatia — a única mudança observável admitida é `ATAQUE_IMEDIATO_RECOMENDADO` deixar de ser `0` e passar a ser o valor real, exatamente como esta fatia pretende (efeito desejado, não regressão) |
| `AC-117` | `US-26` | Dada a docstring de `calcular_diagnostico` e a declaração de `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` (`engine/diagnostico.py`), quando forem lidas após esta fatia, então nenhuma delas afirma que o campo é placeholder, que `OQ-29` está aberta ou que nenhuma decisão do motor o lê — a docstring registra a fórmula real aplicada e referencia `RF-66`/`RF-67`/§14.2.4 (`RF-69`) |

## 5. Non-Functional Requirements

- **Precisão:** aritmética decimal exata em todo o cálculo interno. Ponto
  flutuante binário é proibido para valores monetários — a tolerância de
  `± R$ 0,05` da seção 10.3 existe para arredondamento de exibição, não para
  absorver erro de representação.
- **Tolerância de homologação:** `± R$ 0,05` exclusivamente em valores monetários
  acumulados. Tolerância **zero** para método recomendado, ordem, gates, status,
  número de meses, primeira vitória, classificação, dupla contagem, aplicação de
  resíduo, gatilho de recálculo, `D*`, e `NAO_APLICAVEL` versus `PROVISORIO`.
- **Determinismo:** mesma entrada e mesma versão de parâmetros produzem
  exatamente a mesma saída. Nenhuma dependência de relógio, ordem de iteração
  não especificada ou aleatoriedade.
- **Custo de simulação:** o benefício marginal exige simular duas trajetórias por
  dívida elegível a cada ranqueamento. O motor deve suportar carteiras de pelo
  menos 30 dívidas dentro do horizonte de 10 anos sem degradação inaceitável.
- **Auditabilidade:** toda decisão de ordem carrega a justificativa e os valores
  que a produziram. Um revisor humano precisa conseguir refazer o caminho.
- **Rastreabilidade de versão:** `ENGINE_VERSION` e `PARAMETROS_VERSION`
  carimbados em toda saída.
- **Horizonte:** simulação limitada por `P_HORIZONTE_MAXIMO_SIMULACAO`
  (10 anos), com alerta a partir de `P_HORIZONTE_ALERTA` (5 anos).
- **Observabilidade:** cada recálculo registra o evento que o disparou, o estado
  antes e depois, e o motivo — sem isso o snapshot da regra `V-02` não fecha.
- **Compatibilidade de contrato (Rodada 2):** a extensão de `AcaoRequerida` e
  `Diagnostico` (`RF-28` a `RF-35`) é aditiva por campo, exceto `RF-31`
  (relaxamento de `DIVIDA_ID`), que é mudança de invariante e exige varredura
  de todo consumidor interno. Tolerância **zero** para a saída de `ORDEM_ACOES`
  nos casos tocados por `RF-32` — mesma régua da seção 10.3 da canônica já
  citada em `RF-12`, não uma tolerância nova.
- **Pureza (Rodada 3).** As funções de cálculo de `RF-43` a `RF-47` recebem
  todas as suas entradas por parâmetro e não consultam `EstadoFinanceiro`,
  `Diagnostico`, relógio, arquivo ou variável global. É essa propriedade que
  torna `GAB-AI-01` a `GAB-AI-07` verificáveis antes de `OQ-26`/`OQ-29` serem
  respondidas, e ela é requisito, não estilo.
- **Tolerância dos `GAB-AI` (Rodada 3):** **zero**. São valores exatos de
  `MIN`/`MAX`/soma, sem acumulação de arredondamento — a faixa de `± R$ 0,05`
  da seção 5 vale para monetário acumulado ao longo de meses, situação que não
  ocorre em nenhum dos oito.
- **Compatibilidade de contrato (Rodada 3):** `RF-36` a `RF-40` são aditivos
  por campo em `EstadoFinanceiro`, mas toda adição muda `hash_inputs`
  (`engine/snapshot.py`) e portanto o hash de todo snapshot. `RF-41` (mudança
  de tipo de `Diagnostico.RESERVA_MOBILIZAVEL`) é **quebra de contrato**, não
  adição, e exige varredura de consumidores no mesmo padrão de `RF-31`.
- **Rastreabilidade normativa (Rodada 3):** cada função de `RF-43` a `RF-47`
  cita, em nome ou comentário, a subseção da §13 que implementa (§13.1, §13.2,
  §13.3, §13.4), no mesmo padrão da convenção "regra citada no código" do
  `sdd.config.md` §4.
- **Ordem de precedência é normativa, não sugestão (Rodada 4).** As seis
  regras de `classificar_investimento` (`RF-53`) e as regras de
  `classificar_ativo_fisico` (`RF-54`/`RF-55`/`RF-56`) são avaliadas em ordem
  estrita — a implementação prova isso por teste que force um item elegível
  por mais de uma regra a cair na primeira que se aplica (`AC-95`, `AC-96`),
  não apenas verifica o resultado final de cada caso isolado.
- **Pureza (Rodada 4).** `classificar_investimento`, `classificar_ativo_fisico`,
  `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO` e `_DISPONIVEL` recebem todas as
  suas entradas por parâmetro e não consultam `EstadoFinanceiro`,
  `Diagnostico`, relógio, arquivo ou variável global — mesma propriedade que
  tornou `GAB-AI-*` verificáveis na Rodada 3, aqui exigida para que os sete
  `GAB-NFI-06` a `GAB-NFI-12` (desta fatia, de doze totais na §14.16) sejam
  verificáveis como testes de função pura.
- **Rastreabilidade normativa (Rodada 4):** cada função desta fatia cita, em
  nome ou comentário, a subseção da §14 que implementa (§14.3, §14.3.1,
  §14.4–§14.9, §14.12), no mesmo padrão já exigido nas Rodadas 2 e 3.
- **Dados desconhecidos nunca viram zero silenciosamente (Rodada 4).**
  `SALDO_PASSIVO_VINCULADO` desconhecido, `CUSTOS_ESTIMADOS_DESMOBILIZACAO`
  desconhecido e as entradas que tornam a classificação indecidível (§14.3.1
  Regra 2, §14.4.2) propagam o estado desconhecido — nunca `0` nem uma
  classificação "otimista" por omissão. Mesmo princípio já exigido para
  `RESERVA_MOBILIZAVEL` na Rodada 3 (`RF-43`), reafirmado aqui.
- **Compatibilidade de contrato (Rodada 4 — fatia 4A):** `RF-59` é **quebra
  de contrato**, não adição — `ItemAtivo.CLASSIFICACAO_MOBILIZACAO` e
  `ItemInvestimento.CLASSIFICACAO_MOBILIZACAO` deixam de ser argumento de
  construtor e passam a ser derivados, no mesmo padrão de cuidado de `RF-31`
  e `RF-41`: varredura de todo consumidor interno (`AC-98`), `mypy --strict`
  como rede de segurança, e reescrita (não relaxamento) do teste estático
  que proibia a derivação (`RF-60`, `AC-97`). A mudança altera `hash_inputs`
  de todo item de investimento/ativo construído a partir daqui — mesma
  observação de coordenação já feita nas Rodadas 2 e 3, tratada na seção 9.
- **Ordem de precedência é normativa, não sugestão (Rodada 4 — fatia 4B).**
  Os cinco ramos de `NECESSIDADE_IMEDIATA_DIVIDA` (`RF-64`) são avaliados em
  ordem estrita — Gate 1 pendente vence Gate 3 pendente vence ação financeira
  imediata vence status estratégico — e a implementação prova isso por teste
  que force uma dívida elegível por mais de uma condição a cair na primeira
  que se aplica (`AC-106`), não apenas o resultado final de cada caso
  isolado. Mesmo padrão exigido para `classificar_investimento`/
  `classificar_ativo_fisico` na fatia 4A.
- **`VALOR_RELEVANTE_PARA_QUITACAO` entra integral, nunca fração
  "vantajosa" (Rodada 4 — fatia 4B).** A §14.1.2 é explícita ("REGRA
  CANÔNICA"): `NECESSIDADE_IMEDIATA_DIVIDA` responde "quanto poderia ser
  usado agora", não "quanto vale a pena disponibilizar" — essa segunda
  pergunta é `ATAQUE_IMEDIATO_RECOMENDADO` (fatia 4C, fora de escopo). As
  duas perguntas não podem ser confundidas na implementação desta fatia
  (`AC-107`).
- **Pureza (Rodada 4 — fatia 4B).** `NECESSIDADE_IMEDIATA_DIVIDA` e
  `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` recebem todas as suas entradas
  por parâmetro (`GATE_PENDENTE`, `DIVIDA_STATUS_ESTRATEGICO`,
  `VALOR_ACAO_FINANCEIRA_IMEDIATA`, `VALOR_RELEVANTE_PARA_QUITACAO`) e não
  consultam `EstadoFinanceiro`, `Diagnostico`, relógio, arquivo ou variável
  global — mesma propriedade que tornou os gabaritos das Rodadas 3 e 4A
  verificáveis antes da integração em `calcular_diagnostico`. É essa
  propriedade que torna `GAB-NFI-01` a `GAB-NFI-05` executáveis nesta fatia
  sem depender de `OQ-43` (fatia 4C).
- **Dados desconhecidos nunca viram zero silenciosamente (Rodada 4 — fatia
  4B).** `VALOR_ACAO_FINANCEIRA_IMEDIATA` desconhecido nunca é somado como
  `0` a `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`; o total sinaliza
  incompletude material em vez disso (`AC-108`). Mesmo princípio já exigido
  para `RESERVA_MOBILIZAVEL` (Rodada 3) e para `SALDO_PASSIVO_VINCULADO`/
  `CUSTOS_ESTIMADOS_DESMOBILIZACAO` (Rodada 4, fatia 4A), reafirmado aqui.
- **Rastreabilidade normativa (Rodada 4 — fatia 4B):** cada função desta
  fatia cita, em nome ou comentário, a subseção da §14 que implementa
  (§14.1, §14.1.1, §14.2.1, §14.2.2, §14.2.3), no mesmo padrão já exigido
  nas Rodadas 2, 3 e na fatia 4A.
- **Compatibilidade de contrato (Rodada 4 — fatia 4B):** `RF-61` é **quebra
  de contrato**, não adição — `AcaoRequerida` ganha um campo monetário novo
  que nenhum consumidor hoje espera, no mesmo padrão de cuidado de `RF-31`,
  `RF-41` e `RF-59`: varredura de todo consumidor interno do motor (`AC-110`),
  `mypy --strict` como rede de segurança, e sinalização explícita ao slug
  `app-aluno` — que já consome `AcaoRequerida` desde a Rodada 2 (`RF-28` a
  `RF-35`) e tem hash congelado dependente do formato desta dataclass. A
  mudança altera `hash_inputs` de toda `AcaoRequerida` construída a partir
  daqui — mesma observação de coordenação já feita nas Rodadas 2, 3 e na
  fatia 4A, tratada na seção 9.
- **Trava de dupla contagem é requisito verificável, não efeito colateral
  esperado (Rodada 4 — fatia 4B).** `RF-65`/`AC-104`/`AC-111` exigem prova
  positiva de que `VALOR_ACAO_FINANCEIRA_IMEDIATA` e
  `VALOR_RELEVANTE_PARA_QUITACAO` da mesma dívida nunca são somados no mesmo
  cálculo de `NECESSIDADE_IMEDIATA_DIVIDA` — auditoria de código, não apenas
  teste de caso feliz.
- **Composição, não reimplementação (Rodada 4 — fatia 4C).** `RF-66`/`RF-67`
  exigem que `ATAQUE_IMEDIATO_RECOMENDADO` real seja produzido só pela
  composição das funções puras já homologadas nas fatias anteriores —
  nenhuma fórmula é reescrita, reaproximada ou "simplificada" no ponto de
  integração. `AC-115` audita isso por leitura de código, não apenas pelo
  resultado numérico.
- **Não-regressão é requisito desta fatia, com uma exceção nomeada
  (Rodada 4 — fatia 4C).** Ao contrário de toda fatia anterior, em que
  gabarito mudando de valor era sinal de regressão, aqui a mudança de
  `ATAQUE_IMEDIATO_RECOMENDADO` de `0` fixo para o valor real é o **efeito
  desejado**. Tolerância zero se aplica a todos os demais campos de
  `Diagnostico`/`SnapshotOrdem` — método, ordem, custo, prazo, gates, status,
  `D*` — que não podem mudar (`AC-116`). A régua não muda; o que muda é qual
  campo está autorizado a divergir.
- **Rastreabilidade normativa (Rodada 4 — fatia 4C):** a implementação desta
  fatia cita, em nome ou comentário, §14.2.4 como a fonte da fórmula de
  integração, no mesmo padrão já exigido nas Rodadas 2, 3 e nas fatias 4A/4B.

## 6. Edge Cases

| ID | Situação | Comportamento esperado |
| --- | --- | --- |
| `EC-01` | Resíduo do ataque existe, mas não há mais dívida elegível | Registrar como `ATAQUE_NAO_UTILIZADO` e manter como caixa do usuário (`A-04`) |
| `EC-02` | Dívida se encerra apenas com o pagamento normal, sem ataque | Dispara recálculo da ordem como qualquer outra quitação (`R-01`) |
| `EC-03` | Nenhuma dívida atende às três tolerâncias do Híbrido | `CENARIO_HIBRIDO` = `NAO_APLICAVEL` e `ORDEM_HIBRIDA` = `NAO_APLICAVEL` (`H-08`) |
| `EC-04` | Híbrido `NAO_APLICAVEL` com Bola de Neve economicamente próxima | Não aciona revisão humana obrigatória (`S-05`) |
| `EC-05` | Incompatibilidade comportamental grave e nenhuma alternativa próxima | `STATUS_METODO` = `PROVISORIO` e `REVISAO_HUMANA_OBRIGATORIA` = SIM (`S-04`) |
| `EC-06` | Dívida rotativa sem saldo e sem parcela conhecidos | `INFORMACAO_PENDENTE`; trajetória `BLOQUEADO` (`GAB-03`) |
| `EC-07` | Inventário de dívidas incompleto | Diagnóstico parcial; totais parciais; nenhum cronograma definitivo (`GAB-02`) |
| `EC-08` | Alteração meramente cadastral ou cosmética | Não constitui `EVENTO_RECALCULO` (`R-04`) |
| `EC-09` | Evento material ocorre e o recálculo confirma o mesmo método e a mesma `D*` | Gerar novo snapshot mesmo assim (`R-05`) |
| `EC-10` | Saldo observado positivo produzido por dívida não paga | Não é sobra. `MODO_ESTABILIZACAO` = SIM, `CAPACIDADE_ATAQUE_ATUAL` = 0 (`GAB-A`) |
| `EC-11` | Economia identificada e aceita, mas ainda não implementada | Entra em `CAPACIDADE_ATAQUE_POTENCIAL`, nunca no cronograma-base (`GAB-B`) |
| `EC-12` | Seguro embutido na parcela | Informacional; não é somado de novo (`GAB-01`) |
| `EC-13` | Simulação ultrapassa o horizonte máximo sem quitar tudo | Encerrar em `P_HORIZONTE_MAXIMO_SIMULACAO` e sinalizar |
| `EC-14` | Valor de quitação conhecido, porém com validade desconhecida | Não tratar como vigente; usar `SALDO_DEVEDOR_ATUAL` e gerar `PRIORIDADE_INFORMACAO` se a diferença puder alterar materialmente a decisão |
| `EC-15` | A própria quitação é a ação que contém o risco, e é executável | Pode receber prioridade excepcional, com justificativa expressa — não por ser de risco alto, mas por conter o risco (Gate 2) |
| `EC-16` | Oportunidade de desconto vigente em uma dívida | Avaliada antes da ordem-base, mas desconto **não** implica primeiro lugar automático (Gate 4) |
| `EC-17` | Todas as dívidas bloqueadas pelos gates, nenhuma elegível | Não há alvo. O plano vira ação, não ataque: `ORDEM_ACOES` primeiro, cronograma condicional |
| `EC-18` | Dívida quitada que não estava sendo paga de fato | `VALOR_FLUXO_LIBERADO` = 0. Não libera a parcela contratual fictícia |
| `EC-19` | Empate material de 1% entre três ou mais cenários | Todos os empatados concorrem, e vence o de menor `PRAZO_TOTAL` |
| `EC-20` | `ECONOMIA_POTENCIAL_IMEDIATA > 0` e, no mesmo snapshot, uma ou mais dívidas bloqueadas pelo Gate 1 | `ORDEM_ACOES` contém tanto a(s) `AcaoRequerida` de `TIPO_ACAO="INFORMACAO"` quanto a de `TIPO_ACAO="ECONOMIA"` — a emissão da ação de economia é independente do estado dos gates de dívida (`RF-33`) |
| `EC-21` | Consumidor interno do motor lê `AcaoRequerida.DIVIDA_ID` sem checar `None`, após `RF-31` | Falha de tipagem/execução deve aparecer no comando `build` (`mypy --strict`) antes de chegar a runtime — não é comportamento silencioso aceitável |
| `EC-22` | Dívida bloqueada simultaneamente pelos dois ramos possíveis do Gate 1 (hipoteticamente) | Não ocorre: os dois ramos de `aplicar_gate_1_informacao` são mutuamente exclusivos por construção (o segundo só é avaliado se o primeiro não bloqueou) — `CAMPO_PENDENTE` sempre resolve para exatamente um dos dois valores do domínio, nunca ambíguo |

### Rodada 3 (2026-09-07) — fatias 3A e 3B

| ID | Situação | Comportamento esperado |
| --- | --- | --- |
| `EC-23` | `RESERVA_EXISTE = NAO` porém com `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` preenchido (entrada inconsistente) | `RESERVA_MOBILIZAVEL = 0` — a Regra 1 da §13.1 é avaliada **antes** da Regra 2 e vence; o valor informado é ignorado, não somado (`RF-43`) |
| `EC-24` | `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` negativo | `MAX(0, ...)` da Regra 2 zera a parcela antes do `MIN`; `RESERVA_MOBILIZAVEL` nunca é negativa (`RF-43`) |
| `EC-25` | `RESERVA_TOTAL` desconhecida, com valor máximo informado conhecido | `RESERVA_MOBILIZAVEL` = desconhecida (Regra 3), não o valor informado — a Regra 3 tem precedência sobre a Regra 2 quando o total é desconhecido (`RF-43`) |
| `EC-26` | `RESERVA_MOBILIZAVEL` desconhecida e `NECESSIDADE_RESIDUAL > 0` | `RESERVA_RECOMENDADA = 0` até existir decisão válida, e a pendência é registrada — nunca convertida silenciosamente em zero como informação (`RF-43`, `RF-46`) |
| `EC-27` | Coleções de investimentos, ativos e recursos extraordinários todas vazias e `DINHEIRO_DISPONIVEL = 0` | `ATAQUE_IMEDIATO_POTENCIAL` e `ATAQUE_IMEDIATO_RECOMENDADO` valem `0`; nenhum erro, nenhum estado desconhecido fabricado (`RF-44`, `RF-47`) |
| `EC-28` | `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = 0` com recursos recomendáveis positivos | `ATAQUE_IMEDIATO_RECOMENDADO = 0` — a §13.5 proíbe recomendar recurso sem destinação financeira elegível (`RF-47`, `RF-48`) |
| `EC-29` | Todos os componentes não protetivos já cobrem a necessidade elegível | `NECESSIDADE_RESIDUAL = 0` e `RESERVA_RECOMENDADA = 0` — a reserva é o último componente e só cobre residual (`RF-46`) |
| `EC-30` | Ativo classificado `MOBILIZACAO_COM_RESSALVAS` com valor líquido realizável alto | Não entra em `ATIVOS_RECOMENDADOS` nem em `ATAQUE_IMEDIATO_POTENCIAL` — as ressalvas não são resolvidas automaticamente pelo motor (`RF-44`, `RF-45`) |
| `EC-31` | Item de entrada chega sem classificação de mobilização | Erro de contrato na construção do estado: a classificação é campo obrigatório por item (`RF-40`), pois derivá-la está fora de escopo (`OQ-26`) — o motor não escolhe uma classe por omissão — **revogado pela Rodada 4 (2026-09-09)**: `OQ-26` foi respondida, `CLASSIFICACAO_MOBILIZACAO` passa a ser derivada (`RF-59`), e "chegar sem classificação" deixa de ser um erro de contrato aplicável — o erro passa a ser outro (item chega sem os campos brutos que a classificação exige). Ver `EC-32` |

### Rodada 4 (2026-09-09) — fatia 4A

| ID | Situação | Comportamento esperado |
| --- | --- | --- |
| `EC-32` | Item de entrada (`ItemAtivo`/`ItemInvestimento`) chega sem os campos brutos que `classificar_investimento`/`classificar_ativo_fisico` exigem (ex.: sem `POSSIBILIDADE_VENDA`, sem `ESSENCIALIDADE`) | Erro de contrato na construção do estado — o motor não deriva classificação a partir de campo ausente; substitui `EC-31` como o erro de contrato aplicável após `RF-59` |
| `EC-33` | Investimento satisfaz simultaneamente a Regra 1 (bloqueio) e a Regra 4 (líquido/disponível/sem custo) de `classificar_investimento` | Prevalece a Regra 1 — `NAO_MOBILIZAR` — por ser avaliada primeiro na ordem de precedência estrita (`RF-53`, `AC-95`) |
| `EC-34` | Ativo físico `ESSENCIAL` com `POSSIBILIDADE_VENDA = JA_PRETENDE` (a mais favorável à venda) | `MOBILIZACAO_COM_RESSALVAS`, nunca `MOBILIZACAO_RECOMENDAVEL` — essencialidade prevalece sobre qualquer disposição de venda (§14.5, `RF-54`) |
| `EC-35` | Ativo físico `IMPORTANTE`/`PARCIAL` com `POSSIBILIDADE_VENDA = NAO` | Fora do domínio coberto por §14.6 (que só trata `EXTREMO`/`TALVEZ`/`SIM`/`JA_PRETENDE`); `POSSIBILIDADE_VENDA = NAO` é sempre `NAO_MOBILIZAR` por §14.4.1, avaliada antes da ramificação por essencialidade — a ordem de precedência (bloqueio primeiro) evita a lacuna aparente |
| `EC-36` | `VALOR_ESTIMADO_ATIVO` do próprio ativo é desconhecido | `VALOR_LIQUIDO_REALIZAVEL_ATIVO` = desconhecido por propagação direta (§14.14 `deriveValorLiquidoRealizavelAtivo`, primeira guarda) — nem passivo nem custo chegam a ser avaliados |
| `EC-37` | Investimento do tipo comumente associado a alta liquidez (ex.: poupança) com `LIQUIDEZ_INVESTIMENTOS = MAIS_30` na entrada | Classificado por `LIQUIDEZ_INVESTIMENTOS` real, não pelo tipo — resultado `MOBILIZACAO_COM_RESSALVAS` (Regra 6), contrariando a presunção "poupança = recomendável" que a §14.3.1.1 proíbe fazer |
| `EC-38` | Consumidor interno do motor constrói `ItemAtivo`/`ItemInvestimento` passando `CLASSIFICACAO_MOBILIZACAO` como argumento após `RF-59` | Falha de tipagem deve aparecer no comando `build` (`mypy --strict`) antes de chegar a runtime, no mesmo padrão de `EC-21` para `RF-31` — não é comportamento silencioso aceitável |
| `EC-39` | Ativo físico do tipo veículo, `ESSENCIALIDADE=NAO_ESSENCIAL`, `POSSIBILIDADE_VENDA em {SIM, JA_PRETENDE}` — o único ramo de `classificar_ativo_fisico` que dependeria de `FLUXO_LIQUIDO_RECORRENTE_ATIVO` de veículo | Nenhuma classificação é produzida: bloqueado por `OQ-38` (ausência estrutural de `RENDA_RECORRENTE_VEICULO`/equivalente na coleta). **Não** produz `MOBILIZACAO_POSSIVEL` pela via de "efeito desconhecido" — essa leitura (`OQ-42` no discovery) foi deliberadamente não adotada (`RF-56`, seção 9). Os demais cinco ramos de veículo (bloqueio, essencial, importante/parcial, não essencial com venda extrema/talvez) não são afetados e permanecem classificáveis |

### Rodada 4 (2026-09-09) — fatia 4B

| ID | Situação | Comportamento esperado |
| --- | --- | --- |
| `EC-40` | Dívida com Gate 1 **e** Gate 3 pendentes simultaneamente | `NECESSIDADE_IMEDIATA_DIVIDA = 0` — Gate 1 é avaliado primeiro e já decide o resultado; Gate 3 nunca chega a ser consultado, mas o resultado seria o mesmo se fosse (`RF-64`, ordem de precedência) |
| `EC-41` | Dívida com Gate 1 e Gate 3 resolvidos, ação financeira imediata de Gate 2/4 existente mas **não** executável agora (ex.: proposta expirada) | Não entra no terceiro ramo de `RF-64` — cai para o quarto ramo (status estratégico) ou para `0`, conforme `DIVIDA_STATUS_ESTRATEGICO`; uma ação inexecutável não produz `VALOR_ACAO_FINANCEIRA_IMEDIATA` |
| `EC-42` | Ação financeira imediata de Gate 2/4 executável agora, mas de valor `0` (ex.: regularização sem custo) | `NECESSIDADE_IMEDIATA_DIVIDA = 0` para essa dívida naquele estado — valor `0` é um valor conhecido válido, distinto de `DESCONHECIDO`; não aciona a sinalização de incompletude de `RF-63`/`AC-108` |
| `EC-43` | `DIVIDA_STATUS_ESTRATEGICO` fora de `{PRONTA_PARA_ORDENACAO, EM_ATAQUE}` (ex.: `EM_ANALISE`, `INTERVENCAO_PENDENTE`) e nenhum gate pendente, nenhuma ação financeira imediata | `NECESSIDADE_IMEDIATA_DIVIDA = 0` — quinto ramo (senão) de `RF-64`; a dívida não contribui ao teto de ataque imediato enquanto não atingir um dos dois status elegíveis |
| `EC-44` | Dívida resolve o gate que a direcionava a ação financeira imediata (Gate 2/4 concluído) em um snapshot posterior | A dívida deixa de contribuir via `VALOR_ACAO_FINANCEIRA_IMEDIATA` e volta ao estoque ordinário: passa a contribuir por `VALOR_RELEVANTE_PARA_QUITACAO` (quarto ramo), se o status estratégico for elegível — nunca soma os dois valores no mesmo snapshot (`RF-65`, §14.2.3) |
| `EC-45` | Todas as dívidas do inventário com `NECESSIDADE_IMEDIATA_DIVIDA = 0` (nenhuma elegível) | `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = 0` — soma vazia é `0` legitimamente, distinto do caso de incompletude por valor desconhecido (`EC-46`); não é erro nem sinalização de pendência |
| `EC-46` | Ao menos uma dívida do inventário com `NECESSIDADE_IMEDIATA_DIVIDA = DESCONHECIDO` (ação prioritária de valor desconhecido) e as demais com valores conhecidos | `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` sinaliza incompletude material — a soma das dívidas conhecidas não é apresentada como o teto definitivo, e a dívida desconhecida não entra como `0` (`RF-64`, `AC-108`) |
| `EC-47` | Consumidor interno do motor constrói `AcaoRequerida(...)` sem o novo campo monetário, ou lê o campo presumindo que ele nunca é `DESCONHECIDO`/ausência de desembolso, após `RF-61` | Falha de tipagem deve aparecer no comando `build` (`mypy --strict`) antes de chegar a runtime, no mesmo padrão de `EC-21`/`EC-38` para `RF-31`/`RF-59` — não é comportamento silencioso aceitável |

### Rodada 4 (2026-09-10) — fatia 4C

| ID | Situação | Comportamento esperado |
| --- | --- | --- |
| `EC-48` | `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` resulta em `DESCONHECIDO` para o inventário (`AC-108`, ao menos uma dívida com ação prioritária de valor desconhecido) | `ATAQUE_IMEDIATO_RECOMENDADO` **não** pode ser produzido como `Dinheiro` certo tratando o desconhecido como `0` silenciosamente; o mecanismo concreto de propagação (retipar o campo, sinalizar `STATUS_METODO=PROVISORIO`, ou outro) é decisão do plano técnico (`OQ-44`), mas o requisito de não fabricar um número certo a partir de um insumo incerto vale já nesta spec |
| `EC-49` | Todas as dívidas do inventário com `NECESSIDADE_IMEDIATA_DIVIDA = 0` (nenhuma elegível, `EC-45`) e recursos estrategicamente recomendados positivos | `ATAQUE_IMEDIATO_RECOMENDADO = 0` — mesma regra de `EC-28` (Rodada 3), agora observável ponta a ponta em `Diagnostico` real, não apenas na função pura isolada |
| `EC-50` | Consumidor externo do motor (ex.: `app-aluno`, relatório) lê `Diagnostico.ATAQUE_IMEDIATO_RECOMENDADO` esperando ainda o valor fixo `0` de antes desta fatia | Não é comportamento a preservar: o placeholder nunca foi contrato, era valor de espera documentado como tal (`AC-85` parcialmente satisfeito até esta fatia); a mudança é sinalizada a `app-aluno` como o restante das mudanças de contrato desta rodada (seção 9) |

## 7. Assumptions

- O motor recebe um estado financeiro já coletado e validado. Coleta é escopo de
  `questionario`, não deste slug.
- Os parâmetros da seção 8 estão disponíveis em fonte externa legível em tempo de
  execução, na versão `PARAMETROS_VERSION` 1.0.1.
- Os três gabaritos numéricos da seção 10 foram recomputados mês a mês com
  precisão integral e são a referência oficial. Os valores anteriores, que
  assumiam descarte do resíduo, estão revogados (errata `E-05` e `E-07`).
- A metodologia está fechada. Regra que pareça errada é reportada ao especialista,
  não corrigida no código.
- As definições da seção 11 desta spec são normativas para a implementação
  enquanto a canônica não é atualizada para v1.0.2.
- **Rodada 2.** As decisões de *o quê* mudar em `AcaoRequerida` e
  `Diagnostico` já foram tomadas pelo especialista do método e estão fechadas
  em `specs/app-aluno.spec.md` §10 (`OQ-10`, `OQ-13`, `OQ-14`, `OQ-15`, `OQ-17`,
  `OQ-18`). Este slug não reabre nenhuma dessas decisões — apenas as
  transcreve para código e revalida o que a mudança toca.
- O docstring atual de `AcaoRequerida` já previa a extensão: *"a estrutura
  completa de `ORDEM_ACOES` (...) é consolidada em `T-32`, que pode estender
  esta dataclass com novos campos sem quebrar o contrato aqui fixado"*. A
  extensão desta rodada é o caminho que o próprio motor deixou aberto, não uma
  violação da regra de congelamento de `engine/`.
- `TIPO_ACAO` e `ACAO_ID` não têm hoje linha no dicionário de variáveis da
  canônica (§11) — não há domínio publicado a transcrever além do que
  `OQ-13` já fechou; o domínio de quatro valores usado em `RF-29` é a fonte
  única para esses dois identificadores.
- `RESERVA_MOBILIZAVEL`/`ATAQUE_IMEDIATO_RECOMENDADO` não existem hoje em
  nenhum lugar de `engine/*.py` — só aparecem em condição de exibição e em
  prosa de "uso pelo motor" na canônica, nunca implementados como campo real
  antes desta rodada.

### Rodada 3 (2026-09-07) — fatias 3A e 3B

- **A aritmética da §13 está fechada; as origens de dado não.** A §13 é
  normativa e congelada para as fórmulas que enuncia, mas não diz como cada
  parcela chega ao motor. Esta rodada modela as origens de dado como
  **contrato de entrada** e implementa apenas as fórmulas literais — nenhuma
  regra de derivação nova é inventada.
- **`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` é entrada, não derivada
  (`RF-48`).** A §13.5 a define só em prosa, sem fórmula fechada, e `OQ-29`
  segue pendente do especialista. Os enunciados de `GAB-AI-06` e `GAB-AI-07`
  **fornecem o valor** ("= 20.000", "= 10.000"), o que só é aproveitável se a
  variável for parâmetro das funções em vez de valor derivado internamente. É
  essa decisão de assinatura — e não uma fórmula adivinhada — que torna a
  fatia 3B executável sem o especialista. Quando `OQ-29` for respondida, a
  derivação real passa a alimentar esse mesmo parâmetro, sem alterar as
  funções de `RF-46`/`RF-47`.
- **A classificação de mobilização entra já classificada (`RF-40`).** A
  canônica (`piq-app-spec.md:2614`) fecha que as quatro classes são "derivadas
  pelo motor, nunca perguntadas", mas nenhuma fonte publica a *regra* de
  derivação (`OQ-26`). O **domínio** dos quatro valores está fechado pela §13 e
  é implementável já; a regra não é. Enquanto isso, a classificação é campo
  obrigatório por item no contrato de entrada.
- **`OQ-24` foi decidida pelo usuário em 2026-09-07** e é decisão técnica, não
  metodológica: o escopo verificado é **uma única linha**
  (`collection/registros/bloco-04.yaml:156`). Os outros 15 usos de
  `RESERVA_MOBILIZAVEL` no repositório já se referem ao campo derivado de
  `Diagnostico` e não mudam. O `ID` `B4.03A` não muda — `sdd.config.md` §6
  exige estabilidade do `ID` da pergunta, não do `VARIAVEL_GRAVADA`.
- **A coleta não é dependência bloqueante.** As 49 perguntas do Bloco 4 e as
  perguntas de recurso extraordinário do Bloco 3 já estão transcritas em
  `collection/registros/`. O que falta é o transporte até `EstadoFinanceiro`
  (`OQ-37`, do slug `app-aluno`) e as regras de derivação — não a
  matéria-prima.
- **Capacidade e ataque imediato são grandezas ortogonais.** Capacidade é
  fluxo mensal derivado de `RESULTADO_MENSAL_ATUAL`; ataque imediato é estoque
  patrimonial. A §13 não menciona nenhuma das capacidades existentes exceto
  `MODO_ESTABILIZACAO`, e apenas como trava. Esta rodada não altera nenhuma
  capacidade nem o cronograma-base. O único ponto de contato não resolvido
  (`ECONOMIA_POTENCIAL_IMEDIATA`) está registrado em `OQ-31` e não é tocado
  aqui.

### Rodada 4 (2026-09-09) — fatia 4A

- **`OQ-26` e `OQ-27` estão fechadas para o que a §14 define.** A regra de
  derivação de `CLASSIFICACAO_ATIVO` (investimento e ativo físico) e a
  fórmula de `VALOR_LIQUIDO_REALIZAVEL_ATIVO`/`_DISPONIVEL` são normativas e
  congeladas a partir de 2026-09-09. Esta fatia não inventa nada além do que
  a §14 já fecha — ela apenas decide o **mecanismo de implementação** (onde a
  classificação passa a viver dentro de `ItemAtivo`/`ItemInvestimento`), que
  é decisão técnica nossa, não metodológica (`sdd.config.md` §6).
- **O mecanismo concreto de derivação (`OQ-40`) é decisão técnica, não desta
  spec.** O discovery (Rodada 4, §2) identifica duas opções — campo derivado
  via `object.__setattr__` no `__post_init__`, preservando a leitura
  `item.CLASSIFICACAO_MOBILIZACAO`; ou função separada nunca armazenada na
  dataclass, mudando a forma de leitura de todo consumidor — sem decidir
  qual. `RF-59` exige apenas que a mudança receba o mesmo rigor de varredura
  de consumidores que `RF-31`/`RF-41` já estabeleceram como padrão desta
  base, qualquer que seja o mecanismo escolhido no plano técnico.
- **Veículo permanece classificável em cinco das seis regras de ativo
  físico.** A lacuna de `OQ-38` (ausência de `RENDA_RECORRENTE_VEICULO` na
  coleta) só afeta o ramo `NAO_ESSENCIAL` + `POSSIBILIDADE_VENDA` em
  `{SIM, JA_PRETENDE}` — os demais ramos (`NAO`, `ESSENCIAL`,
  `IMPORTANTE`/`PARCIAL`, `NAO_ESSENCIAL` + `EXTREMO`/`TALVEZ`) não dependem
  de `FLUXO_LIQUIDO_RECORRENTE_ATIVO` e são implementáveis para veículo sem
  ressalva. **Esta fatia não adota a leitura que o discovery chamou de
  `OQ-42`** (tratar a ausência estrutural da variável de renda de veículo
  como equivalente a "efeito recorrente desconhecido" e, por isso, produzir
  `MOBILIZACAO_POSSIVEL` automaticamente) — decisão explícita de não
  contornar `OQ-38` por conta própria, registrada no pedido desta fatia. O
  ramo específico de veículo não essencial com venda aceita fica **bloqueado**
  (ver seção 9), não implementado sob uma leitura alternativa não confirmada
  pelo especialista.
- **`VALOR_LIQUIDO_REALIZAVEL_ATIVO` e `_DISPONIVEL` são variáveis distintas,
  não sinônimos (§14.12.2, "REGRA CANÔNICA").** Um pode ser negativo; o outro
  nunca pode. Isso não é detalhe de implementação — é a razão de existirem
  como dois nomes diferentes na fonte normativa, e `RF-57`/`AC-94` tratam
  essa distinção como requisito e critério separados, não como uma única
  fórmula com dois nomes.
- **Esta fatia não resolve `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`,
  `NECESSIDADE_IMEDIATA_DIVIDA`, nem toca `calcular_diagnostico`, `Divida`
  ou `AcaoRequerida`.** Essas mudanças são as fatias 4B e 4C (seção 9),
  ambas dependentes de questões próprias (`OQ-39`, `OQ-41`, `OQ-43`) que esta
  fatia não decide nem antecipa.

### Rodada 4 (2026-09-09) — fatia 4B

- **Fatia 4A (`RF-53` a `RF-60`) está concluída e verificada** antes do
  início desta fatia. `classificar_investimento`, `classificar_ativo_fisico`
  e a fórmula do valor líquido realizável já existem no motor; esta fatia
  não as reabre, apenas as trata como capacidade já disponível quando
  relevante (não é o caso direto desta fatia — 4B não consome classificação
  de ativo, só gates e status estratégico de dívida).
- **O mecanismo de contrato para `VALOR_ACAO_FINANCEIRA_IMEDIATA` (`OQ-39`)
  é decisão técnica, não desta spec.** O discovery (Rodada 4, §1.2)
  identifica duas leituras — campo novo em `AcaoRequerida` (mas força uma
  dependência de ordem: gates decidem a ação, a ação carrega o valor, a
  necessidade lê a ação) ou campo novo em `Divida` (evita a dependência de
  ordem, mas soa a dado coletado, não derivado, e duplicaria informação que
  `VALOR_QUITACAO_HOJE`/`Oportunidade.beneficio` já cobrem para os casos que
  eles endereçam) — sem decidir qual. `RF-61` exige apenas que a mudança
  receba o mesmo rigor de varredura de consumidores que `RF-31`/`RF-41`/
  `RF-59` já estabeleceram como padrão desta base, qualquer que seja o
  mecanismo escolhido no plano técnico.
- **O módulo onde vive `NECESSIDADE_IMEDIATA_DIVIDA` (`OQ-41`) é decisão
  técnica, não desta spec.** O discovery (Rodada 4, §3) identifica que a
  função precisa do `ResultadoGates`/`GATE_PENDENTE` da dívida, o que
  levanta se ela deve viver em `engine/gates.py` (perto de onde lê) ou em
  `engine/ataque_imediato.py` (perto das outras funções da §13/§14 que a
  consomem, aumentando o acoplamento de um módulo hoje documentado como
  recebendo tudo por parâmetro sem depender de outros módulos de domínio).
  `RF-64` exige apenas que a função seja pura (entradas por parâmetro),
  qualquer que seja o módulo escolhido.
- **`VALOR_RELEVANTE_PARA_QUITACAO` integral é requisito de negócio, não
  detalhe de implementação (§14.1.2, "REGRA CANÔNICA").** A distinção entre
  "quanto poderia ser usado agora" (`NECESSIDADE_IMEDIATA_DIVIDA`, esta
  fatia) e "quanto vale a pena disponibilizar" (`ATAQUE_IMEDIATO_RECOMENDADO`,
  fatia 4C) é deliberada na fonte normativa. Esta fatia implementa apenas a
  primeira pergunta.
- **Esta fatia não resolve `OQ-38` (renda de veículo).** É uma lacuna de
  classificação de ativo físico (fatia 4A, já concluída), não de necessidade
  financeira imediata por dívida. Não afeta `NECESSIDADE_IMEDIATA_DIVIDA`
  nem `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` em nenhum ramo.
- **Esta fatia não liga o resultado a `calcular_diagnostico`.**
  `ATAQUE_IMEDIATO_RECOMENDADO` continua `dinheiro(0)` (placeholder) até a
  fatia 4C. `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` desta fatia é
  verificável como função pura, com entradas fornecidas por parâmetro nos
  gabaritos, sem exigir que a integração exista.

### Rodada 4 (2026-09-10) — fatia 4C

- **Fatias 4A e 4B estão concluídas e verificadas antes do início desta
  fatia.** `classificar_investimento`, `classificar_ativo_fisico`, a fórmula
  do valor líquido realizável (4A), `NECESSIDADE_IMEDIATA_DIVIDA` e
  `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (4B) já existem no motor,
  testados e homologados (build limpo em 298 arquivos, 594 testes, 47
  gabaritos). Esta fatia não reabre nenhuma delas — apenas as compõe.
- **`AMB-R3-01` foi resolvida "provisoriamente" em 2026-09-07, condicionada
  a uma premissa que deixou de valer.** A resolução original (manter a
  assinatura de `calcular_diagnostico`, campo em `dinheiro(0)`) foi
  explicitamente justificada por "enquanto a fórmula não existisse". A
  fórmula existe desde 2026-09-09 (§14). Esta fatia reabre formalmente a
  decisão — não a decide por conveniência de implementação — e a registra
  como `OQ-44` (seção 10), com os mesmos três desenhos já identificados pelo
  discovery (Rodada 4, §5), nenhum deles antecipado aqui.
- **O mecanismo concreto de `RF-68` (`OQ-44`) é decisão técnica do plano,
  não desta spec** — mesmo padrão de `OQ-39`/`OQ-40`/`OQ-41` nas fatias
  anteriores. A diferença de risco: as três anteriores mudavam o contrato de
  uma dataclass de domínio (`ItemAtivo`, `ItemInvestimento`, `AcaoRequerida`);
  esta pode mudar a assinatura da função pública mais central e mais
  consumida do motor (`calcular_diagnostico`), potencialmente com efeito
  sobre todo chamador dentro de `engine/` e em `app-aluno`. O risco maior é
  registrado explicitamente na seção 8, não diluído.
- **Investigação de código confirma o problema, não uma suposição.**
  `engine/gates.py::NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` exige
  `particao: ParticaoElegibilidade` e `acoes_por_divida: Mapping[str,
  AcaoRequerida]` como parâmetros — os dois só existem depois de
  `particionar_elegibilidade`. Em `engine/motor.py::calcular_plano`,
  `calcular_diagnostico(estado, parametros)` é chamada **antes** de
  `particionar_elegibilidade(estado.dividas)` (linhas 245 e 250), e o
  `Diagnostico` resultante já é consumido por `simular_cenario` antes de a
  partição existir. `Diagnostico` é `@dataclass(frozen=True, slots=True)` —
  substituir o campo depois de construído exige mecanismo explícito
  (`dataclasses.replace`, já usado em `calcular_plano` para `particao`) ou
  reordenação do pipeline, não simples atribuição.
- **Nenhum gabarito de homologação (`GAB-A`/`GAB-B`/`GAB-C`/invariantes/
  `GAB-AI-*`/`GAB-NFI-*`) muda de valor além do próprio
  `ATAQUE_IMEDIATO_RECOMENDADO`.** É a única mudança de valor esperada desta
  fatia em toda a base de gabaritos — ao contrário de toda fatia anterior,
  em que gabarito divergindo era sinal de regressão, aqui é o ganho
  pretendido, e precisa ser verificado como tal, não presumido.
- **Esta fatia não implementa `ATAQUE_IMEDIATO_APROVADO` nem o passo de
  confirmação do usuário.** `STATUS_ATAQUE_IMEDIATO` e a fatia 3C original
  (Rodada 3) seguem fora de escopo do PIQ v1.0.1 §14 atual — não fazem parte
  do que esta fatia liga (seção 9).
- **Esta fatia não altera `app-aluno`.** Sinaliza impacto (Bloco 10,
  `T-77`/`T-78`/`T-79`, que passam a ter dado real para consumir) sem
  implementar nada naquele slug (seção 9).

## 8. Risks

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| **`RISCO-CANONICA`** — parte das decisões ainda vive na seção 11 desta spec em vez de em documento normativo do especialista | **médio** (era alto) | Muito reduzido em 2026-09-02: o *Fechamento das Definições Remanescentes da Engine* absorveu oito temas e traz **regra de precedência própria**, então já não são duas fontes concorrentes — são duas camadas com hierarquia declarada. Resta consolidar na canônica os gates, a regra D.4 e a separação entre empate material e proximidade econômica |
| **Ordem de derivação violada.** As fórmulas de `NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS`, D.4 e `FATOR_SEGURANCA` formam um grafo de dependência. Derivar fora de ordem produz resultado errado **sem erro visível** | alto | `RF-27` e a seção 11.10. Exige teste que force a ordem, não apenas confie nela |
| Custo computacional do benefício marginal: duas trajetórias por dívida elegível a cada ranqueamento, e o ranqueamento se repete a cada quitação e a cada resíduo | médio | Requisito não-funcional de carteira de 30 dívidas. Medir antes de otimizar; a corretude vem primeiro |
| Uso de ponto flutuante binário produzindo divergência de centavos nos gabaritos | alto | Exigir tipo decimal exato desde a primeira tarefa; `AC-01` a `AC-03` falham ruidosamente se isso for violado |
| Confundir resíduo de ataque com fluxo liberado, gerando dupla contagem | alto | `AC-14` e `AC-15` cobrem os dois lados; a trava `F-03` é testada isoladamente |
| Implementar reranqueamento mensal por hábito, contrariando `R-02` | alto | `AC-13` existe para pegar isso. A errata `E-06` registra que essa leitura divergiu em 8,5% de 400 carteiras |
| Usar a parcela contratual como fluxo liberado de dívida que não estava sendo paga | alto | `AC-32`. O caso é real e aparece em `GAB-A`, onde D001 tem devido 1.200 e efetivo 0 |
| Confundir `P_DIFERENCA_ECONOMICA_MATERIAL` (1%) com `P_DIFERENCA_CUSTO_EQUIVALENTE` (5%) | médio | `AC-28` e `AC-29` separam os dois usos com números do `GAB-C` |
| Parâmetro escrito no código por conveniência durante o desenvolvimento | médio | `AC-17`; convenção registrada na seção 4 do `sdd.config.md` |
| Fabricar um Híbrido quando nenhuma candidata atende às tolerâncias | médio | `EC-03` e a regra `H-08`; teste explícito de ausência |
| **Gate 1 passa a emitir `AcaoRequerida`** onde hoje devolve `acao=None` (`engine/gates.py`, dois ramos de bloqueio) — altera a saída de um gate já verificado por gabarito | **alto** — `GAB-03` e `EC-17` tocam exatamente dívidas travadas por informação: uma `ORDEM_ACOES` que hoje vem vazia nesses casos passa a vir preenchida. Tolerância zero (seção 5) significa que a divergência não é absorvível por arredondamento | `AC-56` a `AC-59` exigem reexecutar `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes explicitamente, como parte da própria mudança — não como item separado a esquecer |
| `AcaoRequerida.DIVIDA_ID` deixa de estar sempre presente (`str \| None`) — mudança de invariante de contrato, não acréscimo | **alto** — todo consumidor interno do motor que hoje presume `DIVIDA_ID: str` quebra silenciosamente em runtime se não for corrigido, ou é pego pelo `mypy --strict` se a tipagem estiver correta | `AC-55` audita por leitura de código; `EC-21` documenta a expectativa de falha visível no comando `build` |
| Confundir o `CAMPO_PENDENTE` do motor (nomeia campo de `Divida`) com `RegistroPergunta.ID` de coleta (nomeia pergunta) — o motor não conhece pergunta | **médio** — inverteria a fronteira que já separa `engine/` de `collection/` no slug `app-aluno`, fazendo o motor "conhecer" o questionário | `RF-34` fixa o domínio fechado (`"STATUS_DIVIDA"`, `"SALDO_DEVEDOR_ATUAL"`) como os únicos dois valores possíveis, nenhum deles um ID de pergunta |
| Esquecer de coordenar com `app-aluno` a atualização do hash congelado de `engine/` depois desta mudança | **baixo** para este slug (é responsabilidade do outro slug), mas bloqueia `T-77`/`T-78`/`T-79` se ninguém disparar o procedimento | Nota de coordenação explícita na seção 9 (Out of Scope) — `AC-44` de `app-aluno.spec.md` já documenta o procedimento |
| **Rodada 3 — `Diagnostico.RESERVA_MOBILIZAVEL` muda de tipo** (`Dinheiro` → admite desconhecido, `RF-41`). É quebra de contrato, não adição, exatamente como `DIVIDA_ID: str → str \| None` na Rodada 2 | **alto** — todo consumidor que hoje trata o campo como monetário puro quebra; e a mudança altera `hash_inputs` (`engine/snapshot.py`), invalidando o hash congelado de `app-aluno` | `AC-68` exige que `mypy --strict` acuse os consumidores incompletos; `AC-87` reexecuta `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes. A atualização do hash congelado permanece procedimento do slug `app-aluno` (seção 9) |
| **Rodada 3 — `EstadoFinanceiro` aproximadamente dobra de superfície** (14 campos hoje; `RF-36` a `RF-39` acrescentam escalares e três coleções). Ele entra em `SnapshotOrdem.estado_inputs`, que alimenta `hash_inputs` | **médio** — toda adição de campo muda o hash de todo snapshot existente; é consequência estrutural, não detalhe | Fazer a extensão de estado como uma leva só (`RF-36` a `RF-40` juntos), para que o hash mude uma vez, não campo a campo; sinalizar a `app-aluno` uma única vez |
| **Rodada 3 — inventar a classificação de mobilização** por pressão de "fazer funcionar", já que sem ela `ATIVOS_RECOMENDADOS` fica sempre vazio nos dados reais | **alto** — seria decisão de metodologia tomada no código, violando `sdd.config.md` §6; e a classificação alimenta o valor recomendado ao usuário | `RF-40` fixa que o enum existe e a classificação **entra** como dado; `AC-67` audita por leitura de código a ausência de qualquer função de derivação. `OQ-26` fica registrada e aberta |
| **Rodada 3 — inventar fórmula para `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`.** É o teto de toda a §13: em `GAB-AI-07` é ela sozinha que reduz 25.000 a 10.000. Existem pelo menos duas leituras plausíveis (`Σ VALOR_RELEVANTE_PARA_QUITACAO` das elegíveis pós-gate × subconjunto "estrategicamente vantajoso"), com números muito diferentes | **alto** — a diferença cai direto no valor recomendado ao usuário, sob tolerância zero | `RF-48` a torna parâmetro obrigatório das funções; `AC-80` verifica que a função não a busca em estado nem em diagnóstico. `OQ-29` fica registrada e aberta |
| **Rodada 3 — modelar investimentos/ativos como total agregado escalar** em vez de coleção por item, por ser mais simples | **médio** — tornaria `Σ` dos ativos `MOBILIZACAO_RECOMENDAVEL` (§13.3) inexprimível e mataria a rastreabilidade de origem econômica exigida pela §13.8 | `RF-38` exige coleção tipada; `AC-64` verifica que não existe campo escalar de total agregado em `EstadoFinanceiro` |
| **Rodada 3 — colapsar "prefiro decidir depois" e "não sei" cedo demais.** A aritmética da §13.1 Regra 3 trata os dois de forma idêntica, mas eles são comportamentalmente diferentes (adiamento deliberado × falta de informação) | **médio** — colapsar é correto para o cálculo e pode ser errado para a devolutiva e para reabrir a pergunta certa ao usuário | O motor recebe o estado desconhecido (`RF-36`, `RF-43`) e a distinção fina permanece na camada que coleta; `OQ-25` fica registrada. Não bloqueia 3A/3B — `AC-73` só exige o comportamento aritmético |
| **Rodada 4 — `CLASSIFICACAO_MOBILIZACAO` deixa de ser campo de entrada e passa a ser derivada** (`RF-59`). É inversão de responsabilidade sobre um contrato que a Rodada 3 desenhou deliberadamente do jeito oposto, com teste estático escrito especificamente para impedir a inversão até ser autorizada (discovery Rodada 4, §2) | **alto** — todo consumidor que hoje constrói `ItemAtivo`/`ItemInvestimento` passando `CLASSIFICACAO_MOBILIZACAO` quebra se não for corrigido; os oito gabaritos `GAB-AI-*` da Rodada 3 constroem itens já classificados e precisam continuar válidos | `AC-97`/`AC-98` exigem reescrita (não relaxamento) do teste estático e varredura de todo consumidor; `RF-59` exige o mesmo rigor de `RF-31`/`RF-41` |
| **Rodada 4 — contornar `OQ-38` implementando a leitura "desconhecido por construção" para veículo sem confirmação do especialista** (a leitura que o discovery chamou de `OQ-42`) | **alto** — seria decisão de metodologia tomada no código (afirma implicitamente que veículo nunca gera renda recorrente relevante à classificação), violando `sdd.config.md` §6, ainda que a leitura pareça textualmente defensável | Esta fatia **não implementa** esse ramo para veículo (seção 9); `OQ-38` permanece aberta e bloqueando apenas esse ramo específico, não a classificação de veículo como um todo nem a de investimento/imóvel/outro ativo |
| **Rodada 4 — confundir `VALOR_LIQUIDO_REALIZAVEL_ATIVO` com `_DISPONIVEL`**, tratando-as como a mesma variável ou aplicando `MAX(0, ...)` cedo demais (antes de propagar corretamente o estado desconhecido) | **alto** — a §14.12.2 é explícita ("REGRA CANÔNICA... não são a mesma"); confundir as duas esconderia valor negativo real de ativo sobre-hipotecado, ou faria `_DISPONIVEL` aparecer negativo, quebrando a invariante "nunca negativo" | `RF-57`/`AC-94` isolam as duas fórmulas como requisitos e critérios distintos, com o exemplo de `GAB-NFI-12` como caso de teste obrigatório |
| **Rodada 4 — assumir zero para `SALDO_PASSIVO_VINCULADO` ou `CUSTOS_ESTIMADOS_DESMOBILIZACAO` desconhecidos**, por pressão de "produzir um número" quando a informação falta | **alto** — mascararia um passivo real, inflando `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` além do que os dados sustentam, sob tolerância zero de classificação | `RF-58`/`AC-99` exigem propagação do estado desconhecido, no mesmo padrão já reafirmado para `RESERVA_MOBILIZAVEL` na Rodada 3 |
| **Rodada 4 (fatia 4B) — dupla contagem entre `VALOR_ACAO_FINANCEIRA_IMEDIATA` e `VALOR_RELEVANTE_PARA_QUITACAO` da mesma dívida.** É o risco central que a §14.2.3 nomeia explicitamente como "TRAVA DE DUPLA CONTAGEM" | **alto** — somar os dois infla `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` além do real, e esse valor é o teto direto do dinheiro recomendado ao usuário para atacar dívidas (`ATAQUE_IMEDIATO_RECOMENDADO`, fatia 4C) | `RF-65`/`AC-104`/`AC-111` exigem que `NECESSIDADE_IMEDIATA_DIVIDA` retorne exatamente um dos dois valores por dívida, nunca a soma, com auditoria de código além do teste de caso feliz |
| **Rodada 4 (fatia 4B) — quebrar `AcaoRequerida` silenciosamente ao adicionar o campo monetário**, sem varredura de consumidores nem sinalização a `app-aluno` | **alto** — `app-aluno` já consome `AcaoRequerida` desde a Rodada 2 (`RF-28` a `RF-35`) e tem hash congelado dependente do formato da dataclass; uma mudança não sinalizada quebra o outro slug silenciosamente | `RF-61`/`AC-110` exigem tratamento como quebra de contrato, no mesmo padrão de `RF-31`/`RF-41`/`RF-59`, com sinalização explícita ao slug consumidor |
| **Rodada 4 (fatia 4B) — inventar a fórmula de `VALOR_ACAO_FINANCEIRA_IMEDIATA` para os casos que a §14.2.1 não cobre** (ex.: tentar mapear automaticamente qualquer campo monetário existente em `Divida`/`Oportunidade` como se fosse o valor da ação, sem confirmar que a ação exige desembolso imediato) | **alto** — produziria um valor que a norma não define, sob tolerância zero para dupla contagem e para o teto de ataque imediato | `RF-62`/`RF-63` fixam exatamente as duas condições (sem desembolso → `0`; com desembolso e valor conhecido → o valor; com desembolso e valor desconhecido → `DESCONHECIDO`), sem terceira via |
| **Rodada 4 (fatia 4B) — confundir "quanto poderia ser usado agora" com "quanto vale a pena disponibilizar"**, aplicando alguma fração ou critério de conveniência sobre `VALOR_RELEVANTE_PARA_QUITACAO` antes de somar a `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` | **alto** — a §14.1.2 proíbe isso explicitamente ("REGRA CANÔNICA"); a fração vantajosa pertence a `ATAQUE_IMEDIATO_RECOMENDADO` (fatia 4C, fora de escopo) | `AC-107` verifica que o valor integral é usado; a distinção é registrada como Assumption e NFR desta fatia |
| **Rodada 4 (fatia 4C) — mudança de assinatura da função pública mais central do motor** (`calcular_diagnostico`), ou reordenação do pipeline de `calcular_plano`, decidida por conveniência de implementação em vez de registrada como decisão explícita | **alto** — é a mudança de maior risco de toda a Rodada 4 segundo o próprio discovery (§5): potencial efeito sobre todo chamador de `calcular_diagnostico` dentro de `engine/` e em `app-aluno`, incluindo ~22 chamadas já mapeadas na Rodada 3 (gabaritos, testes, `engine/motor.py:241`) | `RF-68` exige que a decisão seja tomada e documentada, não implementada silenciosamente; `OQ-44` (seção 10) registra os desenhos possíveis sem escolher um |
| **Rodada 4 (fatia 4C) — reimplementar ou "simplificar" a fórmula de `ATAQUE_IMEDIATO_RECOMENDADO`** no ponto de integração, em vez de compor as funções puras já homologadas de `engine/ataque_imediato.py` e `engine/gates.py` | **alto** — duplicar a fórmula cria dois pontos de verdade que podem divergir silenciosamente entre as versões isolada (gabaritos `GAB-AI`/`GAB-NFI`) e integrada (`Diagnostico` real) | `RF-67`/`AC-115` exigem composição, auditada por leitura de código, não apenas pelo resultado numérico |
| **Rodada 4 (fatia 4C) — tratar a mudança de `ATAQUE_IMEDIATO_RECOMENDADO` de `0` para o valor real como regressão** e, por reflexo do padrão das fatias anteriores, tentar "corrigir" o gabarito para manter `0` | **médio** — inverteria o próprio objetivo desta fatia; um revisor acostumado à régua "gabarito mudou = bug" das rodadas anteriores pode aplicá-la incorretamente aqui | `AC-116` nomeia explicitamente que esta é a única mudança de valor esperada em toda a base de gabaritos, e que os demais campos permanecem sob tolerância zero |

## 9. Out of Scope

- **Coleta de dados.** As 291 perguntas e as 270 variáveis são escopo de
  `questionario`.
- **Geração do relatório e fila de revisão humana.** Escopo de `relatorio`.
- **Redação de textos ao usuário final.** A canônica fixa as redações
  obrigatórias (`Q-03`); renderizá-las é do relatório.
- **Definição ou alteração de qualquer regra metodológica.** Trava da seção 1.
- **Tratamento jurídico e LGPD.** `PEND-01` corre em paralelo e bloqueia coletar
  dado de pessoa real, não bloqueia construir o motor.
- **Persistência, autenticação e infraestrutura.** Decisões do plano técnico.
- **Cenário condicional de nova dívida prevista.** Pode ser exibido como alerta
  separado, mas não substitui a ordem-base — e sua apresentação é do relatório.
- **Decisão de metodologia/produto sobre `AcaoRequerida`/`Diagnostico`.** *O quê*
  mudar (campos, domínio de `TIPO_ACAO`, derivação, identidade da ação de
  economia, nome de `CAMPO_PENDENTE`) já foi decidido pelo especialista do
  método e está fechado em `specs/app-aluno.spec.md` §10 (`OQ-10`, `OQ-13`,
  `OQ-14`, `OQ-15`, `OQ-17`, `OQ-18`). Este slug implementa; não reabre.
- **Atualização do hash congelado de `engine/`** em
  `tests/app_aluno/estatica/hashes_congelados.json`. É procedimento do slug
  `app-aluno` (`AC-44` daquela spec), disparado depois que esta mudança for
  mesclada — não é executado por este slug nem por esta spec. Vale igualmente
  para a Rodada 3, cujas mudanças de `EstadoFinanceiro` (`RF-36` a `RF-40`) e
  de tipo (`RF-41`) também alteram o hash. Vale igualmente para a Rodada 4
  (fatia 4A), cuja mudança de contrato de `ItemAtivo`/`ItemInvestimento`
  (`RF-59`) também altera o hash de todo item construído a partir dela.

### Rodada 3 (2026-09-07) — o que fica fora

- **A fatia 3C inteira — `ATAQUE_IMEDIATO_APROVADO`, o passo de confirmação do
  usuário e a injeção do ataque imediato no cronograma-base.** Fica para rodada
  futura, por três motivos concretos e verificados no código:

  1. **A trava de conservação é de igualdade exata.**
     `engine/ciclo_mensal.py:596` verifica
     `if soma_conservacao != e.CAPACIDADE_ATAQUE_M: raise ErroInvariante` —
     "nunca ± tolerância, é subtração exata dentro do próprio mês". Qualquer
     dinheiro injetado no mês 0 que não passe por `CAPACIDADE_ATAQUE_M` faz a
     trava estourar. Há pelo menos três desenhos possíveis de injeção, e eles
     produzem cronogramas **diferentes** (`OQ-35`).
  2. **Um aporte no mês 0 pode mudar o método recomendado.** Ele pode quitar
     dívida logo de saída, ativar a cascata de resíduo, alterar
     `mes_primeira_vitoria` (`engine/ciclo_mensal.py:809-812`) e, por
     consequência, mudar o método recomendado — tudo sob tolerância **zero**
     (seção 5). É o análogo, com alcance maior, da mudança de maior risco da
     Rodada 2.
  3. **Há atrito normativo não resolvido.**
     `engine/ciclo_mensal.py:748-750` registra `RF-14`/`RF-15`
     (*"`CAPACIDADE_ATAQUE_CONSERVADORA` é a única capacidade que alimenta o
     cronograma-base"*) contra a §13.6 (*"somente `ATAQUE_IMEDIATO_APROVADO`
     entra no cronograma-base"*). São duas afirmações de exclusividade sobre o
     mesmo objeto. Conciliá-las é decisão do especialista do método
     (`OQ-32`), não deste slug — `sdd.config.md` §6.

  Consequência direta: `GAB-AI-08` **não** é critério de aceite desta rodada
  (seção 4), e nenhum `RF-NN` desta rodada toca `engine/ciclo_mensal.py`.

- **A regra de derivação da classificação de mobilização** (`NAO_MOBILIZAR` ·
  `MOBILIZACAO_COM_RESSALVAS` · `MOBILIZACAO_POSSIVEL` ·
  `MOBILIZACAO_RECOMENDAVEL`). A canônica fecha que é derivada pelo motor e
  **proíbe perguntá-la** (`piq-app-spec.md:2614`), mas nenhuma fonte publica o
  mapeamento das entradas (`LIQUIDEZ_INVESTIMENTOS`,
  `CUSTO_DESMOBILIZACAO_INVESTIMENTOS`, `DISPOSICAO_USO_INVESTIMENTO`,
  `IMOVEL_POSSUI_PASSIVO`, tipo de ativo) para as quatro classes. Esta rodada
  entrega o **enum** (`RF-40`) e recebe a classificação já feita; derivá-la é
  metodologia e depende de `OQ-26`. **Superado pela Rodada 4**: `OQ-26` foi
  respondida em 2026-09-09 (§14) e a regra de derivação passa a ser escopo da
  fatia 4A (`RF-53`/`RF-54`).

- **A fórmula de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`.** Única variável
  da §13 definida só em prosa, sem bloco de fórmula (`OQ-29`). Nesta rodada ela
  é **parâmetro de entrada** das funções (`RF-48`), nunca derivada. Também fica
  fora a fórmula de `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` (`OQ-27`), pelo
  mesmo motivo: o valor chega por item, já apurado. **Superado pela Rodada 4**:
  `OQ-27` foi respondida em 2026-09-09 (§14.12) e a fórmula do valor líquido
  realizável passa a ser escopo da fatia 4A (`RF-57`/`RF-58`).
  `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (`OQ-29`) segue fora desta fatia —
  é a fatia 4B (abaixo).

- **A relação entre `ECONOMIA_POTENCIAL_IMEDIATA` e `ATAQUE_IMEDIATO_POTENCIAL`**
  (`OQ-31`). Esta rodada não a inclui na soma da §13.2 e não altera nenhuma das
  capacidades existentes.

- **O transporte das respostas do Bloco 4 até `EstadoFinanceiro`.** É o montador
  de estado de `app-aluno` (`OQ-37`); este slug entrega apenas o contrato de
  entrada.

### Rodada 4 (2026-09-09) — fatia 4A — o que fica fora

- **`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` e `NECESSIDADE_IMEDIATA_DIVIDA`.**
  A §14.1/§14.2 as fecha, mas implementá-las mexe em `Divida`, em
  `AcaoRequerida` ou em `engine/gates.py` (a depender de como `OQ-39` for
  decidida) — superfície de contrato diferente da tocada por esta fatia. É a
  **fatia 4B**, que também resolve `OQ-41` (onde vive o módulo da função) e
  fecha `GAB-NFI-01` a `GAB-NFI-05`.

- **A ligação em `calcular_diagnostico`** — `ATAQUE_IMEDIATO_RECOMENDADO`
  sair do placeholder `dinheiro(0)` (`engine/diagnostico.py`). Depende de 4A
  **e** 4B estarem prontas, e de decidir `OQ-43` (mudança de assinatura de
  `calcular_diagnostico` ou desenho alternativo de segunda passada) — a
  mudança de maior risco identificada pelo discovery desta rodada, na função
  pública mais central do motor. É a **fatia 4C**.

- **Classificação de veículo não essencial com venda aceita** (ramo
  `ESSENCIALIDADE=NAO_ESSENCIAL` + `POSSIBILIDADE_VENDA em {SIM, JA_PRETENDE}`
  de `classificar_ativo_fisico` aplicado a veículo). **Bloqueada por `OQ-38`**
  — a coleta não tem variável de renda recorrente de veículo
  (`RENDA_RECORRENTE_VEICULO` ou equivalente), então
  `FLUXO_LIQUIDO_RECORRENTE_ATIVO` não é derivável pela §14.8 para esse tipo
  de ativo nesse ramo específico. A pergunta já foi enviada ao especialista
  em 2026-09-09 e segue sem resposta (nota de verificação ao final da §14).
  **Esta fatia não adota a leitura que o discovery chamou de `OQ-42`**
  (tratar a ausência da variável como "efeito recorrente desconhecido" e
  produzir `MOBILIZACAO_POSSIVEL` por essa via) — o usuário decidiu
  explicitamente não contornar `OQ-38` por conta própria nesta fatia. O
  bloqueio é estritamente localizado: é **uma das seis regras** do documento
  canônico, para **um dos três tipos** de ativo físico (imóvel e outro ativo
  não são afetados; os demais ramos de veículo — bloqueio, essencial,
  importante/parcial, não essencial com venda extrema/talvez — também não
  são afetados). Não trava investimento, não trava imóvel, não trava a
  fórmula de valor líquido realizável, e não trava `RF-53` nem a maior parte
  de `RF-54`.

- **Impacto em `app-aluno`.** Ao fechar `OQ-26`/`OQ-27` do lado do motor,
  esta fatia remove parte do motivo de bloqueio da fatia 2C de `app-aluno`
  (investimentos/ativos), registrada como bloqueada por `OQ-26`/`OQ-27` no
  discovery da Rodada 3. Este slug apenas registra que 2C **passa a ter
  disponível**, do lado do motor, a regra de classificação e a fórmula de
  valor líquido realizável — a fatia 2C ainda depende de `OQ-37` (transporte
  Bloco 4 → `EstadoFinanceiro`, dependente de `app-aluno`) e do mecanismo
  concreto de `OQ-40` estar decidido no plano técnico desta fatia. Esta spec
  não especifica o que `app-aluno` deve fazer com esse desbloqueio.

### Rodada 4 (2026-09-09) — fatia 4B — o que fica fora

- **Classificação de ativos/investimentos e `VALOR_LIQUIDO_REALIZAVEL_ATIVO`
  (`_DISPONIVEL`).** Escopo da **fatia 4A**, já concluída e verificada
  (`RF-53` a `RF-60`). Esta fatia não reabre nem revalida essas funções —
  apenas assume que existem no motor.
- **A ligação em `calcular_diagnostico`** — `ATAQUE_IMEDIATO_RECOMENDADO`
  sair do placeholder `dinheiro(0)` (`engine/diagnostico.py`), reaproveitando
  a fórmula `MIN(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL,
  RECURSOS_ESTRATEGICAMENTE_RECOMENDADOS)` já preservada da Rodada 3
  (§14.2.4). Depende de 4A (concluída) **e** desta fatia (4B) estarem
  prontas, e de decidir `OQ-43` (mudança de assinatura de
  `calcular_diagnostico` ou desenho alternativo de segunda passada) — a
  mudança de maior risco identificada pelo discovery desta rodada, na
  função pública mais central do motor. É a **fatia 4C**.
- **`OQ-38` (renda de veículo).** Não afeta esta fatia — é lacuna isolada de
  classificação de ativo físico (fatia 4A), não de necessidade financeira
  imediata por dívida. Nenhum `RF-NN`/`AC-NN` desta fatia depende dela.
- **Qualquer trabalho em `app-aluno`.** Este slug não altera código de
  `app-aluno`. A mudança de contrato de `AcaoRequerida` (`RF-61`) pode exigir
  atenção daquele slug — mesma disciplina de aviso já usada nas Rodadas 2, 3
  e na fatia 4A: esta spec registra a exigência de sinalização (`AC-110`),
  não executa a atualização do lado de `app-aluno`.
- **O nome exato e o mecanismo do campo monetário de `AcaoRequerida`
  (`OQ-39`), e o módulo exato de `NECESSIDADE_IMEDIATA_DIVIDA` (`OQ-41`).**
  Decisões técnicas do plano, não desta spec (seção 10). A spec fixa apenas
  a exigência de contrato (existência do campo, tratamento como quebra) e de
  pureza/acoplamento correto da função — nunca o nome do campo nem o arquivo
  exato.
- **Atualização do hash congelado de `engine/`**, pelo mesmo motivo já
  registrado para as Rodadas 2, 3 e para a fatia 4A: é procedimento do slug
  `app-aluno` (`AC-44` daquela spec), disparado depois que esta mudança for
  mesclada — não executado por este slug. A mudança de contrato de `RF-61`
  também altera `hash_inputs` de toda `AcaoRequerida` construída a partir
  daqui.

### Rodada 4 (2026-09-10) — fatia 4C — o que fica fora

- **`STATUS_ATAQUE_IMEDIATO`/confirmação do usuário
  (`ATAQUE_IMEDIATO_APROVADO`).** É a fatia 3C do documento original
  (Rodada 3), ainda não iniciada, fora do escopo do PIQ v1.0.1 §14 atual.
  Nenhum `RF-NN` desta fatia toca `ATAQUE_IMEDIATO_APROVADO`,
  `engine/ciclo_mensal.py`, nem qualquer mecanismo de confirmação —
  `verificar_hierarquia_ataque_imediato` (`RF-50`) segue verificando só
  `POTENCIAL >= RECOMENDADO >= 0`, a parte da hierarquia da §13.6 que não
  depende do aprovado. `GAB-AI-08` segue sem `AC-NN` nesta spec, como já
  registrado na Rodada 3.
- **Qualquer trabalho em `app-aluno`.** Este slug não altera código de
  `app-aluno`. Esta fatia apenas sinaliza impacto: o Bloco 10 daquele slug
  (`T-77`/`T-78`/`T-79`, bloqueadas por `OQ-29`/`OQ-43`) passa a ter, do
  lado do motor, o dado real que precisa para funcionar — implementar lá
  não é escopo deste slug, e a atualização do hash congelado de `engine/`
  (`tests/app_aluno/estatica/hashes_congelados.json`, `AC-44` de
  `app-aluno.spec.md`) permanece procedimento daquele slug, disparado depois
  que esta mudança for mesclada, mesmo padrão de coordenação já usado nas
  Rodadas 2, 3 e nas fatias 4A/4B.
- **`OQ-38` (renda de veículo).** Não bloqueia esta fatia. O placeholder
  `None`/ausência de classificação de veículo no ramo afetado (`RF-56`,
  `EC-39`) já é tratado corretamente desde a fatia 4A — não soma, não gera
  erro, não fabrica valor. Esta fatia não reabre `OQ-38`.
- **Qualquer mecanismo concreto que resolva `OQ-44` (`RF-68`) por escolha
  desta spec.** Os três desenhos identificados pelo discovery (nova
  assinatura de `calcular_diagnostico`; segunda passada fora dela; ou
  desnormalizar status estratégico de volta para `Divida`) permanecem em
  aberto — decisão do plano técnico, não desta spec (seção 10).

## 10. Open Questions

| ID | Pergunta | Por que importa | Status |
| --- | --- | --- | --- |
| `OQ-01` | Redação determinística da regra D.4 | Classificação de risco → fator de segurança → capacidade | **respondida** 2026-09-01 · §11.4 |
| `OQ-02` | Corte de `P_CAIXA_VS_ESTRUTURAL` | Materialidade do gap caixa × estrutural | **respondida** 2026-09-01 · parâmetro `DEPRECATED` · §11.8 |
| `OQ-03` | Regra de `P_AUTOPERCEPCAO` | Divergência entre autopercepção e cálculo | **respondida** 2026-09-01 · valor 7 · §11.8 |
| `OQ-04` | Evento futuro previsto entra na projeção-base? | O que a `ORDEM_QUITACAO` mostra | **respondida** 2026-09-01 · não entra · §11.6 |
| `OQ-05` | Fórmula de `BENEFICIO_MARGINAL_AMORTIZACAO` | Ordem inteira da Avalanche | **respondida** 2026-09-01 · §11.1 |
| `OQ-06` | Composição de `VALOR_RELEVANTE_PARA_QUITACAO` | Ordem da Bola de Neve e limite do resíduo | **respondida** 2026-09-01 · §11.2 |
| `OQ-07` | Gates de elegibilidade | Bola de Neve e Híbrido | **respondida** 2026-09-01 · §11.3 |
| `OQ-08` | Parâmetro de `ECONOMICAMENTE_PROXIMO` | Acionamento da revisão humana | **respondida** 2026-09-01 · §11.5 |

### Segunda rodada — fechada em 2026-09-02

| ID | Pergunta | Status |
| --- | --- | --- |
| `OQ-09` | Regra de `INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE` | **respondida** · Definições §1 |
| `OQ-10` | Horizonte de `DESEMBOLSO_FUTURO` | **respondida** · Definições §2 |
| `OQ-11` | `FATOR_SEGURANCA` subtrativo ou multiplicativo | **respondida** · subtrativo · Definições §3 |
| `OQ-12` | Fórmulas de `NIVEL_CONTROLE` e `CONFIABILIDADE_DADOS` | **respondida** · Definições §4, §5 |
| `OQ-13` | Elegibilidade de `EM_ACORDO` e `COBRANCA_SEM_PAGAMENTO` | **respondida** · Definições §6 |
| `OQ-14` | Estado da dívida desviada pelo Gate 2 | **respondida** · `INTERVENCAO_PENDENTE` + `GATE_PENDENTE` · Definições §7 |
| `OQ-15` | Domínio de `STATUS_FINANCEIRO` e função do `PISO_CAPACIDADE` | **respondida** · Definições §8 |
| `OQ-16` | Modo de arredondamento | **respondida** · `ROUND_HALF_UP` · Definições §9 |

### Pontas soltas — nenhuma bloqueia a implementação

| ID | Pergunta | Por que importa | Status |
| --- | --- | --- | --- |
| `OQ-17` | A fórmula de `DIVIDA_ELEGIVEL_ORDEM` da devolutiva de 2026-09-01 exige "NÃO `SUBSTITUIDA`" e "NÃO `SUSPENSA`", mas o domínio fechado de `STATUS_DIVIDA` tem cinco valores e não inclui nenhum dos dois | Baixo impacto: as Definições §6 cobrem os cinco status reais, então a elegibilidade é implementável. Ficam dois termos órfãos na redação anterior | aberta |
| `OQ-18` | As Definições §6.4 dizem que a dívida confirmada vai para "`STATUS` correspondente a `QUITADA`", mas `QUITADA` não consta do domínio de `STATUS_DIVIDA` | Precisa de um valor para o pós-confirmação. Provável que seja saída do inventário ativo em vez de novo status | aberta |
| `OQ-19` | Dívida que amortiza deterministicamente, porém além de `P_HORIZONTE_MAXIMO_SIMULACAO` (10 anos) | As Definições §2 mandam apurar até `SALDO = 0` e §2.1 cobre a dívida que **nunca** amortiza. Fica no meio a que amortiza em 15 anos: soma até o fim, ou trata como `NAO_CALCULAVEL`? | aberta |
| `OQ-20` | A §11.9 desta spec afirma "44 parâmetros ativos" após deprecar `P_CAIXA_VS_ESTRUTURAL`, mas a tabela §8 da canônica (`piq-app-spec.md`, linhas 245–283) lista apenas **39 linhas nomeadas `P_*`** — 38 ativas após a depreciação. A diferença de 6 provavelmente pressupõe decompor `P_PRESSAO_INDIVIDUAL` e `P_PRESSAO_TOTAL` (cada um com 4 valores agrupados: "5 / 10 / 20 / 30") em parâmetros escalares individuais, no padrão já usado para `P_TAXA_TOX_MODERADA/_ALTA/_MUITO_ALTA/_CRITICA` — mas a canônica **não nomeia** essas variantes para pressão, ao contrário do que faz para toxicidade. `P_ESCALA_0_10` (2 valores: "3 / 6") tem a mesma ambiguidade. Implementado provisoriamente em `parameters/parametros-1.0.1.json` com os 38 nomes literais da canônica, mantendo `P_PRESSAO_INDIVIDUAL`, `P_PRESSAO_TOTAL` e `P_ESCALA_0_10` como arrays — sem inventar nomes de sufixo não escritos na fonte | **aberta** — bloqueia fechar a contagem oficial de 44; não bloqueia o motor operar com os 38 nomes literais |

> Nenhuma questão bloqueante em aberto. `PEND-01` (jurídico/LGPD) segue aberta na
> canônica, mas é fora do escopo deste slug: bloqueia coletar dado de pessoa
> real, não bloqueia construir o motor.

### Rodada 2 — Extensão de `AcaoRequerida`/`Diagnostico` (2026-09-04)

> **Nota de numeração.** Os IDs `OQ-10` e `OQ-13` a `OQ-18` já existem *acima*,
> neste mesmo arquivo, com assunto diferente (regras da metodologia original,
> fechadas em 2026-09-01/02). As referências `OQ-10`, `OQ-13`, `OQ-14`, `OQ-15`,
> `OQ-17`, `OQ-18` citadas ao longo desta rodada apontam para
> `specs/app-aluno.spec.md` §10 — **namespace distinto**, do outro slug — nunca
> para os IDs locais deste arquivo. Não há colisão de significado, só de rótulo
> textual entre os dois documentos; toda citação nesta rodada é qualificada
> explicitamente com `app-aluno.spec.md`. Questões novas desta rodada continuam
> a numeração local a partir de `OQ-21`.

| ID | Pergunta | Por que importa | Status |
| --- | --- | --- | --- |
| `OQ-21` | O discovery (`specs/motor-calculo.discovery.md`) não especifica o formato interno de `ACAO_ID` (prefixo, gerador, ex.: `A001` no padrão de `D001`/`M001`, ou UUID) — só a propriedade de estabilidade entre snapshots | Baixo impacto para o contrato externo (`RF-28`/`AC-48` só exigem estabilidade, não um formato específico), mas quem implementar precisa de um formato concreto para escrever código. Nenhuma fonte lida (discovery, `app-aluno.spec.md` §10 `OQ-10`, canônica) publica um formato para transcrever | **respondida (2026-09-04)** — decisão do usuário: `ACAO_ID` é **determinístico por composição** de campos já estáveis da origem da ação, sem estado externo, sem contador e sem UUID/hash aleatório persistido. Para ações ligadas a gate (`INFORMACAO`, `RENEGOCIACAO`, `TROCA`): composição de `DIVIDA_ID` + `TIPO_ACAO` (mesma dívida e mesmo tipo de ação sempre produzem o mesmo `ACAO_ID`, independente da ordem de avaliação entre snapshots). Para a ação de economia (`TIPO_ACAO="ECONOMIA"`, sem `DIVIDA_ID`): um identificador fixo derivado só de `TIPO_ACAO` (não há segunda dívida com que colidir — é uma ação única por cálculo). O formato exato de serialização (separador, caixa, prefixo) fica a critério do plano técnico, desde que preserve esta propriedade de determinismo puro por composição |
| `OQ-22` | Quando `ECONOMIA_POTENCIAL_IMEDIATA > 0` em mais de um mês/snapshot consecutivo sem que o valor subjacente mude, o `ACAO_ID` da ação de economia permanece o mesmo (mesma regra de estabilidade de `RF-28`) ou é recriado a cada snapshot? | Se recriado a cada snapshot, o vínculo do Bloco 11 de `app-aluno` para a ação de economia se perderia entre recálculos, do mesmo jeito que `RF-28` evita para as demais ações | **respondida (2026-09-04)** — decisão do usuário: **sim, deve ser estável.** Consistente com o propósito de `ACAO_ID` (`RF-28`): o Bloco 11 de `app-aluno` precisa vincular perguntas de acompanhamento à mesma ação entre recálculos, também para a ação de economia. Decorre diretamente da resolução de `OQ-21`: como o `ACAO_ID` da ação de economia é determinístico por composição a partir só de `TIPO_ACAO="ECONOMIA"` (sem depender de valor ou de estado), ele é estável por construção — o mesmo `ACAO_ID` é produzido em todo snapshot em que `ECONOMIA_POTENCIAL_IMEDIATA > 0`, independente do valor específico mudar entre um snapshot e outro |
| `OQ-23` | Qual a fórmula de cálculo de `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO` (`RF-35`)? Nenhuma fonte lida (discovery, `app-aluno.spec.md` §10 `OQ-17`, canônica) publica o cálculo — só nome, tipo (`Dinheiro`) e posição no bloco de campos comportamentais extras de `Diagnostico` | Levantada durante `/sdd:plan` (`plans/motor-calculo.plan.md` R2.10.1, originalmente `AMB-R2-01`). Envolve cálculo financeiro; a spec exige tolerância zero para gates e aplicação de resíduo (§10.3) — uma fórmula adivinhada arrisca divergência não absorvível por arredondamento. `AC-61` só é verificável por tipo/posição enquanto esta questão estiver aberta, não por valor | **respondida (2026-09-07)** — especialista entregou o documento canônico *"PIQ v1.0.1 — Definição Canônica de `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO`"* (Regras de Ataque Imediato, especificação interna congelada). Fórmulas transcritas na íntegra em §13. **A resposta é maior que a pergunta**: o documento define **seis** variáveis (`RESERVA_MOBILIZAVEL`, `ATAQUE_IMEDIATO_POTENCIAL`, `ATAQUE_IMEDIATO_RECOMENDADO`, `ATAQUE_IMEDIATO_APROVADO`, `RESERVA_RECOMENDADA`, `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`), consome ~13 campos de entrada que **não existem** hoje em `engine/estado.py`, e depende do Bloco 4 do questionário (`B4.03A`), ainda não implementado. Por isso `T-91` **não é destravada por esta resposta**: o bloqueio deixa de ser "falta fórmula" e passa a ser "falta modelagem de estado". Escopo remetido à **Rodada 3** (discovery em `specs/motor-calculo.discovery.md`, rodada de 2026-09-07) |

### Rodada 3 — Ataque Imediato e Reserva (2026-09-07)

> **Regra de leitura.** As questões abaixo estão separadas pelo que
> **efetivamente bloqueiam**. Nenhuma delas bloqueia as fatias 3A e 3B desta
> spec — é exatamente por isso que o fatiamento existe. As que exigem o
> especialista do método permanecem abertas e **não devem ser respondidas por
> implementação** (`sdd.config.md` §6, `CLAUDE.md` regra 3): nenhuma fórmula
> foi inventada para nenhuma delas.

**Bloqueiam a fatia 3C — exigem o especialista do método**

| ID | Pergunta | Por que importa | Status |
| --- | --- | --- | --- |
| `OQ-26` | Qual a regra de derivação da classificação de ativos e investimentos (`NAO_MOBILIZAR` · `MOBILIZACAO_COM_RESSALVAS` · `MOBILIZACAO_POSSIVEL` · `MOBILIZACAO_RECOMENDAVEL`)? A canônica (`piq-app-spec.md:2614`) fecha que é derivada pelo motor e proíbe perguntá-la, mas nenhuma fonte publica o mapeamento das entradas disponíveis na coleta para as quatro classes | Sem ela, `ATIVOS_RECOMENDADOS` e `INVESTIMENTOS_RECOMENDADOS` não são deriváveis a partir de dados brutos. **Não bloqueia 3A/3B**: o domínio dos quatro valores está fechado pela §13 (`RF-40`) e a classificação entra como dado por item; `GAB-AI-01` a `GAB-AI-07` continuam verificáveis | **aberta** — enviada ao especialista |
| `OQ-27` | Qual a fórmula de `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`? A canônica lista `VALOR_LIQUIDO_REALIZAVEL_ATIVO` como derivada; a §13.3 usa o sufixo `_DISPONIVEL`, ausente da canônica. São a mesma variável? Entram custos estimados de desmobilização e saldo de passivo vinculado? | Componente direto de `ATIVOS_RECOMENDADOS`. **Não bloqueia 3A/3B**: nesta rodada o valor líquido realizável chega já apurado por item (`RF-38`) | **aberta** — enviada ao especialista |
| `OQ-29` | Qual a fórmula fechada de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`? A §13.5 é a única variável da §13 definida só em prosa. É `Σ VALOR_RELEVANTE_PARA_QUITACAO` das dívidas elegíveis pós-gate, ou um subconjunto "estrategicamente vantajoso" (§13.4)? Ações de `ORDEM_ACOES` entram — e com que valor, se `AcaoRequerida` não tem campo monetário? | É o **teto** de toda a fórmula: em `GAB-AI-07` é ela, sozinha, que reduz 25.000 de recursos a um recomendado de 10.000. **Não bloqueia 3A/3B**: `RF-48` a recebe por parâmetro e os enunciados de `GAB-AI-06`/`-07` fornecem o valor. Bloqueia a derivação real | **RESPONDIDA E IMPLEMENTADA POR COMPLETO (fatia 4C, especificada 2026-09-10).** Histórico: a metade `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` (§14.1/§14.1.1, `RF-64`/`RF-65`) foi implementada em `engine/gates.py` e testada na fatia 4B (`GAB-NFI-01` a `05`, §14.16, `T-134`–`T-139`). A metade que faltava — `ATAQUE_IMEDIATO_RECOMENDADO` real dentro de `Diagnostico`, via ligação em `calcular_diagnostico`/`calcular_plano` (§14.2.4) — é o objeto de `RF-66` a `RF-69` desta fatia. Com esta spec, `OQ-29` não deixa nenhum resíduo aberto — o mecanismo concreto de ligação (`OQ-44`, abaixo) é decisão técnica de plano, não pendência de metodologia |
| `OQ-31` | `ECONOMIA_POTENCIAL_IMEDIATA` compõe `ATAQUE_IMEDIATO_POTENCIAL`? É fluxo (economia recorrente) ou estoque (dinheiro liberável já)? Hoje entra em soma com as capacidades (`engine/diagnostico.py:23-30`); a canônica cita `ECONOMIA_RECORRENTE_POTENCIAL` ao lado de `ATAQUE_IMEDIATO_POTENCIAL` (`piq-app-spec.md:2614`) sem relacioná-las | Risco de dupla contagem entre capacidade mensal e ataque imediato (§13.8). **Não bloqueia 3A/3B**: esta rodada não a inclui na soma da §13.2 e não altera nenhuma capacidade (seção 9) | **aberta** — enviada ao especialista |
| `OQ-32` | Como conciliar `RF-14`/`RF-15` ("`CAPACIDADE_ATAQUE_CONSERVADORA` é a única capacidade que alimenta o cronograma-base", `engine/ciclo_mensal.py:748-750`) com a §13.6 ("somente `ATAQUE_IMEDIATO_APROVADO` entra no cronograma-base")? Fluxo mensal e injeção pontual coexistem, ou uma redação revoga a outra? | Define se há revisão de norma anterior. **Bloqueia 3C e `GAB-AI-08`**; não bloqueia 3A/3B, que não tocam `engine/ciclo_mensal.py` | **aberta** — enviada ao especialista |
| `OQ-35` | Em que momento do cronograma o `ATAQUE_IMEDIATO_APROVADO` é aplicado? Antes do primeiro ciclo de juros (abatendo `saldos_iniciais`, `engine/ciclo_mensal.py:769-777`) ou dentro do mês 1 após o cômputo de juros? As duas produzem cronogramas diferentes, e o aporte pode quitar dívida de saída, alterando `mes_primeira_vitoria` e o método recomendado | Tolerância zero para "número de meses, primeira vitória, método recomendado" (seção 5). **Bloqueia 3C e `GAB-AI-08`**; não bloqueia 3A/3B | **aberta** — enviada ao especialista |

**Não bloqueiam nada — decisão técnica, encaminhada nesta spec**

| ID | Pergunta | Encaminhamento | Status |
| --- | --- | --- | --- |
| `OQ-24` | Colisão de nome: `collection/registros/bloco-04.yaml:156` grava a resposta crua de `B4.03A` em `RESERVA_MOBILIZAVEL`; a §13.1 define `RESERVA_MOBILIZAVEL` como o valor **derivado** e chama a resposta crua de `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO`. Em `GAB-AI-02` os dois valem 30.000 e 20.000 | **respondida (2026-09-07)** — decisão do usuário: renomear o `VARIAVEL_GRAVADA` daquela linha para `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` (o nome que a própria §13.1 usa para a resposta crua); `RESERVA_MOBILIZAVEL` fica exclusivo do valor derivado. Escopo verificado: **uma única linha** — os outros 15 usos do nome no repositório já se referem ao campo derivado de `Diagnostico`. O `ID` `B4.03A` não muda. Virou `RF-42`/`AC-69` | **respondida** |
| `OQ-25` | Contrato de domínio para os três estados de `B4.03A` ("valor", "prefiro decidir depois", "não sei"), para `RESERVA_EXISTE = INFORMAL` e para os quatro valores de `DISPOSICAO_USO_RESERVA`, que a §13.1 reduz a `NAO`/não-`NAO`. Colapsar em desconhecido é correto para a aritmética e pode ser errado para a devolutiva ao usuário | Encaminhado nesta rodada apenas no que a §13 fecha: o motor recebe o estado desconhecido (`RF-36`) e as três regras da §13.1 são aplicadas na ordem (`RF-43`). A distinção comportamental fina entre adiamento e desconhecimento permanece na camada que coleta e reabre pergunta, fora de `engine/`. `AC-73` cobre só o comportamento aritmético | **aberta** — não bloqueia 3A/3B |
| `OQ-28` | Como o motor sabe que `DINHEIRO_DISPONIVEL` está "realmente livre, não comprometido" (§13.3)? `B4.01` já pergunta isso no enunciado — é garantia de coleta, ou o motor deve validar? | Encaminhado como **garantia de coleta**, documentada: `RF-37`/`AC-63` fixam que o motor consome o valor sem revalidá-lo. Se o especialista decidir que cabe validação no motor, ela é acréscimo, não reescrita | **aberta** — não bloqueia 3A/3B |
| `OQ-33` | Onde vivem as travas de dupla contagem da §13.8? Invariante de execução com `ErroInvariante` (padrão `A-04`), validação na construção do estado, ou garantia de coleta? Detectar "origem econômica única" exige que cada item carregue categoria | Encaminhado como híbrido no que é verificável sem 3C: origem única por item garantida pela modelagem em coleção (`RF-38`, `RF-52`, `AC-83`) e não-relançamento garantido na coleta (`AC-84`). O caso "extraordinário aprovado × evento independente" depende de `ATAQUE_IMEDIATO_APROVADO` e fica em 3C | **aberta** — parcialmente encaminhada; não bloqueia 3A/3B |
| `OQ-34` | Tolerância dos `GAB-AI`: `± R$ 0,05` (padrão de monetário acumulado) ou zero? | **respondida nesta spec** — tolerância **zero** (seção 5): os oito são valores exatos de `MIN`/`MAX`/soma, sem acumulação de arredondamento | **respondida** |
| `OQ-36` | `Diagnostico` cresce em campos e `RESERVA_MOBILIZAVEL` muda de `Dinheiro` para tipo que admite desconhecido — mudança de tipo é quebra de contrato, não adição, e impacta `hash_inputs` e o hash congelado de `app-aluno` | **respondida nesta spec** — virou `RF-41` com o mesmo tratamento dado a `RF-31` na Rodada 2 (varredura de consumidores, `mypy --strict` como rede, `AC-68`), e `AC-87` reexecuta gabaritos e invariantes. A atualização do hash congelado permanece do slug `app-aluno` (seção 9) | **respondida** |

**Coordenação entre slugs**

| ID | Pergunta | Slug dono | Status |
| --- | --- | --- | --- |
| `OQ-30` | Onde vive o passo de confirmação de `ATAQUE_IMEDIATO_APROVADO`? `engine/` é puro por regra e `calcular_diagnostico` é uma passada só — o aprovado não pode ser derivado, tem que entrar como dado num segundo cálculo | `app-aluno` provavelmente dono do passo; `motor-calculo` entrega o contrato de entrada | **aberta** — **bloqueia 3C** e `GAB-AI-08`; não bloqueia 3A/3B |
| `OQ-37` | Quem transporta as respostas do Bloco 4 até `EstadoFinanceiro`? O montador de estado de `app-aluno` hoje não tem nenhuma referência a reserva ou ataque imediato | `app-aluno`, dependente do contrato entregue por 3A | **DESBLOQUEADA (2026-09-07, `T-116`)** — a fatia 3A entregou o contrato: `EstadoFinanceiro` declara os 8 campos novos (`RF-36`–`RF-39`) e `app/montagem/estado.py:1326` falha no `build` por argumento faltante. A pergunta **continua sem resposta** e é de `app-aluno`: preencher os campos **não é correção mecânica**, exige antes decidir a allowlist de `AC-41` (ver sinalização em `tasks/motor-calculo.tasks.md`, `T-116`) |

### Rodada 4 — Fechamento: Necessidade Financeira Imediata e Classificação de Ativos (2026-09-09)

> `OQ-29`, `OQ-26` e `OQ-27` (Rodada 3) foram **respondidas** pelo documento
> canônico transcrito integralmente em **§14** e marcado **congelado**
> (*"Nenhuma dessas decisões fica a critério do desenvolvedor"*). A questão
> abaixo é nova, levantada durante a própria transcrição — não pela
> implementação (`sdd.config.md` §6, `CLAUDE.md` regra 3).

| ID | Pergunta | Por que importa | Status |
| --- | --- | --- | --- |
| `OQ-38` | A §14.8 (`FLUXO_LIQUIDO_RECORRENTE_ATIVO = RENDA_RECORRENTE_ATIVO - CUSTO_RECORRENTE_ATIVO`) se aplica a veículo, mas `collection/registros/bloco-04.yaml` só declara `CUSTO_RECORRENTE_VEICULO` (linha 624) — não existe variável de renda para veículo, ao contrário de imóvel (`RENDA_IMOVEL`, linha 436) e de outro ativo (`RENDA_OUTRO_ATIVO`, linha 885). Qual é a variável de renda recorrente de veículo, ou veículo está estruturalmente excluído da fórmula (renda sempre 0)? | Sem resposta, `FLUXO_LIQUIDO_RECORRENTE_ATIVO` de veículo não é derivável pela §14.8 — bloqueia aplicar §14.7/14.9 (classificação de veículo não essencial com venda aceita) por falta de um dos dois termos da subtração | **aberta** — enviada ao especialista em 2026-09-09, ver nota de verificação ao final de §14 |

### Rodada 4 — fatia 4B (2026-09-09)

> Decisões técnicas nossas, não do especialista (mesmo sentido de `OQ-40`
> acima) — nenhuma delas exige resposta do especialista do método, mas
> ambas bloqueiam o plano técnico desta fatia até serem decididas.

| ID | Pergunta | Por que importa | Bloqueia | Status |
| --- | --- | --- | --- | --- |
| `OQ-39` | **Onde mora `VALOR_ACAO_FINANCEIRA_IMEDIATA`?** Campo monetário novo em `AcaoRequerida` (mudança de contrato de dataclass já consumida por `app-aluno`, mesma classe de risco de `RF-31`/`RF-41`/`RF-59` — mas força uma dependência de ordem, já que `AcaoRequerida` só é produzida depois que um gate decide bloquear), campo novo em `Divida` (evita a dependência de ordem, mas soa a dado coletado, não derivado, e duplicaria `VALOR_QUITACAO_HOJE`/`Oportunidade.beneficio` para os casos que eles já cobrem), ou terceiro desenho não cogitado no discovery? | Sem decidir, `NECESSIDADE_IMEDIATA_DIVIDA` não tem de onde ler o valor para os ramos de Gate 2/4 | Implementação desta fatia (`RF-61`, `RF-62`, `RF-63`) | **respondida (plano, R4B.1.1, 2026-09-09)** — campo novo em `AcaoRequerida` (`VALOR_ACAO_FINANCEIRA_IMEDIATA: DinheiroTalvez`), com os cinco pontos de construção de `engine/gates.py` fornecendo o valor |
| `OQ-41` | **Em que módulo vive `NECESSIDADE_IMEDIATA_DIVIDA`?** `engine/gates.py` (perto de `ParticaoElegibilidade`, evita `ataque_imediato.py` importar tipos de gate) ou `engine/ataque_imediato.py` (perto das outras funções da §13/§14 que a consomem, mas aumenta o acoplamento de um módulo hoje documentado como recebendo tudo por parâmetro sem depender de outros módulos de domínio) | Não altera o resultado numérico, mas altera a superfície de import entre módulos que já tem uma dívida técnica registrada (ciclo de import da Rodada 3, `engine/diagnostico.py:792-803`) | Implementação desta fatia (`RF-64`) | **respondida (plano, R4B.1.2, 2026-09-09)** — `engine/gates.py`, confirmado no código real: `NECESSIDADE_IMEDIATA_DIVIDA`/`NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` vivem em `engine/gates.py:937` e `:1002` |

### Rodada 4 — fatia 4C (2026-09-10)

> Decisão técnica nossa, não do especialista — mesmo sentido de `OQ-39`/
> `OQ-40`/`OQ-41` acima. Reabre formalmente `AMB-R3-01` (plano, R3.10.1),
> cuja resolução original ("manter a assinatura, opção b") foi
> explicitamente condicionada a "enquanto a fórmula não existisse" — condição
> que deixou de valer em 2026-09-09. Não é decidida nesta spec.

| ID | Pergunta | Por que importa | Bloqueia | Status |
| --- | --- | --- | --- | --- |
| `OQ-44` | **Como `calcular_diagnostico`/`calcular_plano` deixam de emitir o placeholder de `ATAQUE_IMEDIATO_RECOMENDADO`, dado que `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` exige `ParticaoElegibilidade`/`Mapping[str, AcaoRequerida]` (produzidos por `particionar_elegibilidade`), e `engine/motor.py::calcular_plano` hoje chama `calcular_diagnostico` (linha 245) **antes** de `particionar_elegibilidade` (linha 250), com o `Diagnostico` resultante já consumido por `simular_cenario` antes da partição existir?** Investigados três desenhos, nenhum decidido: (1) `calcular_diagnostico` ganha parâmetro novo (`ParticaoElegibilidade`/inventário pós-gates) — mudança de assinatura pública, todo chamador precisa fornecer o argumento novo; (2) `calcular_diagnostico` mantém a assinatura `(estado, parametros)`, e uma segunda função/passada em `calcular_plano` (depois de `particionar_elegibilidade`) substitui o campo no `Diagnostico` já construído, via `dataclasses.replace` (mecanismo já usado em `calcular_plano` para `particao`/`Cenario`) — preserva a assinatura pública, mas reordena/estende o pipeline e reabre a pergunta "onde vive a segunda passada", já registrada para `ATAQUE_IMEDIATO_APROVADO` em `OQ-30`, agora também para o *recomendado*; (3) desnormalizar `DIVIDA_STATUS_ESTRATEGICO`/`GATE_PENDENTE` de volta para dentro de `Divida`, eliminando a dependência de `ParticaoElegibilidade` — contradiz a decisão de design da Rodada 1 de que status estratégico é **saída** calculada pelo motor, não entrada declarada pelo usuário | É a mudança de maior risco de toda a Rodada 4 (discovery §5, §8): mexe na função pública mais central e mais consumida do motor, com efeito potencial sobre todo chamador de `calcular_diagnostico` dentro de `engine/` e em `app-aluno` — maior alcance que `RF-31`/`RF-41`/`RF-59`/`RF-61`, que mudaram tipo/campo de uma dataclass já existente, nunca a lista de parâmetros de uma função pública | Implementação de `RF-66`/`RF-68` desta fatia | **resolvida (fatia 4C, 2026-09-10)** — decisão (2): `calcular_diagnostico` mantém a assinatura pública `(estado, parametros)` inalterada, continuando a devolver `ATAQUE_IMEDIATO_RECOMENDADO=dinheiro(0)` quando chamada isoladamente; `engine/motor.py::calcular_plano` ganha uma segunda passada, via `dataclasses.replace` sobre o `Diagnostico` já construído, executada depois de `particionar_elegibilidade` e antes de `montar_SnapshotOrdem` (`T-141`, `T-142`). Resolve formalmente `AMB-R3-01` (plano, R3.10.1) e `OQ-43` (discovery, Rodada 4 §5/§9) por completo |
| `OQ-45` | **Segunda metade de `EC-48`/`AC-109`: quando `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` é `DESCONHECIDO`, `ATAQUE_IMEDIATO_RECOMENDADO` resolve para `dinheiro(0)` documentado (`T-141`, `T-144`) — mas nada sinaliza `STATUS_METODO=PROVISORIO` para esse cenário, lacuna registrada em R4C.10.1 do plano.** Ligar exigiria reordenar o pipeline de `calcular_plano` (calcular `elegivel` antes de `derivar_METODO_RECOMENDADO_PIQ`), o que arriscaria mudar `STATUS_METODO` de cenários hoje não-`PROVISORIO`, violando `AC-116` desta própria fatia | A metade "não fabricar número certo a partir do desconhecido" de `EC-48` está satisfeita; a metade "sinalizar status provisório ao usuário" não — risco de o relatório apresentar um `ATAQUE_IMEDIATO_RECOMENDADO=0` como número firme quando na verdade é incompletude de dado | Nenhuma — registrada como lacuna, não implementada por nenhuma tarefa desta fatia | **aberta** — decisão técnica pendente de especialista/humana, não resolvida nesta fatia. Candidata a rodada futura, possivelmente junto de `OQ-30`/`STATUS_ATAQUE_IMEDIATO` (fatia 3C, ainda fora de escopo) |

## 11. Definições incorporadas

> Origem: devolutiva do especialista de 2026-09-01. **Ainda ausentes da canônica
> v1.0.1** — ver `RISCO-CANONICA` na seção 8.

### 11.1. Benefício marginal de amortização — `RF-05`, `RF-21`

```
DELTA_TESTE_AVALANCHE = MIN(CAPACIDADE_ATAQUE_CONSERVADORA,
                            VALOR_RELEVANTE_PARA_QUITACAO)
```

Para cada dívida elegível, simular isoladamente duas trajetórias:
**A** sem pagamento extraordinário; **B** com `DELTA_TESTE_AVALANCHE` aplicado
agora. Então:

```
BENEFICIO_MARGINAL_AMORTIZACAO = (DESEMBOLSO_FUTURO_SEM_DELTA
                               −  DESEMBOLSO_FUTURO_COM_DELTA)
                               ÷  DELTA_REALMENTE_APLICADO
```

A Avalanche ordena do maior benefício marginal para o menor.

**Horizonte de `DESEMBOLSO_FUTURO`** (Definições §2): cada trajetória é somada do
snapshot atual **até seu próprio `SALDO = 0`**. As duas podem terminar em meses
diferentes — isso é esperado. É proibido truncar no menor prazo ou usar horizonte
fixo (60, 120, número de períodos). É permitido usar horizonte comum igual ao
maior dos dois prazos, com `DESEMBOLSO_MENSAL = 0` após cada quitação, desde que
o resultado seja matematicamente equivalente.

**Fallback.** Se a trajetória não puder chegar deterministicamente à extinção —
faltam dados essenciais, saldo desconhecido, taxa desconhecida, fluxo contratual
indeterminado, pagamento insuficiente para amortizar sem solução determinística,
ou outra insuficiência material — então
`BENEFICIO_MARGINAL_AMORTIZACAO = NAO_CALCULAVEL`, e aplica-se o fallback: 1º
`TAXA_EFETIVA_MENSAL_NORMALIZADA`; 2º `CET` comparável. A ordem fica
`PROVISORIA`. **Não criar benefício marginal artificial.**

**Exceção intramês.** Ao reranquear após uma quitação para aplicar
`RESIDUO_ATAQUE_M`, substituir a capacidade cheia pelo dinheiro efetivamente
restante:

```
DELTA_TESTE_AVALANCHE_RESIDUO = MIN(RESIDUO_ATAQUE_M,
                                    VALOR_RELEVANTE_PARA_QUITACAO)
```

### 11.2. Valor relevante para quitação — `RF-06`

```
SE VALOR_QUITACAO_HOJE = CONFIRMADO
E  STATUS_VALIDADE_PROPOSTA = VIGENTE:
       VALOR_RELEVANTE_PARA_QUITACAO = VALOR_QUITACAO_HOJE
SENÃO:
       VALOR_RELEVANTE_PARA_QUITACAO = SALDO_DEVEDOR_ATUAL
```

| Situação | Comportamento |
| --- | --- |
| Proposta expirada | Não usar; fallback para `SALDO_DEVEDOR_ATUAL` |
| Quitação nunca consultada | Fallback para `SALDO_DEVEDOR_ATUAL` |
| Validade desconhecida | Não tratar como vigente; fallback para saldo e gerar `PRIORIDADE_INFORMACAO` se a diferença puder alterar materialmente a decisão |
| Saldo também desconhecido | `VALOR_RELEVANTE_PARA_QUITACAO` = `DESCONHECIDO`; decisão dependente fica bloqueada ou provisória conforme a materialidade |

### 11.3. Os quatro gates — `RF-17`

Aplicados **antes** da ordem-base do método, na sequência
Informação → Contenção de Risco → Transformação → Oportunidade com Prazo.

| Gate | Condição | Efeito |
| --- | --- | --- |
| **1 — Informação** | Dado material pendente impede saber o valor sobre o qual o ataque será aplicado, a evolução da dívida, se ela está ativa, ou se uma intervenção anterior precisa ocorrer | `DIVIDA_STATUS_ESTRATEGICO` = `INFORMACAO_PENDENTE`. A falta apenas da simulação marginal **não** bloqueia, se o fallback de §11.1 for possível |
| **2 — Contenção de risco** | Risco que exija ação anterior ao ataque ordinário, especialmente patrimonial crítico ou consequência material iminente | Sai temporariamente da ordem-base e entra em `ORDEM_ACOES`. Se a própria quitação for a ação que contém o risco e for executável, pode receber prioridade excepcional com justificativa expressa. **Risco alto não significa automaticamente primeira dívida** |
| **3 — Transformação** | Renegociação, troca ou outra intervenção pendente que possa alterar materialmente saldo, parcela, taxa, prazo ou custo | `DIVIDA_STATUS_ESTRATEGICO` = `INTERVENCAO_PENDENTE`. Não entra na ordem ordinária até a intervenção ser executada, rejeitada ou encerrada |
| **4 — Oportunidade com prazo** | Oportunidade vigente, por exemplo desconto | Avaliada antes da ordem-base. `OPORTUNIDADE_EXECUTAVEL` = benefício + recurso disponível + prazo + sustentabilidade. Pode gerar prioridade específica. **Não** é bloqueio automático, e desconto não implica primeiro lugar |

```
DIVIDA_ELEGIVEL_ORDEM = Gate 1 resolvido
                      E Gate 2 resolvido ou contido
                      E Gate 3 resolvido
                      E Gate 4 resolvido ou sem oportunidade prioritária
```

Para receber ataque ordinário, a dívida deve estar em
`PRONTA_PARA_ORDENACAO` ou já em `EM_ATAQUE`.

**`STATUS_DIVIDA` não decide elegibilidade** (Definições §6). Ele é o estado
operacional declarado no cadastro; quem decide são os gates. Mapeamento:

| `STATUS_DIVIDA` | Efeito |
| --- | --- |
| `ATIVA` | Passa pelos gates. Resolvidos → `PRONTA_PARA_ORDENACAO`, ou `EM_ATAQUE` se já for o alvo |
| `EM_ACORDO` — acordo executado, estrutura vigente conhecida, nada pendente | Não bloqueia. Pode chegar a `PRONTA_PARA_ORDENACAO` |
| `EM_ACORDO` — negociação aberta ou estrutura sujeita a mudança material | `INTERVENCAO_PENDENTE` · `GATE_PENDENTE = TRANSFORMACAO` |
| `COBRANCA_SEM_PAGAMENTO` | Elegível se a existência for confirmada, houver `VALOR_RELEVANTE_PARA_QUITACAO` conhecido e os gates estiverem resolvidos. **Não inventar parcela mensal** |
| `QUITADA_A_CONFIRMAR` | Inelegível. `INFORMACAO_PENDENTE` · `GATE_PENDENTE = INFORMACAO` |
| `OUTRA` | `EM_ANALISE`. Sem ataque até a situação ser normalizada |

**Estados estratégicos — cinco, não quatro:**

```
DIVIDA_STATUS_ESTRATEGICO ∈ {INFORMACAO_PENDENTE, INTERVENCAO_PENDENTE,
                             EM_ANALISE, PRONTA_PARA_ORDENACAO, EM_ATAQUE}
```

**Atributo interno `GATE_PENDENTE`** (Definições §7.1). Em vez de criar um estado
por gate, o estado diz *o que a dívida é* e este campo diz *o que a trava*:

```
GATE_PENDENTE ∈ {INFORMACAO, CONTENCAO_RISCO, TRANSFORMACAO,
                 OPORTUNIDADE, NENHUM}
```

Gate 2 e Gate 3 compartilham `INTERVENCAO_PENDENTE` e se distinguem por
`CONTENCAO_RISCO` versus `TRANSFORMACAO`. Campo interno ao motor — nunca é
pergunta ao usuário.

### 11.4. Regra D.4 — classificação de risco — `RF-18`

**`RISCO_RECAIDA`** — contar 1 sinal por condição ativa:

1. `NOVA_DIVIDA_PREVISTA` = SIM ou TALVEZ
2. `MECANISMO_DEFICIT` inclui cartão, cheque especial, empréstimo ou parcelamento para fechar o mês
3. `HISTORICO_RECAIDA` = SIM
4. `NOVO_PARCELAMENTO_PREVISTO` = SIM ou TALVEZ
5. `PACTO` = `EM_CONSTRUCAO` ou `NAO_ESTABELECIDO`

**`RISCO_COMPORTAMENTAL_GERAL`** — contar 1 sinal por condição ativa:

1. Crédito usado para fechar o mês
2. `RISCO_IMPULSO` = duas ou mais compras não planejadas nos últimos 30 dias
3. Alguma linha reutilizável ainda usada frequentemente ou às vezes
4. `HISTORICO_RECAIDA` = SIM
5. `NOVO_PARCELAMENTO_PREVISTO` = SIM ou TALVEZ
6. `NIVEL_CONTROLE` = `FRAGIL`

**Classificação, para ambos:** `0` = BAIXO · `1–2` = MODERADO · `3+` = ALTO

**Travas.** Dado desconhecido não conta artificialmente como risco positivo, mas
reduz a confiança quando material. Somente `RISCO_COMPORTAMENTAL_GERAL` = ALTO
aciona `P_REDUCAO_RISCO_COMPORTAMENTAL_ALTO`; o histórico de recaída tem
`P_REDUCAO_HISTORICO_RECAIDA` própria e separada — as duas não se absorvem.

### 11.5. Cenário superior e proximidade econômica — `RF-19`, `RF-20`

São dois conceitos distintos, com parâmetros distintos. Não são concorrentes.

**Empate material — `P_DIFERENCA_ECONOMICA_MATERIAL` = 1%.** Encontra-se o menor
custo. Cenário a menos de 1% desse menor custo está em empate econômico
material; entre os empatados, prefere-se o menor `PRAZO_TOTAL`. O vencedor é
`CENARIO_ECONOMICAMENTE_SUPERIOR`.

**Proximidade econômica — 5% e 2 meses.** Para um cenário alternativo X:

```
PENALIDADE_CUSTO(X) = (CUSTO_X − CUSTO_SUPERIOR) ÷ CUSTO_SUPERIOR
ATRASO_PRAZO(X)     =  PRAZO_X − PRAZO_SUPERIOR

ECONOMICAMENTE_PROXIMO(X) = PENALIDADE_CUSTO(X) ≤ P_DIFERENCA_CUSTO_EQUIVALENTE
                          E ATRASO_PRAZO(X)     ≤ P_DIFERENCA_PRAZO_EQUIVALENTE
```

Valores v1.0.1: `P_DIFERENCA_CUSTO_EQUIVALENTE` = 5% ·
`P_DIFERENCA_PRAZO_EQUIVALENTE` = 2 meses.

**Métricas do Híbrido.** `PENALIDADE_CUSTO_VS_AVALANCHE` e
`ATRASO_PRAZO_VS_AVALANCHE` são específicas da construção e validação do
Híbrido. Na comparação geral entre métodos, a referência é
`CENARIO_ECONOMICAMENTE_SUPERIOR`.

### 11.6. Evento futuro previsto — `RF-22`

`NOVA_DIVIDA_PREVISTA` = SIM ou TALVEZ **não** entra na projeção-base. É insumo
de `RISCO_RECAIDA`, alerta de sustentabilidade, condição de revisão futura e
informação para o relatório — não é dívida do inventário.

> A projeção-base incorpora somente eventos futuros **determinísticos** já
> pertencentes ao estado financeiro ou expressamente aprovados para o cenário.
> Intenção, possibilidade ou probabilidade de nova dívida não é evento
> determinístico.

Contratada de fato: `EVENTO_RECALCULO` = `NOVA_DIVIDA`, e novo snapshot.

### 11.7. Fluxo liberado — `RF-04`

```
VALOR_FLUXO_LIBERADO = fluxo mensal que efetivamente deixa de sair
                       do orçamento pela quitação da dívida
```

Para dívida de pagamento estável, corresponde ao `PAGAMENTO_MENSAL_EFETIVO` que
realmente vinha sendo pago. **Dívida que não estava sendo paga libera zero**,
não sua parcela contratual fictícia. Entra em *m+1*.

### 11.8. Parâmetros alterados — `RF-13`, `RF-14`

| Parâmetro | Situação anterior | Situação v1.0.1 fechada |
| --- | --- | --- |
| `P_CAIXA_VS_ESTRUTURAL` | ⚠️ A calibrar | **`DEPRECATED`** — não é necessário parâmetro |
| `P_AUTOPERCEPCAO` | ⚠️ A calibrar | **`7`** |

**Gap caixa × estrutural** é diagnóstico matemático, sem limiar:

```
GAP_CAIXA_VS_ESTRUTURAL = RESULTADO_CAIXA_OBSERVADO − RESULTADO_MENSAL_ATUAL
```

Qualquer valor `> 0` significa que existe obrigação vigente não saindo
integralmente do caixa observado. A capacidade continua derivando de
`RESULTADO_MENSAL_ATUAL`, jamais de um limiar arbitrário sobre o gap. Se um dia
houver limiar apenas para destacar o alerta no relatório, será parâmetro de
apresentação, não de decisão da engine.

**Autopercepção:**

```
GAP_AUTOPERCEPCAO = AUTOPERCEPCAO_CONTROLE ≥ 7
                  E NIVEL_CONTROLE ≠ FORTE
```

**Diagnóstico financeiro** (Definições §8):

```
PISO_CAPACIDADE = MAX(P_PISO_CAPACIDADE_ABSOLUTO,
                      RENDA_TOTAL_RECORRENTE × P_PISO_CAPACIDADE_PERCENTUAL)

CAPACIDADE_ATAQUE_ATUAL = MAX(0, RESULTADO_MENSAL_ATUAL)
```

| `STATUS_FINANCEIRO` | Condição | Semáforo |
| --- | --- | --- |
| `DEFICIT` | `RESULTADO_MENSAL_ATUAL < 0` | vermelho |
| `EQUILIBRIO_FRAGIL` | `0 ≤ RESULTADO_MENSAL_ATUAL < PISO_CAPACIDADE` | amarelo |
| `CAPACIDADE_POSITIVA` | `RESULTADO_MENSAL_ATUAL ≥ PISO_CAPACIDADE` | verde |

> O piso **classifica**. Não trunca, não aumenta, não reduz a capacidade, não é
> capacidade mínima nem valor mínimo de ataque. Com resultado 200 e piso 300, a
> capacidade é **200** — não 0, não 300. Em déficit, o piso não fabrica
> capacidade: `CAPACIDADE_ATAQUE_ATUAL` = 0 e `MODO_ESTABILIZACAO` = SIM.

**Fator de segurança — subtrativo** (Definições §3):

```
REDUCAO_SEGURANCA_TOTAL = REDUCAO_RENDA_VARIAVEL + REDUCAO_CONFIABILIDADE
                        + REDUCAO_RISCO_COMPORTAMENTAL + REDUCAO_RECAIDA

FATOR_SEGURANCA = MAX(P_FATOR_SEGURANCA_MINIMO, 1 − REDUCAO_SEGURANCA_TOTAL)
```

Proibida a composição multiplicativa. O piso entra **depois** da soma. As quatro
parcelas são independentes — nenhuma absorve outra (`AC-26`).

**Arredondamento** (Definições §9): `ROUNDING_MODE = ROUND_HALF_UP`, oficial e
não mais provisório. Monetário exibido em 2 casas; percentuais, taxas e
indicadores no mesmo modo, com casas conforme o campo. Não arredondar etapa
intermediária apenas para coincidir com a apresentação.

### 11.10. Ordem de derivação obrigatória — `RF-27`

As fórmulas novas criaram dependências entre si. Derivar fora desta ordem produz
resultado **silenciosamente errado** — sem exceção, sem erro visível.

```
Bloco 2 (8 variáveis)
   └→ NIVEL_CONTROLE
        ├→ CONFIABILIDADE_DADOS ──→ REDUCAO_CONFIABILIDADE ──┐
        ├→ RISCO_RECAIDA (D.4) ───→ REDUCAO_RECAIDA ─────────┤
        ├→ RISCO_COMPORTAMENTAL_GERAL (D.4)                  ├→ FATOR_SEGURANCA
        │     └→ REDUCAO_RISCO_COMPORTAMENTAL ───────────────┤
        │                          REDUCAO_RENDA_VARIAVEL ───┘
        │                                                          ↓
        └──── + NECESSIDADE_VITORIA + RISCO_RECAIDA    CAPACIDADE_ATAQUE_CONSERVADORA
                 └→ INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE
                          └→ STATUS_METODO / REVISAO_HUMANA_OBRIGATORIA
```

O grafo é acíclico — verificado. `NIVEL_CONTROLE` é raiz de tudo e depende
apenas de entrada coletada.

### 11.11. Entradas do Bloco 2 exigidas pelo motor

Oito variáveis que antes eram só coleta e agora são **entrada obrigatória do
motor**. Domínios internos fechados — não criar novos valores.

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

As regras completas de `NIVEL_CONTROLE`, `CONFIABILIDADE_DADOS` e
`INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE`, com suas ordens de avaliação, estão em
[`piq-definicoes-engine.md`](piq-definicoes-engine.md) §1, §4 e §5. Não são
reproduzidas aqui para não criar segunda redação.

### 11.9. Contagem de parâmetros

A canônica publica 45 parâmetros. Com `P_CAIXA_VS_ESTRUTURAL` deprecado,
**44 permanecem ativos**, e nenhum segue marcado "a calibrar" — todos estão
fechados ou são calibráveis com valor vigente. `RF-13` refere-se ao conjunto
ativo, não ao número publicado em v1.0.1.

## 12. Definições incorporadas — Rodada 2 (`AcaoRequerida`/`Diagnostico`)

> Origem: `specs/motor-calculo.discovery.md` (mudanças 1 a 8) e
> `specs/app-aluno.spec.md` §10 (`OQ-10`, `OQ-13`, `OQ-14`, `OQ-15`, `OQ-17`,
> `OQ-18`, todas `respondida`). Estas subseções são a fonte primária para
> `RF-28` a `RF-35` — a decisão de metodologia já está fechada nas fontes
> citadas; o texto abaixo apenas as organiza para implementação.

### 12.1. `AcaoRequerida` — contrato atual e campos novos — `RF-28`, `RF-29`

Estado atual (`engine/gates.py`):

```python
@dataclass(frozen=True, slots=True)
class AcaoRequerida:
    DIVIDA_ID: str
    descricao: str
    gate_origem: Literal[2, 3]
    prioridade_excepcional: bool = False
```

Passa a incluir:

```python
ACAO_ID: str
TIPO_ACAO: str  # domínio fechado, ver abaixo
```

- **`ACAO_ID`** — identidade estável da ação: permanece idêntica entre
  snapshots enquanto a ação for a mesma (`AC-48`). É o vínculo que o Bloco 11
  de `app-aluno` usa para saber que uma pergunta de acompanhamento se refere
  à mesma ação vista antes, mesmo depois de recalcular.
- **`TIPO_ACAO`** — domínio fechado de exatamente quatro valores, ASCII, sem
  parênteses, nomeados pelo conceito específico e não pelo termo genérico que
  a canônica usa em prosa (`INTERVENÇÃO (renegociação)`, `CORREÇÃO
  (economia)`) — decisão do especialista, `app-aluno.spec.md` §10 `OQ-13`:

  ```
  "INFORMACAO", "RENEGOCIACAO", "TROCA", "ECONOMIA"
  ```

Nenhum dos dois tem hoje linha no dicionário de variáveis da canônica (§11).

### 12.2. Derivação de `TIPO_ACAO` — `RF-30`

O discriminador é `GATE_PENDENTE` (`engine/tipos.py`), nunca `gate_origem`
(que é só `Literal[2, 3]`, insuficiente). O próprio docstring de
`GATE_PENDENTE` já afirma: *"Gates 2 e 3 compartilham `INTERVENCAO_PENDENTE`
e só se distinguem aqui"*.

| `TIPO_ACAO` | Origem |
| --- | --- |
| `"INFORMACAO"` | Gate 1 (`GATE_PENDENTE.INFORMACAO`) |
| `"RENEGOCIACAO"` | Gate 3 + `divida.RENEGOCIACAO_PENDENTE` |
| `"TROCA"` | Gate 3 + `divida.TROCA_PENDENTE` |
| `"ECONOMIA"` | Fora do fluxo de gates (§12.5) |

O Gate 3 já ramifica os três primeiros casos internamente, hoje escrevendo a
origem em `descricao` (texto livre) — a informação já existe, só passa a ser
campo tipado.

### 12.3. `DIVIDA_ID` opcional — `RF-31`

```python
DIVIDA_ID: str | None
```

Mudança de **invariante do contrato**, não acréscimo: hoje todo consumidor de
`ORDEM_ACOES` pode presumir `DIVIDA_ID` presente. Com a ação de economia
(§12.5) emitida fora do fluxo de gates, ela não tem dívida associada — é
identificada exclusivamente por `ACAO_ID`. Todo código dentro de
`motor-calculo` que hoje lê `AcaoRequerida.DIVIDA_ID` presumindo `str`
precisa passar a tratar `None` (`AC-55`, `EC-21`).

### 12.4. Gate 1 emitindo `AcaoRequerida` — `RF-32`, `RF-34`

Hoje, `aplicar_gate_1_informacao` devolve `acao=None` nos dois ramos de
bloqueio:

```python
# ramo 1 — STATUS_DIVIDA == QUITADA_A_CONFIRMAR
return ResultadoGates(..., acao=None)  # ← passa a construir AcaoRequerida

# ramo 2 — SALDO_DEVEDOR_ATUAL is DESCONHECIDO
# (dentro de compor_VALOR_RELEVANTE_PARA_QUITACAO, engine/valor_quitacao.py)
return ResultadoGates(..., acao=None)  # ← idem
```

Os dois ramos passam a construir uma `AcaoRequerida` com `TIPO_ACAO =
"INFORMACAO"` e `CAMPO_PENDENTE` conforme a tabela:

| Ramo | `CAMPO_PENDENTE` |
| --- | --- |
| `STATUS_DIVIDA == QUITADA_A_CONFIRMAR` | `"STATUS_DIVIDA"` |
| `SALDO_DEVEDOR_ATUAL is DESCONHECIDO` | `"SALDO_DEVEDOR_ATUAL"` |

```python
CAMPO_PENDENTE: Literal["STATUS_DIVIDA", "SALDO_DEVEDOR_ATUAL"]
```

O campo nomeia o **campo de `Divida` do próprio contrato do motor** — nunca
um `RegistroPergunta.ID` de coleta (o motor não conhece pergunta, só
variável de domínio; mesma fronteira que já separa `engine/` de
`collection/` no slug `app-aluno`). Quem traduz `CAMPO_PENDENTE` para a
pergunta a reabrir é a aplicação, não o motor.

**Consequência obrigatória, não efeito colateral (`AC-58` a `AC-60`).** Os
gabaritos e invariantes do slug foram fechados contra a saída atual
(`acao=None`). `GAB-03` (dívida rotativa sem saldo/pagamento,
`INFORMACAO_PENDENTE`) e `EC-17` (todas as dívidas bloqueadas, `ORDEM_ACOES`
primeiro) tocam exatamente dívidas travadas por informação — uma
`ORDEM_ACOES` que hoje vem vazia nesses casos passa a vir preenchida.
Tolerância **zero** para gates e aplicação de resíduo (seção 5 desta spec,
que cita a §10.3 da canônica) — uma divergência aqui não é absorvível por
arredondamento. Reexecutar `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes, e
atualizar as expectativas de `ORDEM_ACOES` onde mudarem, é parte desta
mudança.

### 12.5. Ação de economia fora do fluxo de gates — `RF-33`

Quando `ECONOMIA_POTENCIAL_IMEDIATA > 0` (deriva de `VALOR_GASTOS_FANTASMAS`
com `B2.10A = SIM`), o motor emite uma `AcaoRequerida` com `TIPO_ACAO =
"ECONOMIA"` e `DIVIDA_ID = None`, fora do fluxo normal de gates — gates
avaliam dívidas; economia é sobre orçamento, não sobre uma dívida
específica.

### 12.6. `Diagnostico` — dois campos extras — `RF-35`

```python
# engine/diagnostico.py — mesmo bloco de "campos comportamentais adicionais"
# já usado para NIVEL_CONTROLE, CONFIABILIDADE_DADOS, RISCO_RECAIDA,
# RISCO_COMPORTAMENTAL_GERAL, INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE
RESERVA_MOBILIZAVEL: Dinheiro
ATAQUE_IMEDIATO_RECOMENDADO: Dinheiro
```

`SnapshotOrdem` declara um único campo `diagnostico: Diagnostico`, não uma
tupla — a extensão vem como campo novo em `Diagnostico`, nunca como objeto
separado. Antes desta rodada, nenhum dos dois campos existia em `engine/*.py`
— só em condição de exibição e prosa de "uso pelo motor" na canônica.

---

> **Rastreabilidade.** Todo `RF-NN` aponta para os IDs de regra da seção 9, para
> os gabaritos da seção 10 da canônica, para a seção 11 desta spec, ou — para
> `RF-28` a `RF-35` — para a seção 12 desta spec e para `specs/app-aluno.spec.md`
> §10. Todo `AC-NN` é verificável sem reinterpretação.

## 13. Definições incorporadas — Rodada 3 (Ataque Imediato e Reserva)

> **Origem.** Documento canônico *"PIQ v1.0.1 — Definição Canônica de
> `RESERVA_MOBILIZAVEL` e `ATAQUE_IMEDIATO_RECOMENDADO` — Regras de composição,
> limites, precedência e entrada no cronograma"*, entregue pelo especialista do
> método em **2026-09-07**, em resposta a `OQ-23` (§10, Rodada 2).
> Especificação interna de desenvolvimento, marcada como **congelada**.
>
> **Regra de precedência (transcrita do documento).** Para os temas
> especificamente tratados nesta seção, estas definições prevalecem sobre
> qualquer redação anterior conflitante, incompleta ou menos específica
> constante da Matriz Canônica, Questionário Canônico, erratas, respostas
> técnicas ou documentos intermediários de desenvolvimento. A Matriz Canônica
> permanece soberana para todos os demais temas.
>
> **Declaração final (transcrita).** *"Nenhuma dessas decisões fica a critério
> do desenvolvedor."* Qualquer alteração futura exige nova versão formal da
> especificação do PIQ.

### 13.1. `RESERVA_MOBILIZAVEL`

`RESERVA_MOBILIZAVEL` **não** é percentual calculado automaticamente pelo
motor. Representa o valor máximo da reserva que o usuário aceita submeter à
análise, sem que isso constitua autorização automática de uso. Decorre da
resposta do usuário no **Bloco 4**; o motor apenas valida e limita.

As três regras se aplicam **na ordem registrada**:

```
Regra 1 — ausência de reserva ou de disposição de uso:
SE RESERVA_EXISTE = NAO
OU DISPOSICAO_USO_RESERVA = NAO
ENTAO
    RESERVA_MOBILIZAVEL = 0

Regra 2 — valor numérico conhecido em B4.03A:
SE B4.03A possuir valor numérico conhecido
ENTAO
    RESERVA_MOBILIZAVEL =
        MIN(
            RESERVA_TOTAL,
            MAX(
                0,
                VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO
            )
        )

Regra 3 — decisão adiada, desconhecimento ou reserva total desconhecida:
SE B4.03A = "Prefiro decidir somente depois de ver a análise"
OU B4.03A = "Não sei"
OU RESERVA_TOTAL = DESCONHECIDA
ENTAO
    RESERVA_MOBILIZAVEL = DESCONHECIDA
```

**TRAVA CANÔNICA.** Nunca calcular `RESERVA_MOBILIZAVEL` mediante percentual
automático de `RESERVA_TOTAL`. Fórmulas **expressamente proibidas** na v1.0.1:

```
RESERVA_MOBILIZAVEL = 30% × RESERVA_TOTAL                     ← PROIBIDA
RESERVA_MOBILIZAVEL = 50% × RESERVA_TOTAL                     ← PROIBIDA
RESERVA_MOBILIZAVEL = RESERVA_TOTAL - RESERVA_MINIMA_PADRAO   ← PROIBIDA
```

**Reserva desconhecida.** Quando `RESERVA_MOBILIZAVEL = DESCONHECIDA`, nenhum
valor da reserva entra numericamente no recomendado ou aprovado até existir
decisão válida. O estado `DESCONHECIDA` **não** é convertido silenciosamente em
zero como informação — a engine registra a pendência. (Alinha-se ao
`DESCONHECIDO` já existente em `engine/tipos.py`.)

### 13.2. `ATAQUE_IMEDIATO_POTENCIAL`

```
ATAQUE_IMEDIATO_POTENCIAL =
      DINHEIRO_DISPONIVEL
    + RESERVA_MOBILIZAVEL
    + INVESTIMENTOS_LIQUIDOS_MOBILIZAVEIS
    + RECURSOS_EXTRAORDINARIOS_POTENCIAIS
    + ATIVOS_LIQUIDOS_CLASSIFICADOS_COMO
          MOBILIZACAO_POSSIVEL
          OU MOBILIZACAO_RECOMENDAVEL
```

É **apenas potencial**: não entra no cronograma, não é recomendação, não é
aprovação, e não significa que todos os recursos devam ser utilizados.

### 13.3. `ATAQUE_IMEDIATO_RECOMENDADO`

```
ATAQUE_IMEDIATO_RECOMENDADO =
    MIN(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL,
          CAIXA_RECOMENDADO
        + INVESTIMENTOS_RECOMENDADOS
        + EXTRAORDINARIOS_RECOMENDADOS
        + ATIVOS_RECOMENDADOS
        + RESERVA_RECOMENDADA
    )
```

Componentes:

| Componente | Regra |
| --- | --- |
| `CAIXA_RECOMENDADO` | `= DINHEIRO_DISPONIVEL`, desde que realmente livre, não correspondente a obrigação já contabilizada, não comprometido com despesa conhecida e não contado em outra variável. Valor comprometido **não** integra |
| `INVESTIMENTOS_RECOMENDADOS` | Soma do valor líquido realizável dos investimentos **com liquidez** E classificados `MOBILIZACAO_RECOMENDAVEL`. Apenas `MOBILIZACAO_POSSIVEL` fica no potencial, não entra automaticamente no recomendado |
| `ATIVOS_RECOMENDADOS` | `Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` dos ativos `MOBILIZACAO_RECOMENDAVEL`. `MOBILIZACAO_COM_RESSALVAS` e `NAO_MOBILIZAR` **não** entram automaticamente |
| `EXTRAORDINARIOS_RECOMENDADOS` | Recursos extraordinários confirmados, disponíveis, não comprometidos e aptos **no momento atual**. Recurso apenas previsto para o futuro não compõe o recomendado atual |
| `RESERVA_RECOMENDADA` | Ver §13.4 — último componente mobilizado |

### 13.4. `RESERVA_RECOMENDADA` — reserva como último componente

A reserva é recurso **protetivo**: só é considerada depois dos recursos não
protetivos recomendáveis.

```
NECESSIDADE_RESIDUAL =
    MAX(
        0,
          NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL
        - CAIXA_RECOMENDADO
        - INVESTIMENTOS_RECOMENDADOS
        - EXTRAORDINARIOS_RECOMENDADOS
        - ATIVOS_RECOMENDADOS
    )

SE RESULTADO_MENSAL_ATUAL < 0
ENTAO
    RESERVA_RECOMENDADA = 0

Nos demais casos:
RESERVA_RECOMENDADA =
    MIN(
        RESERVA_MOBILIZAVEL,
        NECESSIDADE_RESIDUAL
    )
```

**TRAVA — MODO ESTABILIZAÇÃO.** Se `RESULTADO_MENSAL_ATUAL < 0`, então
`MODO_ESTABILIZACAO = SIM` e `RESERVA_RECOMENDADA = 0` para ataque ordinário de
quitação. A reserva não pode ser usada para mascarar déficit estrutural.
(`MODO_ESTABILIZACAO` já existe em `engine/diagnostico.py`, derivado da mesma
condição de déficit — ver §11.)

**REGRA CANÔNICA.** A existência de `RESERVA_MOBILIZAVEL`, isoladamente, **nunca**
é justificativa suficiente para recomendar sua utilização. Exige finalidade
concreta e justificável, tendo passado pelos gates aplicáveis. Finalidades
aceitáveis: contenção de risco; oportunidade executável; quitação
estrategicamente vantajosa; amortização com benefício econômico relevante;
redução de custo futuro; eliminação de obrigação cuja manutenção produza dano
financeiro material.

### 13.5. `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`

Valor máximo que faz sentido aplicar imediatamente, considerando o estado do
plano **após os gates**. Corresponde ao necessário para: executar ações
financeiras imediatas elegíveis; aproveitar oportunidades executáveis; realizar
quitações e amortizações permitidas; aplicar ataque extraordinário sobre dívidas
atualmente elegíveis.

```
ATAQUE_IMEDIATO_RECOMENDADO <= NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL
ATAQUE_IMEDIATO_RECOMENDADO <= ATAQUE_IMEDIATO_POTENCIAL
```

Nunca recomendar recurso sem destinação financeira elegível.

### 13.6. `ATAQUE_IMEDIATO_APROVADO` e hierarquia

Parcela do recomendado que o usuário **confirma** que utilizará.

```
0 <= ATAQUE_IMEDIATO_APROVADO <= ATAQUE_IMEDIATO_RECOMENDADO
```

**HIERARQUIA CANÔNICA:**

```
ATAQUE_IMEDIATO_POTENCIAL >= ATAQUE_IMEDIATO_RECOMENDADO
                          >= ATAQUE_IMEDIATO_APROVADO >= 0
```

| Estágio | Interpretação canônica | Entra no cronograma? |
| --- | --- | --- |
| `ATAQUE_IMEDIATO_POTENCIAL` | Poderia ser utilizado | NÃO |
| `ATAQUE_IMEDIATO_RECOMENDADO` | O motor considera estrategicamente adequado | NÃO |
| `ATAQUE_IMEDIATO_APROVADO` | O usuário confirmou que efetivamente utilizará | **SIM** |

**Somente `ATAQUE_IMEDIATO_APROVADO` entra no cronograma-base da engine.**

### 13.7. Ordem de utilização dos recursos

Precedência metodológica de composição do `ATAQUE_IMEDIATO_RECOMENDADO`:

| Ordem | Componente | Regra |
| --- | --- | --- |
| 1 | `DINHEIRO_DISPONIVEL` | Usar se realmente livre e não comprometido |
| 2 | `INVESTIMENTOS_RECOMENDADOS` | Somente líquidos e classificados como recomendáveis |
| 3 | `EXTRAORDINARIOS_RECOMENDADOS` | Somente confirmados e disponíveis |
| 4 | `ATIVOS_RECOMENDADOS` | Somente `MOBILIZACAO_RECOMENDAVEL` |
| 5 | `RESERVA_RECOMENDADA` | Último componente; apenas necessidade residual e se estrategicamente justificado |

### 13.8. Travas de dupla contagem

**TRAVA.** Nenhum recurso pode aparecer simultaneamente em dois componentes do
ataque. Cada recurso deve possuir **origem econômica única** no cálculo.

Casos expressamente vedados:

- reserva aplicada em CDB contada como `RESERVA_MOBILIZAVEL` **e** novamente
  como `INVESTIMENTOS_RECOMENDADOS`;
- recurso extraordinário aprovado entrando como `ATAQUE_IMEDIATO_APROVADO` **e**
  novamente como evento independente;
- dinheiro de venda de ativo contado como ativo realizável **e** como dinheiro
  disponível após a venda;
- valor já comprometido com obrigação contado como `DINHEIRO_DISPONIVEL`.

**Classificação econômica prevalece sobre o instrumento financeiro.** Se um
investimento já foi declarado componente da reserva, pertence à categoria
RESERVA e não é contabilizado novamente como investimento adicional.

### 13.9. Pseudocódigo de referência

> **Nota de implementação (transcrita).** *"O pseudocódigo é ilustrativo. A
> tecnologia pode variar, mas o resultado lógico não pode variar."*

```
deriveReservaMobilizavel():
    if RESERVA_EXISTE == NAO:
        return 0
    if DISPOSICAO_USO_RESERVA == NAO:
        return 0
    if RESERVA_TOTAL is DESCONHECIDA:
        return DESCONHECIDA
    if VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO is DESCONHECIDO:
        return DESCONHECIDA
    return min(
        RESERVA_TOTAL,
        max(0, VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO)
    )

deriveReservaRecomendada():
    if RESULTADO_MENSAL_ATUAL < 0:
        return 0
    necessidadeResidual = max(
        0,
          NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL
        - CAIXA_RECOMENDADO
        - INVESTIMENTOS_RECOMENDADOS
        - EXTRAORDINARIOS_RECOMENDADOS
        - ATIVOS_RECOMENDADOS
    )
    if RESERVA_MOBILIZAVEL is DESCONHECIDA:
        return 0 até decisão válida
    return min(RESERVA_MOBILIZAVEL, necessidadeResidual)

deriveAtaqueImediatoRecomendado():
    recursosRecomendados =
          CAIXA_RECOMENDADO
        + INVESTIMENTOS_RECOMENDADOS
        + EXTRAORDINARIOS_RECOMENDADOS
        + ATIVOS_RECOMENDADOS
        + RESERVA_RECOMENDADA
    return min(
        NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL,
        recursosRecomendados
    )
```

### 13.10. Testes mínimos de homologação (`GAB-AI-01` a `GAB-AI-08`)

> A implementação deve reproduzir **exatamente** estes resultados. IDs locais
> `GAB-AI-NN` atribuídos por esta spec para rastreabilidade; o documento de
> origem os numera de 1 a 8.

| ID | Cenário | Resultado esperado |
| --- | --- | --- |
| `GAB-AI-01` | `RESERVA_TOTAL = 20.000`; usuário aceita analisar `5.000` | `RESERVA_MOBILIZAVEL = 5.000` |
| `GAB-AI-02` | `RESERVA_TOTAL = 20.000`; usuário informa máximo de `30.000` | `RESERVA_MOBILIZAVEL = 20.000` (limitado pelo total) |
| `GAB-AI-03` | `DISPOSICAO_USO_RESERVA = NAO` | `RESERVA_MOBILIZAVEL = 0` |
| `GAB-AI-04` | Usuário responde "Prefiro decidir depois" | `RESERVA_MOBILIZAVEL = DESCONHECIDA`; nenhum valor da reserva entra no recomendado |
| `GAB-AI-05` | `RESULTADO_MENSAL_ATUAL = -1.000`; `RESERVA_MOBILIZAVEL = 20.000` | `MODO_ESTABILIZACAO = SIM`; `RESERVA_RECOMENDADA = 0` |
| `GAB-AI-06` | `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = 20.000`; `CAIXA_RECOMENDADO = 5.000`; `INVESTIMENTOS_RECOMENDADOS = 7.000`; `EXTRAORDINARIOS_RECOMENDADOS = 0`; `ATIVOS_RECOMENDADOS = 0`; `RESERVA_MOBILIZAVEL = 10.000` | `NECESSIDADE_RESIDUAL = 8.000`; `RESERVA_RECOMENDADA = 8.000`; `ATAQUE_IMEDIATO_RECOMENDADO = 20.000` |
| `GAB-AI-07` | `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = 10.000`; recursos recomendáveis totais `= 25.000` | `ATAQUE_IMEDIATO_RECOMENDADO = 10.000` (**não** 25.000) |
| `GAB-AI-08` | `ATAQUE_IMEDIATO_RECOMENDADO = 15.000`; usuário confirma apenas `9.000` | `ATAQUE_IMEDIATO_APROVADO = 9.000`; cronograma-base utiliza apenas 9.000 |

### 13.11. Tabela mestra de variáveis

| Variável | Origem | Regra | Entra no cronograma? |
| --- | --- | --- | --- |
| `RESERVA_TOTAL` | Usuário | Valor total da reserva | NÃO |
| `RESERVA_MOBILIZAVEL` | Usuário + validação | Máximo aceito para análise | NÃO |
| `ATAQUE_IMEDIATO_POTENCIAL` | Motor | Soma de recursos potencialmente utilizáveis | NÃO |
| `ATAQUE_IMEDIATO_RECOMENDADO` | Motor | Parcela estrategicamente adequada | NÃO |
| `ATAQUE_IMEDIATO_APROVADO` | Usuário | Parcela confirmada do recomendado | **SIM** |
| `RESERVA_RECOMENDADA` | Motor | Parcela da reserva após recursos não protetivos | NÃO isoladamente |
| `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` | Motor | Limite útil de aplicação imediata | NÃO |

## 14. Definições incorporadas — Rodada 4 (Fechamento: Necessidade Financeira Imediata e Classificação de Ativos)

> **Origem.** Documento canônico *"PIQ v1.0.1 — Fechamento Canônico —
> Necessidade Financeira Imediata e Classificação de Ativos"*, entregue pelo
> especialista do método em **2026-09-09**, em resposta a `OQ-29`, `OQ-26` e
> `OQ-27` (§10, Rodada 3). Especificação interna de desenvolvimento, marcada
> como **congelada**.
>
> **Regra de precedência (transcrita do documento).** Para os temas
> especificamente tratados nesta seção, estas definições prevalecem sobre
> qualquer redação anterior conflitante, incompleta ou menos específica
> constante da Matriz Canônica, Questionário Canônico, erratas, respostas
> técnicas ou documentos intermediários de desenvolvimento. A Matriz Canônica
> permanece soberana para todos os demais temas.
>
> **Declaração final (transcrita).** *"Nenhuma dessas decisões fica a critério
> do desenvolvedor."* Qualquer alteração futura exige nova versão formal da
> especificação do PIQ.

### 14.0. Objetivo

Fecha três lacunas: a fórmula de `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`; a
regra de classificação dos ativos; e a fórmula de
`VALOR_LIQUIDO_REALIZAVEL_ATIVO`/`VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`.
Nenhuma pergunta nova ao usuário é criada.

### 14.1. `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`

Representa o teto monetário objetivo do valor que pode receber aplicação
imediata de recursos, após os gates. **Não** é subconjunto subjetivo
"estrategicamente vantajoso" — é soma objetiva.

```
NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL = Σ NECESSIDADE_IMEDIATA_DIVIDA(d) para todas as dívidas do inventário
```

#### 14.1.1. `NECESSIDADE_IMEDIATA_DIVIDA(divida)` — avaliada em ordem estrita

```
SE Gate 1 = PENDENTE: NECESSIDADE_IMEDIATA_DIVIDA = 0
SENAO SE Gate 3 = PENDENTE: NECESSIDADE_IMEDIATA_DIVIDA = 0
SENAO SE existe ação financeira imediata, decorrente de Gate 2 ou Gate 4, executável agora E com valor monetário conhecido:
    NECESSIDADE_IMEDIATA_DIVIDA = VALOR_ACAO_FINANCEIRA_IMEDIATA
SENAO SE DIVIDA_STATUS_ESTRATEGICO em {PRONTA_PARA_ORDENACAO, EM_ATAQUE}:
    NECESSIDADE_IMEDIATA_DIVIDA = VALOR_RELEVANTE_PARA_QUITACAO
SENAO: NECESSIDADE_IMEDIATA_DIVIDA = 0
```

#### 14.1.2. Interpretação do `VALOR_RELEVANTE_PARA_QUITACAO`

Para dívida ordinariamente elegível, entra o `VALOR_RELEVANTE_PARA_QUITACAO`
integral, não fração "vantajosa".

> **REGRA CANÔNICA.** A variável responde "quanto poderia ser usado agora", não
> "quanto vale a pena disponibilizar" (isso é `ATAQUE_IMEDIATO_RECOMENDADO`);
> "qual dívida recebe o dinheiro" pertence ao método/ordem de ataque.

### 14.2. Tratamento monetário da `ORDEM_ACOES`

`ORDEM_ACOES` não é somada genericamente. Cada ação é analisada por desembolso
imediato ou não.

#### 14.2.1. `VALOR_ACAO_FINANCEIRA_IMEDIATA`

Variável interna derivada, **não** nova pergunta — vem de valor já conhecido na
operação/proposta/acordo/oportunidade/regularização/intervenção.

```
SE a ação não exige desembolso financeiro imediato: VALOR_ACAO_FINANCEIRA_IMEDIATA = 0
SE a ação exige desembolso financeiro imediato E o valor é conhecido:
    VALOR_ACAO_FINANCEIRA_IMEDIATA = valor monetário necessário à execução da ação
```

Exemplos **sem** desembolso: solicitar documento, consultar proposta,
renegociar, conferir saldo, formalizar pedido, aguardar retorno, revisar
contrato.

Exemplo **com** desembolso: oferta válida de quitação por R$ 8.000 →
`VALOR_ACAO_FINANCEIRA_IMEDIATA = 8.000`.

#### 14.2.2. Valor desconhecido em ação prioritária

```
VALOR_ACAO_FINANCEIRA_IMEDIATA = DESCONHECIDO
```

Se essa ação tem precedência material sobre uso do caixa:
`STATUS_ATAQUE_IMEDIATO = PROVISORIO` (ou equivalente já existente no modelo de
status). O motor não deve usar recursos em outra dívida e depois descobrir que
precisava reservar para ação prioritária.

#### 14.2.3. Dupla contagem entre ação e dívida

> **TRAVA DE DUPLA CONTAGEM.** Uma mesma dívida entra uma única vez em
> `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`. Se a dívida está temporariamente
> direcionada a ação financeira imediata (Gate 2/4), entra
> `VALOR_ACAO_FINANCEIRA_IMEDIATA` e **não** entra `VALOR_RELEVANTE_PARA_QUITACAO`
> para a mesma dívida naquele estado. Depois de resolvido o gate, volta ao
> estoque ordinário elegível.

#### 14.2.4. Relação com `ATAQUE_IMEDIATO_RECOMENDADO`

Fórmula do documento anterior (Rodada 3) é integralmente preservada:

```
ATAQUE_IMEDIATO_RECOMENDADO = MIN(NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL, RECURSOS_ESTRATEGICAMENTE_RECOMENDADOS)
```

`RECURSOS_ESTRATEGICAMENTE_RECOMENDADOS` = soma de `CAIXA_RECOMENDADO` +
`INVESTIMENTOS_RECOMENDADOS` + `EXTRAORDINARIOS_RECOMENDADOS` +
`ATIVOS_RECOMENDADOS` + `RESERVA_RECOMENDADA`.

### 14.3. Classificação determinística dos ativos

Derivada exclusivamente pelo motor. **Nunca** perguntar diretamente ao usuário
se ativo é recomendável/deve ser vendido/é mobilizável. Categorias:
`NAO_MOBILIZAR`, `MOBILIZACAO_COM_RESSALVAS`, `MOBILIZACAO_POSSIVEL`,
`MOBILIZACAO_RECOMENDAVEL`. Considera conforme tipo: disposição do usuário,
essencialidade, liquidez, custo de desmobilização, passivo vinculado, valor
líquido realizável, renda recorrente, custo recorrente, impacto financeiro da
venda, possibilidade de substituição.

#### 14.3.1. Investimentos — regras em ordem de precedência

```
Regra 1 — bloqueio: SE DISPOSICAO_USO_INVESTIMENTO = NAO OU LIQUIDEZ_INVESTIMENTOS = BLOQUEADO: CLASSIFICACAO_ATIVO = NAO_MOBILIZAR
Regra 2 — dado desconhecido: SE valor/liquidez/custo p/ apurar valor líquido forem desconhecidos: CLASSIFICACAO_ATIVO = MOBILIZACAO_COM_RESSALVAS
Regra 3 — disposição condicional: SE DISPOSICAO_USO_INVESTIMENTO = TALVEZ E o investimento pode efetivamente ser resgatado: CLASSIFICACAO_ATIVO = MOBILIZACAO_POSSIVEL
Regra 4 — líquido/disponível/sem custo: SE DISPOSICAO_USO_INVESTIMENTO = SIM E LIQUIDEZ_INVESTIMENTOS em {D0,D1,D7} E não existe custo/perda relevante conhecida E VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL > 0: CLASSIFICACAO_ATIVO = MOBILIZACAO_RECOMENDAVEL
Regra 5 — custo conhecido ou D30: SE DISPOSICAO_USO_INVESTIMENTO = SIM E (existe custo conhecido de saída OU LIQUIDEZ_INVESTIMENTOS = D30): CLASSIFICACAO_ATIVO = MOBILIZACAO_POSSIVEL
Regra 6 — liquidez longa/indeterminado: SE LIQUIDEZ_INVESTIMENTOS = MAIS_30 OU custo/perda indeterminado OU consequência material não quantificada: CLASSIFICACAO_ATIVO = MOBILIZACAO_COM_RESSALVAS
```

##### 14.3.1.1. Tipo do investimento não determina isoladamente a classificação

Não presumir: todo CDB = recomendável; toda previdência = não mobilizar; toda
ação = possível; toda poupança = recomendável. Usar dados efetivamente
coletados.

### 14.4. Imóveis, veículos e outros ativos

Variável normalizada: `POSSIBILIDADE_VENDA em {NAO, EXTREMO, TALVEZ, SIM, JA_PRETENDE}`.
Regras das seções 14.4–14.9 em ordem de precedência.

#### 14.4.1. `SE POSSIBILIDADE_VENDA = NAO: CLASSIFICACAO_ATIVO = NAO_MOBILIZAR`

#### 14.4.2. Dados materiais desconhecidos

Quando valor líquido realizável não pode ser calculado por ausência de
informação material (valor do ativo, saldo passivo vinculado, custo
desmobilização desconhecidos): `CLASSIFICACAO_ATIVO = MOBILIZACAO_COM_RESSALVAS`.
Não assumir zero.

#### 14.4.3. Valor líquido disponível = 0

Ativo não gera liquidez imediata. Se venda ainda produz benefício relevante
(ex: redução de custo mensal): `CLASSIFICACAO_ATIVO = MOBILIZACAO_COM_RESSALVAS`.
Economia recorrente tratada separadamente em `ECONOMIA_RECORRENTE_POTENCIAL`.

### 14.5. Regra de essencialidade

> **REGRA CANÔNICA.** Ativo `ESSENCIAL` nunca pode ser
> `MOBILIZACAO_RECOMENDAVEL` automaticamente.

```
SE ESSENCIALIDADE = ESSENCIAL:
    SE POSSIBILIDADE_VENDA = NAO: CLASSIFICACAO_ATIVO = NAO_MOBILIZAR
    SE POSSIBILIDADE_VENDA = EXTREMO: CLASSIFICACAO_ATIVO = MOBILIZACAO_COM_RESSALVAS
    SE POSSIBILIDADE_VENDA em {TALVEZ,SIM,JA_PRETENDE}: CLASSIFICACAO_ATIVO = MOBILIZACAO_COM_RESSALVAS
```

Essencialidade prevalece sobre disposição de venda.

### 14.6. Ativo importante/parcialmente essencial

```
SE ESSENCIALIDADE em {IMPORTANTE, PARCIAL}:
    SE POSSIBILIDADE_VENDA em {EXTREMO,TALVEZ}: CLASSIFICACAO_ATIVO = MOBILIZACAO_COM_RESSALVAS
    SE POSSIBILIDADE_VENDA em {SIM,JA_PRETENDE}: CLASSIFICACAO_ATIVO = MOBILIZACAO_POSSIVEL
```

### 14.7. Ativo não essencial

```
SE ESSENCIALIDADE = NAO_ESSENCIAL:
    SE POSSIBILIDADE_VENDA = EXTREMO: CLASSIFICACAO_ATIVO = MOBILIZACAO_COM_RESSALVAS
    SE POSSIBILIDADE_VENDA = TALVEZ: CLASSIFICACAO_ATIVO = MOBILIZACAO_POSSIVEL
    SE POSSIBILIDADE_VENDA em {SIM,JA_PRETENDE}: avaliar efeito recorrente (14.8/14.9)
```

### 14.8. Efeito financeiro recorrente

```
FLUXO_LIQUIDO_RECORRENTE_ATIVO = RENDA_RECORRENTE_ATIVO - CUSTO_RECORRENTE_ATIVO
```

Não incluir novamente parcelas de financiamento já tratadas no inventário de
dívidas.

### 14.9. Ativo não essencial com venda aceita

```
SE ESSENCIALIDADE=NAO_ESSENCIAL E POSSIBILIDADE_VENDA em {SIM,JA_PRETENDE} E VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL>0 E FLUXO_LIQUIDO_RECORRENTE_ATIVO<=0:
    CLASSIFICACAO_ATIVO = MOBILIZACAO_RECOMENDAVEL
SE ESSENCIALIDADE=NAO_ESSENCIAL E POSSIBILIDADE_VENDA em {SIM,JA_PRETENDE} E VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL>0 E FLUXO_LIQUIDO_RECORRENTE_ATIVO>0:
    CLASSIFICACAO_ATIVO = MOBILIZACAO_POSSIVEL
```

Motivo da 2ª regra: venda produz liquidez mas elimina fluxo recorrente
positivo.

```
SE o efeito recorrente for DESCONHECIDO: CLASSIFICACAO_ATIVO = MOBILIZACAO_POSSIVEL
```

Enquanto desconhecido, nunca `MOBILIZACAO_RECOMENDAVEL`.

### 14.10. Significado de `MOBILIZACAO_RECOMENDAVEL`

> **ATENÇÃO.** Não significa venda obrigatória, execução automática,
> autorização do aluno ou entrada automática no cronograma. Significa apenas
> apto a compor `ATIVOS_RECOMENDADOS`. Valor ainda passa por:
> `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`, demais gates, regra de ataque
> recomendado, confirmação do usuário.

### 14.11. Significado de `MOBILIZACAO_POSSIVEL`

Pode compor `ATAQUE_IMEDIATO_POTENCIAL`, mas **não** entra automaticamente em
`ATIVOS_RECOMENDADOS` nem `ATAQUE_IMEDIATO_RECOMENDADO`.

### 14.12. Fórmula canônica do valor líquido realizável

#### 14.12.1. `VALOR_LIQUIDO_REALIZAVEL_ATIVO`

```
VALOR_LIQUIDO_REALIZAVEL_ATIVO = VALOR_ESTIMADO_ATIVO - SALDO_PASSIVO_VINCULADO - CUSTOS_ESTIMADOS_DESMOBILIZACAO
```

#### 14.12.2. `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`

```
VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL = MAX(0, VALOR_LIQUIDO_REALIZAVEL_ATIVO)
```

> **REGRA CANÔNICA.** As duas variáveis **não** são a mesma. A primeira pode
> ser negativa. A segunda **nunca** pode ser negativa.

#### 14.12.3. Exemplos de cálculo

| Componente | Exemplo positivo | Exemplo negativo |
| --- | --- | --- |
| `VALOR_ESTIMADO_ATIVO` | 100.000 | 100.000 |
| `SALDO_PASSIVO_VINCULADO` | 70.000 | 105.000 |
| `CUSTOS_ESTIMADOS_DESMOBILIZACAO` | 5.000 | 5.000 |
| `VALOR_LIQUIDO_REALIZAVEL_ATIVO` | 25.000 | -10.000 |
| `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` | 25.000 | 0 |

#### 14.12.4. Normalização do passivo vinculado

```
SE não existe passivo vinculado: SALDO_PASSIVO_VINCULADO = 0
SE existe e saldo conhecido: usar valor conhecido
SE existe e saldo desconhecido: SALDO_PASSIVO_VINCULADO = DESCONHECIDO; VALOR_LIQUIDO_REALIZAVEL_ATIVO = DESCONHECIDO
```

Não assumir zero.

#### 14.12.5. Normalização dos custos de desmobilização

```
SE não existe custo relevante conhecido: CUSTOS_ESTIMADOS_DESMOBILIZACAO = 0
SE custo informado é monetário: usar diretamente
SE custo é percentual: CUSTOS_ESTIMADOS_DESMOBILIZACAO = VALOR_ESTIMADO_ATIVO × PERCENTUAL_CUSTO_DESMOBILIZACAO
SE existe custo e é desconhecido: CUSTOS_ESTIMADOS_DESMOBILIZACAO = DESCONHECIDO; VALOR_LIQUIDO_REALIZAVEL_ATIVO = DESCONHECIDO
```

#### 14.12.6. Investimentos

Para investimentos, `SALDO_PASSIVO_VINCULADO = 0` (salvo regra futura formal).

```
VALOR_LIQUIDO_REALIZAVEL_ATIVO = VALOR_ESTIMADO_ATIVO - CUSTO_DESMOBILIZACAO_INVESTIMENTOS
SE CUSTO_DESMOBILIZACAO_INVESTIMENTOS_EXISTE = NAO: CUSTO_DESMOBILIZACAO_INVESTIMENTOS = 0
SE CUSTO_DESMOBILIZACAO_INVESTIMENTOS_EXISTE em {SIM,TALVEZ,NAO_SEI} E valor não conhecido: VALOR_LIQUIDO_REALIZAVEL_ATIVO = DESCONHECIDO
```

### 14.13. Agregados patrimoniais

#### 14.13.1. `PATRIMONIO_MOBILIZAVEL`

```
PATRIMONIO_MOBILIZAVEL = Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL dos ativos cuja classificação seja diferente de NAO_MOBILIZAR
```

Não incluir ativos com valor `DESCONHECIDO` como se fossem zero —
incompletude deve ser registrada.

#### 14.13.2. `PATRIMONIO_ESTRATEGICAMENTE_MOBILIZAVEL`

```
PATRIMONIO_ESTRATEGICAMENTE_MOBILIZAVEL = Σ VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL dos ativos classificados como MOBILIZACAO_POSSIVEL ou MOBILIZACAO_RECOMENDAVEL
```

Somente ativos `MOBILIZACAO_RECOMENDAVEL` entram automaticamente em
`ATIVOS_RECOMENDADOS`.

### 14.14. Pseudocódigo de referência

```
deriveNecessidadeImediataDivida(divida):
    if divida.gate1 == PENDENTE: return 0
    if divida.gate3 == PENDENTE: return 0
    if divida.temAcaoFinanceiraImediataGate2Ou4:
        if divida.valorAcaoFinanceiraImediata is DESCONHECIDO: return DESCONHECIDO
        return divida.valorAcaoFinanceiraImediata
    if divida.statusEstrategico in {PRONTA_PARA_ORDENACAO, EM_ATAQUE}:
        return divida.valorRelevanteParaQuitacao
    return 0
```

```
deriveNecessidadeFinanceiraImediataElegivel():
    total = 0
    for divida in DIVIDAS:
        valor = deriveNecessidadeImediataDivida(divida)
        if valor is DESCONHECIDO:
            sinalizarIncompletudeMaterial()
        else:
            total += valor
    return total
```

```
deriveValorLiquidoRealizavelAtivo(ativo):
    if ativo.valorEstimado is DESCONHECIDO: return DESCONHECIDO
    if ativo.possuiPassivo == NAO: saldoPassivo = 0
    else if ativo.saldoPassivo is DESCONHECIDO: return DESCONHECIDO
    else: saldoPassivo = ativo.saldoPassivo
    if ativo.custoDesmobilizacao == NAO_EXISTE: custo = 0
    else if ativo.custoDesmobilizacao is DESCONHECIDO: return DESCONHECIDO
    else: custo = ativo.custoDesmobilizacao
    return ativo.valorEstimado - saldoPassivo - custo

deriveValorLiquidoRealizavelAtivoDisponivel(ativo):
    valor = deriveValorLiquidoRealizavelAtivo(ativo)
    if valor is DESCONHECIDO: return DESCONHECIDO
    return max(0, valor)
```

```
classifyInvestment(investimento):
    if investimento.disposicao == NAO: return NAO_MOBILIZAR
    if investimento.liquidez == BLOQUEADO: return NAO_MOBILIZAR
    if investimento.valorLiquidoDisponivel is DESCONHECIDO: return MOBILIZACAO_COM_RESSALVAS
    if investimento.disposicao == TALVEZ: return MOBILIZACAO_POSSIVEL
    if investimento.disposicao == SIM:
        if investimento.liquidez in {D0,D1,D7} and investimento.semCustoPerdaRelevante and investimento.valorLiquidoDisponivel > 0:
            return MOBILIZACAO_RECOMENDAVEL
        if investimento.liquidez == D30: return MOBILIZACAO_POSSIVEL
        if investimento.temCustoConhecido: return MOBILIZACAO_POSSIVEL
        if investimento.liquidez == MAIS_30: return MOBILIZACAO_COM_RESSALVAS
    return MOBILIZACAO_COM_RESSALVAS
```

```
classifyPhysicalAsset(ativo):
    if ativo.possibilidadeVenda == NAO: return NAO_MOBILIZAR
    if ativo.valorLiquidoDisponivel is DESCONHECIDO: return MOBILIZACAO_COM_RESSALVAS
    if ativo.valorLiquidoDisponivel == 0: return MOBILIZACAO_COM_RESSALVAS
    if ativo.essencialidade == ESSENCIAL: return MOBILIZACAO_COM_RESSALVAS
    if ativo.essencialidade in {IMPORTANTE, PARCIAL}:
        if ativo.possibilidadeVenda in {EXTREMO, TALVEZ}: return MOBILIZACAO_COM_RESSALVAS
        if ativo.possibilidadeVenda in {SIM, JA_PRETENDE}: return MOBILIZACAO_POSSIVEL
    if ativo.essencialidade == NAO_ESSENCIAL:
        if ativo.possibilidadeVenda == EXTREMO: return MOBILIZACAO_COM_RESSALVAS
        if ativo.possibilidadeVenda == TALVEZ: return MOBILIZACAO_POSSIVEL
        if ativo.possibilidadeVenda in {SIM, JA_PRETENDE}:
            if ativo.fluxoLiquidoRecorrente is DESCONHECIDO: return MOBILIZACAO_POSSIVEL
            if ativo.fluxoLiquidoRecorrente <= 0: return MOBILIZACAO_RECOMENDAVEL
            return MOBILIZACAO_POSSIVEL
    return MOBILIZACAO_COM_RESSALVAS
```

### 14.15. Matriz resumida de classificação

| Tipo de ativo | Condição | Classificação | Efeito no potencial | Efeito no recomendado |
| --- | --- | --- | --- | --- |
| Investimento | Disposição NAO | NAO_MOBILIZAR | Não | Não |
| Investimento | Bloqueado | NAO_MOBILIZAR | Não | Não |
| Investimento | TALVEZ + resgatável | MOBILIZACAO_POSSIVEL | Sim | Não |
| Investimento | SIM + D0/D1/D7 + sem custo relevante + líquido > 0 | MOBILIZACAO_RECOMENDAVEL | Sim | Sim |
| Investimento | SIM + D30 ou custo conhecido | MOBILIZACAO_POSSIVEL | Sim | Não |
| Ativo físico | Disposição NAO | NAO_MOBILIZAR | Não | Não |
| Ativo físico | Essencial | MOBILIZACAO_COM_RESSALVAS | Conforme regra | Não |
| Ativo físico | Importante + SIM | MOBILIZACAO_POSSIVEL | Sim | Não |
| Ativo físico | Não essencial + SIM + fluxo líquido <= 0 | MOBILIZACAO_RECOMENDAVEL | Sim | Sim |
| Ativo físico | Não essencial + SIM + fluxo líquido > 0 | MOBILIZACAO_POSSIVEL | Sim | Não |

### 14.16. Testes mínimos de homologação (`GAB-NFI-01` a `GAB-NFI-12`)

> IDs locais `GAB-NFI-NN` atribuídos por esta spec para rastreabilidade; o
> documento de origem os numera de 1 a 12.

| ID | Cenário | Resultado esperado |
| --- | --- | --- |
| `GAB-NFI-01` — dívida ordinária elegível | `VALOR_RELEVANTE_PARA_QUITACAO=20.000`, `STATUS=PRONTA_PARA_ORDENACAO` | `NECESSIDADE_IMEDIATA_DIVIDA=20.000` |
| `GAB-NFI-02` — Gate 1 pendente | `VALOR_RELEVANTE_PARA_QUITACAO=20.000`, `Gate1=PENDENTE` | `NECESSIDADE_IMEDIATA_DIVIDA=0` |
| `GAB-NFI-03` — Gate 3 pendente | `Gate3=PENDENTE` | `NECESSIDADE_IMEDIATA_DIVIDA=0` |
| `GAB-NFI-04` — oportunidade Gate 4 | `VALOR_ACAO_FINANCEIRA_IMEDIATA=8.000`, `VALOR_RELEVANTE_PARA_QUITACAO=15.000` | `NECESSIDADE_IMEDIATA_DIVIDA=8.000` (não somar 8.000+15.000) |
| `GAB-NFI-05` — ação sem valor monetário | Ação=solicitar proposta | `VALOR_ACAO_FINANCEIRA_IMEDIATA=0` |
| `GAB-NFI-06` — investimento bloqueado | `DISPOSICAO=SIM`, `LIQUIDEZ=BLOQUEADO` | `NAO_MOBILIZAR` |
| `GAB-NFI-07` — investimento líquido e disponível | `DISPOSICAO=SIM`, `LIQUIDEZ=D1`, sem custo relevante, valor líquido=10.000 | `MOBILIZACAO_RECOMENDAVEL` |
| `GAB-NFI-08` — investimento com disposição TALVEZ | `DISPOSICAO=TALVEZ`, resgatável | `MOBILIZACAO_POSSIVEL` |
| `GAB-NFI-09` — imóvel essencial | `ESSENCIALIDADE=ESSENCIAL`, `POSSIBILIDADE_VENDA=SIM` | `MOBILIZACAO_COM_RESSALVAS` (nunca RECOMENDAVEL) |
| `GAB-NFI-10` — ativo não essencial com fluxo negativo | `ESSENCIALIDADE=NAO_ESSENCIAL`, `VENDA=SIM`, `VALOR_LIQUIDO_DISPONIVEL=30.000`, `FLUXO=-500` | `MOBILIZACAO_RECOMENDAVEL` |
| `GAB-NFI-11` — ativo não essencial gerador de renda líquida | `ESSENCIALIDADE=NAO_ESSENCIAL`, `VENDA=SIM`, `VALOR_LIQUIDO_DISPONIVEL=30.000`, `FLUXO=+700` | `MOBILIZACAO_POSSIVEL` |
| `GAB-NFI-12` — valor líquido negativo | `VALOR_ESTIMADO_ATIVO=100.000`, `SALDO_PASSIVO_VINCULADO=105.000`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO=5.000` | `VALOR_LIQUIDO_REALIZAVEL_ATIVO=-10.000`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=0` |

### 14.17. Tabela mestra de variáveis

| Variável | Escopo | Tipo | Origem | Regra | Status | Observação |
| --- | --- | --- | --- | --- | --- | --- |
| `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL` | PIQ | moeda | motor | `Σ NECESSIDADE_IMEDIATA_DIVIDA` | CANONICA | Teto do ataque imediato |
| `NECESSIDADE_IMEDIATA_DIVIDA` | dívida | moeda | motor | Regra pós-gates | CANONICA | Uma ocorrência por dívida |
| `VALOR_ACAO_FINANCEIRA_IMEDIATA` | ação/dívida | moeda | motor | Valor concreto de ação executável | CANONICA | Zero se ação não monetária |
| `CLASSIFICACAO_ATIVO` | ativo | enum | motor | Algoritmo deste documento | CANONICA | Não perguntar ao usuário |
| `VALOR_LIQUIDO_REALIZAVEL_ATIVO` | ativo | moeda | motor | Valor estimado - passivo - custos | CANONICA | Pode ser negativo |
| `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` | ativo | moeda | motor | `MAX(0, valor líquido)` | CANONICA | Nunca negativo |
| `FLUXO_LIQUIDO_RECORRENTE_ATIVO` | ativo | moeda/mês | motor | Renda recorrente - custo recorrente | CANONICA | Não duplicar dívida |

### 14.18. Declaração final

Constitui definição canônica para: `NECESSIDADE_FINANCEIRA_IMEDIATA_ELEGIVEL`,
`NECESSIDADE_IMEDIATA_DIVIDA`, `VALOR_ACAO_FINANCEIRA_IMEDIATA`,
`CLASSIFICACAO_ATIVO`, `VALOR_LIQUIDO_REALIZAVEL_ATIVO`,
`VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`, `FLUXO_LIQUIDO_RECORRENTE_ATIVO`.
Fica estabelecido: necessidade financeira imediata é objetiva, derivada das
dívidas pós-gates; ações só entram monetariamente com desembolso imediato e
valor conhecido; mesma dívida nunca contada 2x (ação + dívida ordinária);
classificação de ativos é derivada pelo motor sem pergunta direta;
essencialidade/disposição/liquidez/custo/valor líquido/efeito recorrente
determinam classificação; `VALOR_LIQUIDO_REALIZAVEL_ATIVO` = valor estimado -
passivo - custos desmobilização; `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL` =
`MAX(0, VALOR_LIQUIDO_REALIZAVEL_ATIVO)`; dados desconhecidos não podem virar
zero silenciosamente; `MOBILIZACAO_POSSIVEL` só integra o potencial;
`MOBILIZACAO_RECOMENDAVEL` pode integrar os recomendados; nenhuma decisão fica
a critério do desenvolvedor. Versionamento: qualquer alteração futura exige
nova versão formal.

---

> **Nota de verificação (não normativa, do Spec Agent).** Esta transcrição foi
> verificada contra `collection/registros/bloco-04.yaml`. **Uma lacuna foi
> identificada e ainda não resolvida**: o documento define
> `FLUXO_LIQUIDO_RECORRENTE_ATIVO = RENDA_RECORRENTE_ATIVO - CUSTO_RECORRENTE_ATIVO`
> (§14.8) também para veículo, mas o questionário (`bloco-04.yaml`) só tem
> `CUSTO_RECORRENTE_VEICULO` (linha 624) — não existe variável de renda para
> veículo, diferente de imóvel, que tem `RENDA_IMOVEL` (linha 436), e de outro
> ativo, que tem `RENDA_OUTRO_ATIVO` (linha 885). Pergunta enviada ao
> especialista em 2026-09-09, ainda sem resposta. Registrada como `OQ-38` na
> seção 10.
