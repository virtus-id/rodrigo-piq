# Decisões do especialista — 30/09/2026

Fonte: formulário de decisões do PIQ, respondido pelo especialista (Rodrigo),
com contribuições do revisor (Marcelo). Respostas brutas, incluindo o campo
de observação de cada pergunta, em [`respostas/`](respostas/) (`q<decisão>_<n>.json`).
Onde Rodrigo e Marcelo divergiram, vale a resposta do Rodrigo.

Confirmações posteriores, pelo responsável do produto em nome do
especialista (30/09/2026): **DE-02** e **DE-06** abaixo.

Cada decisão tem um ID `DE-NN` para rastreio em spec, plano e tarefas.

---

## DE-01 — Fotografia do mês (B3.C00) · `q1_1`, `q1_2`

- A tela de confirmação mostra **Renda total**, **Despesas totais** e
  **Sobra do mês** (= Renda total − Despesas totais, calculada
  automaticamente). As decomposições (categorias, não mensais, parcelas de
  dívidas) ficam acessíveis para consulta/edição, sem precisar aparecer na
  tela de confirmação.
- Totais consolidam tudo; decomposições **nunca** são somadas de novo
  (sem dupla contagem).
- Parcelas de dívidas continuam **cadastradas só no Inventário de Dívidas**
  (regra atual do Bloco 3). Como a B3.C00 ocorre antes do inventário, a
  sobra exibida ali é a do orçamento antes das dívidas, rotulada assim.
- "Ainda não consigo avaliar": sem ação especial; o fluxo segue.

## DE-02 — Recursos extraordinários (B3.05A–D) · `q2_1`–`q2_3` · **confirmado**

- Usados como **aceleradores** da quitação, nunca como condição para o
  plano mensal fechar.
- Grau de certeza informado pelo aluno (B3.05D): **Confirmado**, Provável,
  Possível. O **tipo** sozinho não decide; valem prazo e certeza.
- **Ataque de hoje** (§13.3, `EXTRAORDINARIOS_RECOMENDADOS`): só o que já
  está disponível no momento — regra atual mantida.
- **Projeção**: recursos **Confirmados** com valor estimável e recebimento
  dentro do horizonte do plano entram na projeção no mês previsto.
  Prováveis e Possíveis aparecem só como **cenário adicional** e só viram
  ataque quando efetivamente recebidos.
- Férias: considerar extraordinário **apenas o acréscimo** (1/3), não a
  remuneração normal, que já é renda mensal.
- Antes de destinar um extraordinário às dívidas, preservar necessidades
  essenciais, despesas sazonais já conhecidas, obrigações prioritárias e a
  proteção mínima (parâmetros de reserva já existentes no motor). Sempre
  valor líquido; sem dupla contagem com renda já no orçamento.
- O aluno pode cadastrar **vários** recursos, cada um com tipo, valor,
  janela e certeza; nunca somados como se tivessem a mesma certeza.

## DE-03 — Valor mensal × total · `q3_1`–`q3_3`

**Seguro embutido (B5.D05A):** valor total = custo total do seguro, nunca
despesa mensal. Distinguir três situações: (1) prêmio único financiado —
já compõe saldo/parcela, **não somar de novo**; (2) cobrado mensalmente à
parte — despesa mensal enquanto existir; (3) cancelado com restituição —
cessa a cobrança; restituição só quando confirmada (vira extraordinário).
Equivalente mensal só para análise, com período de cobertura, rotulado
como rateio. Orientar o aluno sobre apólice e cancelamento.

**Desconto do credor (B7.13A):** base = **valor atual de quitação antes do
desconto** (não "saldo devedor"). R$ → líquido = bruto − desconto;
% → líquido = bruto × (1 − %). Guardar separado: bruto, tipo (R$/%), valor
informado, valor final, validade. Valor final informado pelo credor
prevalece; desconto calculado só confere. R$ e % juntos: checar
compatibilidade e sinalizar divergência, nunca somar. Travas: % entre 0 e
100; desconto em R$ ≤ bruto.

