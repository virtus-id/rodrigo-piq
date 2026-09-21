# Checklist manual de acessibilidade — fluxo de coleta, tela do plano e fila de revisão

| Campo   | Valor                                                                    |
| ------- | ------------------------------------------------------------------------- |
| Slug    | `app-aluno`                                                                |
| Tarefa  | `T-48` — Verificar acessibilidade automatizada do fluxo de coleta; estendido por `T-97` — Verificar acessibilidade automatizada da apresentação do plano |
| Rastreia| `RF-07`, `RF-09` (T-48); `RF-21`, `RF-22` (T-97)                           |
| Origem  | `plans/app-aluno.plan.md` §9, "Fora de teste automatizado, e por quê": *"Conformidade WCAG 2.1 AA completa — automação (`axe`) cobre contraste, rótulo e ordem de foco, e entra no E2E; navegação por teclado com leitor de tela real exige verificação manual, registrada como checklist."* |

## Por que este checklist existe, e o que ele NÃO substitui

**Atualizado em `T-145`: a interface é React.** A automação de
acessibilidade hoje está em dois lugares:

- `tests/app_aluno/e2e/test_acessibilidade_coleta.py` recalcula a razão de
  contraste pela própria fórmula da WCAG 2.1 sobre os tokens de cor de
  `frontend/tailwind.config.js` — que são as cores que o aluno de fato vê.
- `frontend/tests/e2e/` roda em **Chromium de verdade** (Playwright), sobre
  o DOM renderizado: navegação só por teclado, recusa do servidor chegando
  ao aluno com `role="alert"`, e ausência de rolagem horizontal a 360 px.

Nenhum dos dois **é `axe-core`**. Eles cobrem os padrões mais comuns de
violação nessas categorias — não o motor de acessibilidade completo de um
navegador (ARIA inválido, papel semântico computado pela árvore de
acessibilidade, contraste após cascata CSS completa, foco visível por
`:focus`).

Os itens abaixo são o que **nenhuma automação deste projeto cobre hoje** —
nem o teste estático, nem (se um dia existir) uma execução real de
`axe-core`, porque dependem de percepção humana ou de comportamento de
software assistivo real.

**Extensão de `T-97`, revista em `T-145`.**
`tests/app_aluno/e2e/test_acessibilidade_plano.py` aplica a MESMA decisão de
fronteira ao HTML que continua sendo gerado no servidor: o do **PDF**
(`report/templates/plano/`), sobre um `SnapshotOrdem` de verdade, nunca
fabricado à mão. As telas do plano, da fila e do operador viraram React, e
sua acessibilidade se verifica em `frontend/tests/e2e/plano.spec.ts` e
`coleta.spec.ts`, em navegador real.

As seções abaixo (leitor de tela real, zoom/360 px, contraste em percepção
visual real) valem para **qualquer tela** desta feature, sem duplicação por
tela.

## Como executar

Repita esta checklist a cada mudança relevante em `frontend/src/`
(componentes e telas), em `frontend/tailwind.config.js` (tokens de cor e
alvos de toque), em `frontend/src/index.css`, ou em
`report/templates/plano/*.html` (o PDF) — e ao menos uma vez antes de abrir
o piloto (`plans/app-aluno.plan.md` §10, "1–3 alunos em série").

Dispositivos/leitores mínimos recomendados (um por sistema operacional já
disponível para quem executa o checklist — não é preciso ter os três):

- **NVDA** (Windows, gratuito) + Chrome ou Firefox
- **VoiceOver** (macOS/iOS, nativo) + Safari
- **TalkBack** (Android, nativo) + Chrome

## Itens do checklist

### 1. Navegação por teclado, ponta a ponta

- [ ] É possível preencher e submeter uma pergunta de cada `TipoResposta`
      (os nove tipos — `SELECAO_UNICA`, `SELECAO_MULTIPLA`, `NUMERO`,
      `MOEDA`, `TAXA`, `DATA`, `TEXTO_CURTO`, `SIM_NAO_TALVEZ`,
      `ESCALA_0_10`) usando **somente o teclado** (Tab, Shift+Tab, Enter,
      Espaço, setas em grupos de rádio).
- [ ] A ordem de tabulação segue a ordem visual da página — nenhum campo
      "salta" para um lugar inesperado.
- [ ] O indicador visual de foco (contorno/realce) é visível em todo
      elemento interativo, inclusive dentro de um `<details>` aberto.
- [ ] Expandir/recolher uma ficha (`<details>`/`<summary>` de
      `ficha_repetivel.html`) funciona com Enter e Espaço.
- [ ] O botão "Adicionar ficha" e o botão "Salvar resposta" são alcançáveis
      e ativáveis sem mouse.
- [ ] Nenhuma armadilha de foco: é sempre possível sair de qualquer campo
      ou grupo de campos só com o teclado.

### 1.1 Navegação por teclado — tela do plano e tela da fila (`T-97`)

Diferente da coleta, o plano e a fila são telas
de LEITURA, sem campo de formulário nem `<details>` — o teste estático
(`test_acessibilidade_plano.py`) já confirma essa ausência e a ausência de
`tabindex` fora de `0`. O que só verificação manual cobre:

- [ ] A partir do momento em que a tela do plano carrega, Tab percorre os
      elementos na MESMA ordem em que aparecem visualmente: título (`<h1>`),
      corpo, cada posição da ordem (`<h2>` de `posicao.html`) na sequência
      publicada, bloco de pendências (quando presente) e o carimbo de versão
      no rodapé — nenhum elemento fica inacessível por Tab nem "some" da
      ordem de tabulação.
