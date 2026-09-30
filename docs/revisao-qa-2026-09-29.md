# Revisão técnica — achados do QA de 29/09/2026

- **Origem:** "Relatório consolidado dos testes do PIQ V1" (QA com apoio de LLM + teste humano), ambiente `piq.multiplicaservidor.com.br`.
- **Base analisada:** `main` @ `83b69b7`.
- **Como foi analisado:** leitura de código + reprodução local com fakes/`TestClient` (sem banco). **Nenhum dado de produção foi lido por código** e **nenhum arquivo foi alterado**.
- **Legenda de evidência:** 🔁 reproduzido localmente · 🔍 análise estática (confirmada por leitura/grep).

> Os números de linha referem-se a `83b69b7`.

---

## Resumo

| ID | Causa raiz | Sintomas do QA | Prioridade | Evidência |
|----|-----------|----------------|-----------|-----------|
| C1 | Opções sem `valor_interno` (141 perguntas) → front envia `''` | A02, rádios "bloqueados", condicionais não abrem, montagem quebra | **P1** | 🔁 |
| C2 | Front nunca dispara `POST /caso/{id}/calculo`; erros do servidor são descartados | A01 | **P1** | 🔍 |
| C3 | Fichas de despesa (`ITEM_DESPESA`) nunca são criadas → despesa = R$ 0 silenciosa | A04 | **P1** (financeiro) | 🔍 |
| C4 | Condições avaliadas só no nível do caso, nunca do item da ficha | A05 (b) | P2 | 🔁 |
| C5 | Completude de ficha só olha OBR; `B5.00` não exige fichas | A05 (a) | P2 | 🔁 |
| C6 | Percurso registro→item intercala as dívidas | "dívidas misturadas" | P2 | 🔁 |
| C7 | `GET /respostas` estoura com resposta cuja condição deixou de valer | A03 | **P1/P2** | 🔁 |
| P1–P7 | Pontuais (hash de ficha, B5.I02, escala, mensagens, contadores, "Não sei") | A05 (c)(d), A06 | P2/P3 | 🔁/🔍 |