**Custo mensal × total (B8.12A):** mensal = despesa recorrente enquanto
durar; total = custo único da operação, nunca somado a cada mês. Guardar
tipo, valor, período e meses restantes. Custo já embutido na parcela/saldo
não soma de novo. Mensalização só com prazo informado — sem prazo, não
inventar.

## DE-04 — Fichas obrigatórias · `q4_1`, `q4_2`

- O aluno **pode continuar preenchendo**, mas **não pode concluir o
  diagnóstico nem gerar o plano** com inventário incompleto.
- Dívidas: fichas cadastradas precisam igualar as declaradas (B5.00).
  Mensagem exata: "Você declarou 7 dívidas e cadastrou 5. Faltam 2 fichas."
  Alerta permanente de inventário incompleto.
- Renda extra, vínculo consignável, despesa não mensal: se respondeu Sim,
  precisa de ao menos um item antes do cálculo final; ou mudar a resposta
  para Não. Mensagem específica por caso.

## DE-05 — Vínculos e margem consignável · `q5_1`, `q5_2`

- O servidor pode ter **mais de um vínculo** (acumulação lícita, entes
  diferentes, mais de uma fonte). *Diverge do dicionário da spec
  ("única") — decisão do especialista prevalece.*
- Cada vínculo: órgão/ente pagador, tipo, renda líquida, existência de
  consignação, margem total, utilizada e disponível.
- **Margem pertence ao vínculo**; cada consignado aponta para o vínculo em
  que é descontado. **Nunca somar margens** de vínculos diferentes.

## DE-06 — Fonte de comprovação do dado · `q6_1` · **confirmado**

- Renomear o conceito para **"Fonte de comprovação"**. Três níveis:
  1. **Comprovado por documento/registro** — contrato, documento,
     aplicativo/internet banking, mensagem/e-mail, contracheque.
  2. **Informado pelo aluno, sem comprovação** — memória, "Não tenho
     registro", "Outra" sem documento associado.
  3. **Pendente de confirmação** — informação fornecida **verbalmente**
     (ex.: informada em atendimento), sem documento/registro.
- Regra geral: **não bloqueia** o plano; reduz o grau de confiança e fica
  sinalizado para validação posterior.
- Exceção: dado **indispensável** cuja incerteza impede resultado
  confiável → a pendência é apontada **antes de homologar** o resultado
  final (conferência da equipe).
- Confirmado em 30/09: taxa de juros informada como **estimada** não
  bloqueia a liberação — só reduz a confiança; **periodicidade da taxa**
  (B5.D01B) respondida "não sei" é pendência de dado indispensável e
  bloqueia a liberação pelo revisor até ser confirmada (sem ela a taxa não
  pode ser interpretada). Não bloqueia o cálculo. (`T-287`)

## DE-07 — Proposta do credor (B7.05, B7.08, B7.09) · `q7_1`

- Fluxo: existe proposta? Não → saltar todo o bloco. Sim → à vista,
  parcelada ou ambas. Parcelada → nº de parcelas, valor da parcela e
  demais dados. À vista → só dados da quitação à vista.
- **Validade** da proposta: pode ser perguntada em qualquer tipo.
  **Prazo do parcelamento**: só na parcelada.
- Campos não aplicáveis não aparecem nem contam como ausentes.

## DE-08 — Referência de validação · `q8_1`, `q8_2`

- Nenhum resultado pré-fixado: o motor apura caso a caso. Referência de
  aprovação: gabaritos da especificação (`GAB-A`, `GAB-B`, `GAB-C` e
  invariantes). Se faltar dado indispensável, o resultado não pode ser
  homologado.
- Todo teste de homologação registra: ordem final de ataque, mês de
  quitação de cada dívida, valor mensal destinado, custo total de juros e
  uso da reserva.