- [ ] Quando existe um link (ex.: para o PDF do plano, se a interface do
      piloto expuser um), ele é alcançável e ativável só com Tab e Enter, com
      indicador visual de foco visível.
- [ ] Na tela da fila de revisão, Tab percorre as linhas da tabela em ordem,
      e a navegação por tabela de um leitor de tela (comando dedicado de
      "próxima célula"/"próxima linha") lê `<th scope="col">` associado a
      cada `<td>` corretamente (ex.: ao entrar na célula de `MOTIVO_
      RECALCULO` de uma linha, o leitor anuncia o rótulo da coluna).
- [ ] Nenhuma armadilha de foco em nenhuma das duas telas: é sempre possível
      sair de qualquer elemento focável só com o teclado.

### 2. Leitor de tela real (NVDA/VoiceOver/TalkBack)

- [ ] O enunciado de cada pergunta é anunciado antes do tipo de campo (ex.:
      "Qual o saldo devedor atual?, caixa de texto").
- [ ] Em `SELECAO_UNICA`/`SIM_NAO_TALVEZ`/`SELECAO_MULTIPLA`, o leitor
      anuncia o enunciado (`<legend>`) uma vez ao entrar no grupo, e depois
      só o rótulo de cada opção — nunca o enunciado repetido a cada opção.
- [ ] O checkbox "Não sei" é anunciado com um rótulo claro, associado ao
      campo a que se refere.
- [ ] Quando a resposta é confirmada (`confirmacao_resposta.html`), o
      leitor anuncia "Resposta registrada" sem precisar que o foco se mova
      até lá (`role="status"`/`aria-live="polite"` já testados
      estaticamente em `test_acessibilidade_coleta.py`; este item confirma
      o comportamento real do software assistivo, que pode divergir entre
      leitores).
- [ ] Quando a validação cruzada falha (`erro_resposta.html`,
      `role="alert"`), o leitor **interrompe** a leitura corrente para
      anunciar o erro (comportamento esperado de `role="alert"`, mas cuja
      urgência de interrupção varia entre NVDA/VoiceOver/TalkBack) e, ao
      navegar de volta ao campo (`aria-describedby`), o leitor lê a
      mensagem de erro junto da pergunta.
- [ ] O aviso de materialidade (`aviso_materialidade.html`) é anunciado
      junto do campo que o originou, sem precisar navegar até ele
      separadamente.
- [ ] Ao expandir uma ficha da lista repetível, o leitor anuncia que o
      estado mudou (expandido/recolhido) e o rótulo "Completa"/"Pendência"
      correspondente.
- [ ] A navegação por "landmarks"/cabeçalhos (recurso de navegação rápida
      de leitores de tela) chega a cada bloco de fichas (`<h2>` de
      `ficha_repetivel.html`) de forma previsível.

### 3. Zoom e proporções reais de tela (360 px)

- [ ] Em um navegador real, com a janela redimensionada para 360 px de
      largura (ou em um celular físico de fato estreito), nenhuma tela de
      coleta, do plano ou da fila produz rolagem horizontal — os testes
      estáticos (`tests/app_aluno/estatica/test_css_360px.py`,
      `tests/app_aluno/test_ficha_repetivel.py`,
      `tests/app_aluno/e2e/test_acessibilidade_plano.py`) só verificam
      AUSÊNCIA de padrões problemáticos no CSS/HTML, não o resultado visual
      real após zoom do navegador, fontes do sistema ou orientação de tela —
      em particular, a tabela da fila de revisão nunca foi confirmada sem
      rolagem em um navegador real (o teste estático só confirma ausência de
      largura fixa declarada).
- [ ] Com zoom do navegador em 200%, todo texto e controle continuam
      legíveis e utilizáveis, sem sobreposição.

### 4. Contraste em contexto visual real

- [ ] Os indicadores "Completa"/"Pendência" e o aviso de materialidade são
      distinguíveis também para quem tem daltonismo (não dependem só da
      cor — os testes estáticos já confirmam a razão numérica de
      contraste; este item confirma a percepção visual real, inclusive sob
      simulação de daltonismo, se disponível na ferramenta do avaliador).

## Registro de execução

| Data       | Executor       | Dispositivo/leitor | Resultado | Observações |
| ---------- | -------------- | ------------------- | --------- | ----------- |
| _pendente_ | _pendente_     | _pendente_           | _pendente_ | Piloto ainda não aberto — primeira execução prevista antes de `plans/app-aluno.plan.md` §10 liberar o primeiro caso real. |

## Trabalho de infraestrutura futura (fora do escopo de `T-48`/`T-97`)

- **Atualização de 2026-09-14 (T-129):** Playwright e Chromium passaram a
  existir neste ambiente (extra `browser` do `pyproject.toml`), e
  `tests/app_aluno/e2e/test_navegador_mascaras.py` já roda em navegador real
  — mas cobrindo a **máscara de entrada**, não acessibilidade. O item abaixo
  continua aberto: ter o navegador é pré-requisito de `axe-core`, não é
  `axe-core`. O que destravou foi a possibilidade; o trabalho em si não foi
  feito e não deve ser dado como feito.
- Pipeline de CI com Chromium/Playwright instalado, rodando `axe-core` real
  sobre as páginas renderizadas — hoje inviável sem introduzir uma
  dependência nova fora do plano desta feature (`sdd.config.md`, "sem
  dependência nova que não esteja no plano").
- Automação de zoom/proporção de tela real via `pytest-playwright` (mesma
  dependência acima).