Decisões de produto/spec necessárias antes de algumas correções: ver **[Decisões pendentes](#decisões-pendentes)**.

---

## C1 — Opções sem `valor_interno` (P1)

**Sintomas:** checkbox marca/desmarca todas as opções do grupo (moradia, alimentação, transporte, saúde, lazer, local da reserva…); rádios Sim/Não "não aceitam clique" (B3.D11, B3.04, B4.I01, B4.V01, B5.A03, extraordinário…).

**Causa:**
- 141 registros em `collection/registros/*.yaml` têm opções com `valor_interno: null` (ex.: `B3.D01`–`B3.D10`, `B3.D11`, `B5.C01`, `B5.D05`, `B5.A03`).
- `frontend/src/componentes/CampoPergunta.tsx`:
  - múltipla: `const valorInterno = opcao.valor_interno ?? ''` → todas as opções compartilham `''`; `marcados.includes('')` marca todas.
  - única: `onClick={() => onValor(opcao.valor_interno ?? '')}` e `marcado = texto === opcao.valor_interno` → `'' !== null`, nunca aparece marcado.
- O backend espera literais: `app/montagem/estado.py:550,552,655,1111,1223,1415,1417,1454` comparam com `"SIM"`/`"NAO"`. Nenhum código converte rótulo → valor.

**Impacto a jusante (🔁 com a fixture `caso_completo` em `montar_divida`):**
```
{'QUITACAO_CONSULTADA': ''} -> ValueError: valor inesperado ''   (estado.py:556)
{'TIPO_DIVIDA': ''}         -> ValueError: '' is not a valid TIPO_DIVIDA (estado.py:611)
```
Também por leitura: `JANELA_NOVA_DIVIDA=''` → `ValueError` (estado.py:961); sinais comportamentais com `''` → `ErroSinalComportamentalAusente` (~:800). `B5.C01` gravado como `''` mantém `B5.C02–C04` fechadas. 27 das 141 perguntas alimentam a montagem.

**Correção sugerida:**
1. Preencher `valor_interno` no registro (edição de dado, não de código): `SIM`/`NAO`/`NAO_SEI` nas Sim/Não, identificadores estáveis nos checklists (`ALUGUEL`, `CONDOMINIO`, …). → **Decisão D1**.
2. Teste estático: nenhum registro de seleção pode ter `valor_interno` nulo nem repetido.
3. Front: usar índice/rótulo como `key`, nunca `valor_interno ?? ''`.
4. Dados já gravados com `''` nas contas de teste ficam inválidos → reteste com contas novas.

---

## C2 — "Montar o seu plano" não dispara o cálculo (P1)

**Sintoma:** aparece "Estamos montando o seu plano" por um instante e volta ao Início com o mesmo botão; caso segue em `COLETA_INICIAL`.

**Causa:**
- `frontend/src/services/api.ts` não tem nenhuma função que faça `POST /caso/{id}/calculo` (confirmado por grep e `git log -S`). Só existe `obterProgressoDoCalculo` (GET, `api.ts:387`).
- `rotas_inicio.py:233-241` devolve `destino="calculando"` → `TelaInicio.tsx:85/134` navega para `TelaCalculando`.
- `TelaCalculando.tsx:45-50` só faz polling; como o caso não está calculando, recebe `calculando:false` e chama `onTerminou()` → `voltarAoInicio` (`App.tsx:560`).

**Erros que ficariam escondidos mesmo com o POST:**
- `api.ts:52-62` (`pedir`) lê `corpo.erro`; `rotas_calculo.py` devolve `mensagem`/`pendencias` → usuário veria só "HTTP 4xx".
- `_preparar_calculo` captura apenas `ErroRespostaAusente`/`ErroValorInternoDesconhecido` (`rotas_calculo.py:521-527`). Escapam como 500: `ValueError` (ver C1), `ErroSinalComportamentalAusente`, `ErroCampoAgregadoDesconhecido`, `ErroDinheiroDisponivelIndeterminado`, `ErroConversaoInvalida`, `AssertionError` — inclusive em `_ParametrosExternosDerivadosDoBloco2.obter` (`:294`).
- 503 se `PARAMETROS_VERSION_VIGENTE` ausente (`:533-540`) — **conferir no `.env` do VPS**.

**Correção sugerida:**
1. `dispararCalculo(casoId)` em `api.ts`; `TelaCalculando` chama antes do polling (409 com caso já `CALCULANDO` = sucesso).
2. `pedir` passa a ler `mensagem` e expor `pendencias`; tela mostra pendências concretas com link para cada pergunta.
3. Rota converte exceções de montagem (base comum) em 422 com identificador de suporte, em vez de 500.

---

## C3 — Despesas por categoria nunca viram valor (P1 — erro financeiro)

**Sintoma (A04):** o fluxo pede categorias e segue sem campos de valor; a "fotografia" não mostra números; "Não, algum valor parece errado" não leva a lugar nenhum.

**Causa:**
- A spec (`specs/piq-app-spec.md:1314,1329`) diz: "cada item marcado → abre B3.DF01–DF04". Isso está só em `salto_consequencia` (texto livre) — **nenhum código interpreta**.
- Nada cria itens `ITEM_DESPESA` a partir de `ITENS_DESPESA_*`; as DF só existem para itens já cadastrados (`app/casos/progresso.py:409`).
- `frontend/src/App.tsx:481-485`: `TelaFichas` fixo em `escopo="DIVIDA_ID"`.
- **Consequência:** `_despesas_operacionais_atuais` (`app/montagem/estado.py:1102-1108`) soma zero fichas → **`DESPESAS_OPERACIONAIS_ATUAIS = 0` sem aviso** → capacidade de ataque inflada. Um plano gerado hoje seria financeiramente errado.
- `B3.C00` ("fotografia", `bloco-03.yaml:812-833`): sem `interpolacoes`, a spec não define os números exibidos; `FALTA_DESPESA → B3.D11` / `VALOR_ERRADO → editar fichas` (spec `:1638`) não implementados; `CONFIRMACAO_MAPEAMENTO_DESPESAS` não tem consumidor.
- A interpolação `[despesa]` usa `ID_DO_ITEM` (`bloco-03.yaml:645`) → mostraria "DESP001" em vez de "Aluguel".

**Correção sugerida:** depende de **D2/D3**. Enquanto isso, recomendo um **gate**: bloquear o cálculo (pendência explícita) se houver categoria marcada sem ficha de valor — nunca calcular com despesa zero implícita.

---

## C4 — Condições de exibição ignoram o item da ficha (P2)

**Sintoma (A05 b):** após "não há proposta do credor", a ficha ainda pergunta nº de parcelas e prazo da proposta.

**Causa:**
- `collection/condicoes.py:137` → `respostas.valor(variavel)` busca a chave `(var, "")`; respostas de ficha são gravadas com `item_id` (`D001`…). `avaliar()` (`:127`) não recebe item.
- Resultado: toda `IGUAL` sobre variável de ficha é sempre falsa; toda `NAO(...)` é sempre verdadeira.
- 🔁 Com `POSSUI_PARCELA_DEFINIDA=SIM` e `TIPO_DIVIDA=CARTAO_ROTATIVO` em D001: `B5.C02=False`, `B5.C07=False`, `B5.G03=False`, `B5.C05 (NAO)=True`.
- As perguntas vistas são `B7.08`/`B7.09` (`bloco-07.yaml` ~96-118): condição `NAO(PROPOSTA_PARCELA == A_VISTA)` sempre verdadeira. Além disso, `proxima_pergunta_nao_respondida` inclui o Bloco 7 (coleta dirigida pós-plano) no percurso inicial.

**Correção sugerida:** `avaliar(condicao, respostas, item_id=None)` resolvendo por item quando a pergunta é repetível; condicionar B7.08/B7.09 à B7.05; excluir blocos 7, 8 e 11 da retomada inicial.

---

## C5 — Ficha vazia aparece "Completa" (P2)

**Sintomas (A05 a):** ficha recém-criada "Completa"; Início diz "tudo respondido" com dívidas declaradas e sem fichas; "37 campos" em cada ficha.

**Causa:**
- `completa` vem de `pendencias_obrigatorias` (`rotas_fichas.py:115-123`), que só conta OBR (`app/casos/progresso.py:330-341`). As 55 perguntas de ficha do Bloco 5 são `[REP]`/`[COND, REP]` → nunca pendentes. 🔁 duas fichas vazias → `completa=True`; 0 pendências sem ficha nenhuma.
- Nada liga `B5.00` (nº de dívidas declarado) à existência de fichas; sem itens, `progresso.py:409` pula a seção inteira e o fluxo vai de `B5.00A` direto a `B5.FIM02`.
- "37" é o tamanho da ficha: `perguntas_da_ficha` (`collection/repeticao.py:78`) filtra só por escopo e inclui `B7.08`/`B7.09` além das 35 do Bloco 5 (o contador de posição diz "de 35").

**Correção sugerida:** completude de ficha pelos mesmos predicados da retomada (REP exigíveis); `B5.00 > 0` exige fichas criadas; `perguntas_da_ficha` restrita ao bloco de coleta inicial.

---

## C6 — Perguntas das dívidas intercaladas (P2)

**Sintoma:** Dívida 1 · pergunta 1 → Dívida 2 · pergunta 1 → Dívida 1 · pergunta 2…

**Causa:** `_percorrer_ocorrencias` (`app/casos/progresso.py:404-411`) itera registro → item. 🔁 ordem obtida: `B5.A01/D001, B5.A01/D002, B5.A02/D001, B5.A02/D002…`. Usado por `POST /resposta` (T-193) e `GET /pergunta` via `_primeira_exibivel`.

**Correção sugerida:** para escopos com ficha, iterar item → registro (D001 completa, depois D002), tanto na retomada quanto em `contar_coleta`.

---

## C7 — "Minhas respostas" não carrega (P1/P2)

**Sintoma (A03):** "Não foi possível carregar as suas respostas", persistente após uma correção.

**Causa:** `app/http/rotas_respostas.py:94` chama `montar_contexto_pergunta` para cada resposta gravada; essa função lança `ErroPerguntaNaoExibivel` quando a `condicao_exibicao` deixou de valer (`app/http/renderizacao.py:109-112`). Não há captura → 500 em toda carga.

🔁 `B1.02=SIM` → responde `B1.03` → corrige `B1.02=NAO` → `GET /respostas`: 200 antes, `ErroPerguntaNaoExibivel: B1.03` depois (`rotas_respostas.py:159` → `renderizacao.py:112`).

Efeito colateral: o botão "‹ Pergunta anterior" (`TelaPergunta`) depende da mesma rota e engole a falha com `.catch` → some.

**Correção sugerida:** na revisão, pular (ou marcar como "não se aplica mais") respostas cuja condição fechou — sem checar exibibilidade para montar a linha. Decidir se a resposta órfã deve ser mantida ou desconsiderada no cálculo.

---

## Pontuais

| ID | Achado | Causa | Correção sugerida | Evid. |
|----|--------|-------|-------------------|-------|
| P1 | Abrir 1ª ficha pela lista → "Não foi possível carregar a pergunta" (A05 d) | `App.tsx:489` navega sem `idPergunta`; `rotaParaHash` (`navegacao.ts:121`, `filter(Boolean)`) gera `#pergunta/D001`; `hashParaRota` (`:167`) lê `D001` como pergunta → `GET /pergunta/D001` 404 | Rota "próxima pergunta aberta do item X" + hash com posições fixas | 🔁 |
| P2 | Escolha única mostra duas opções marcadas / opções "reaparecem" (A05 c) | `B5.I02` (`bloco-05.yaml:1164-1169`) repete `DOCUMENTO` ×3 e `USUARIO` ×3; `CampoPergunta.tsx:68` marca todas iguais; `:71` usa o valor como `key` → React reaproveita nós entre perguntas | Valores distintos por opção (derivar `ORIGEM_DADO` fora do `valor_interno`); `key` por índice/rótulo | 🔍 |
| P3 | Nota 0–10 salva não aparece pré-selecionada (A06) | Servidor grava/serializa `int` (`rotas_coleta.py:371-386`, `serializacao.py:64-65`); front faz `as string` (`TelaPergunta.tsx:224-226`) e compara `texto === n` com `"7"` (`CampoPergunta.tsx:125`) | `String(valor_atual)` no front (ou string no servidor p/ ESCALA/NUMERO) | 🔍 |
| P4 | "RENDA_PRINCIPAL: entrada vazia" (A06) | `rotas_coleta.py:489`: `f"{registro.VARIAVEL_GRAVADA}: {erro.motivo}"` | Mensagem para humano, sem nome de variável; impedir envio vazio de OBR no front | 🔍 |
| P5 | Contadores 41 × 34 × "Bloco 3 · 28" (A06) | Início usa `contar_coleta().faltam` (todas abertas — `rotas_inicio.py:333`, `progresso.py:641-674`); fluxo usa `len(pendencias_obrigatorias)` global (`rotas_pergunta.py:190,206`, `rotas_coleta.py:577`) rotulado como do bloco (`TelaPergunta.tsx:162`) | Uma fonte só, ou rótulo honesto ("N obrigatórias restantes") | 🔍 |
| P6 | "Não sei" duplicado e com layout diferente (UI) | 64 perguntas têm `admite_nao_sei` no registro **e** uma opção "Não sei…"; front ignora `opcao.admite_nao_sei`; checkbox fora do `fieldset` (`CampoPergunta.tsx:188-198`) | Não renderizar o checkbox quando uma opção já cobre; estilizar como `.opt` | 🔍 |
| P7 | Máscara de moeda trata dígitos como centavos (A06) | Intencional (`mascaras.ts`, "os dois últimos dígitos são os centavos"); RF-47 não fixa o modo | Decisão de UX; se mudar, manter `tests/app_aluno/test_mascaras.py` | 🔍 |

---

## Fora do escopo de bug (spec)

| Pedido do QA | Situação |
|--------------|----------|
| "Iniciar novo plano" / reiniciar coleta | **Contra a spec**: RF-01 (`app-aluno.spec.md:112`) e RF-69 (`:282`) dizem "sem reiniciar"; plano novo só por recálculo (RF-28). Exige mudança de spec. |
| Caixa de texto em "Outro" | Lacuna: "Outro → texto curto OPT" só no `salto_consequencia` (20 perguntas); não há variável nem registro para o texto. |
| Resumo numérico na "fotografia" (B3.C00) | Lacuna: spec não define quais números nem onde. |
| Trilha lateral por blocos | Feature nova. `TrilhaDaJornada.tsx` existe, mas mostra as 5 etapas da jornada (RF-64), não blocos, e só no Início. |

---

## Decisões pendentes

| ID | Pergunta | Bloqueia |
|----|---------|----------|
| D1 | Valores internos das opções hoje nulas: `SIM`/`NAO`/`NAO_SEI` e identificadores dos itens de checklist? | C1 |
| D2 | Como nasce a ficha de despesa por item marcado e como ela se apresenta ("Qual o valor mensal de Aluguel?")? | C3 |
| D3 | O que a "fotografia" (B3.C00) mostra e o que "valor errado"/"falta despesa" fazem? | C3 |
| D4 | Reinício, texto em "Outro" e trilha lateral: agora ou backlog? | — |
| D5 | Resposta que ficou órfã após correção (C7): mantém visível? entra no cálculo? | C7 |

---

## Ordem sugerida

1. **Fase 1 — destravar o fluxo:** C1 (após D1), C2, C7, C4, C5, C6, P1, P2.
2. **Fase 2 — orçamento:** gate de despesa zero imediatamente; C3 completo após D2/D3.
3. **Fase 3 — acabamento:** P3–P6.
4. **Reteste:** contas novas (as atuais têm `''` gravado), caso T02 do QA como gabarito, variação de gastos 3.500 → 3.800, depois caso com consignado.

Cada item deve virar tarefa `T-194+` em `tasks/app-aluno.tasks.md`, com teste que reproduz o bug antes da correção.

## Checklist de revisão

- [ ] Conferir se concorda com a causa raiz de cada item (principalmente C2 e C3)
- [ ] Responder D1–D5
- [ ] Confirmar `PARAMETROS_VERSION_VIGENTE` no `.env` de produção
- [ ] Validar a priorização
- [ ] Apontar algo que a análise não viu
