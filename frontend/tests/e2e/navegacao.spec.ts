/**
 * O modelo novo de navegação, provado no navegador — `RF-57`, `RF-58`,
 * `RF-59` (T-152).
 *
 * **Por que estes sete testes existem.** A Rodada 5 trocou a barra de sete
 * abas por roteamento por hash e uma casca de tela. A migração dos 18 blocos
 * de `coleta.spec.ts` e `plano.spec.ts` prova que as garantias ANTIGAS
 * sobreviveram; ela não prova nada sobre o modelo novo. Sem este arquivo, o
 * roteador, o foco de navegação, o rodapé `sticky`, o filtro por papel e o
 * fallback de hash desconhecido ficariam sem prova em navegador real —
 * exatamente as cinco coisas que só um navegador de verdade sabe verificar.
 *
 * Toda navegação passa por `apoio/navegacao.ts`: nem aqui, no arquivo que
 * testa navegação, um seletor de navegação é escrito à mão.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

import {
  abrirTela,
  acaoPrincipal,
  entrarComoRevisor,
  inicioEmColeta,
  type InicioDeTeste,
  interceptarBase,
  interceptarRespostas,
  type ParteDeTeste,
  partesVazias,
  ROTULOS_DAS_PARTES,
  voltarDaTela,
} from './apoio/navegacao'
// O texto da entrada é redação revisada pelo especialista (`T-185`) — o
// teste aponta para a fonte, nunca para um literal que divergiria a cada
// revisão de copy. Mesma disciplina de `TelaLogin.test.tsx`.
import { TITULO } from '../../src/telas/textosDaEntrada'

const CASO = 'CASO-NAV-E2E'

const TITULO_BASE = 'PIQ Meu Plano'

/**
 * As cinco fases de `app/casos/fases.py::FASE_INICIO`, cada uma com o
 * destino que `rotas_inicio.py::_proxima_etapa` devolve para ela, e o rótulo
 * que `TelaInicio::TEXTO_DA_ETAPA` mapeia — `AC-81`.
 *
 * O `rotulo` é do CLIENTE de propósito: o servidor manda o destino, não o
 * texto (`AC-37`, `AC-88`). É por isso que este par vive aqui e não no
 * payload abaixo.
 */
const FASES: readonly {
  fase: InicioDeTeste['fase']
  estado: string
  destino: InicioDeTeste['proxima_etapa']['destino']
  mensagem: string
  rotulo: string
}[] = [
  {
    fase: 'coleta',
    estado: 'COLETA_INICIAL',
    destino: 'pergunta',
    mensagem: 'Sua coleta está em andamento.',
    rotulo: 'Continuar de onde você parou',
  },
  {
    fase: 'revisao',
    estado: 'AGUARDANDO_REVISAO',
    destino: 'aguardando',
    mensagem: 'Seu plano está em conferência.',
    rotulo: 'Aguardar a conferência',
  },
  {
    fase: 'reprovado',
    estado: 'REPROVADO',
    destino: 'progresso',
    mensagem: 'Seu plano está em nova análise.',
    rotulo: 'Ver as suas respostas',
  },
  {
    fase: 'plano',
    estado: 'PLANO_LIBERADO',
    destino: 'bloco10',
    mensagem: 'Seu plano está liberado.',
    rotulo: 'Decidir sobre o dinheiro que você tem disponível',
  },
  {
    fase: 'acompanhamento',
    estado: 'EM_ACOMPANHAMENTO',
    destino: 'acoes',
    mensagem: 'Seu plano está em acompanhamento.',
    rotulo: 'Ver o que fazer agora',
  },
]

/** `document.title` — o formato é `PIQ Meu Plano · <título da tela>`. */
function tituloDoDocumento(page: Page): Promise<string> {
  return page.evaluate(() => document.title)
}

/** O texto do elemento com o foco — `AC-84` exige que seja o `<h1>`. */
function focoAtual(page: Page): Promise<{ tag: string; texto: string }> {
  return page.evaluate(() => ({
    tag: document.activeElement?.tagName ?? '',
    texto: document.activeElement?.textContent?.trim() ?? '',
  }))
}

/**
 * `AC-81` — o Início oferece UMA próxima etapa, em cada uma das cinco fases.
 *
 * Um teste por fase, e não um laço dentro de um teste: assim o relatório diz
 * QUAL fase quebrou, que é a informação que falta quando um laço falha na
 * terceira volta.
 *
 * A asserção que carrega o requisito é a CONTAGEM: `RF-58` não promete "um
 * botão bom entre vários", promete **um**. O segundo botão que a tela admite
 * ("Ver meu progresso", "Ver meu plano") nunca é alternativa de fluxo — é
 * consulta ao que já existe —, então ele é contado à parte e o que se exige é
 * que não exista um segundo DESTINO.
 */
for (const caso of FASES) {
  test(`AC-81: a fase ${caso.fase} oferece exatamente uma próxima etapa`, async ({
    page,
  }) => {
    await interceptarBase(page, CASO, {
      inicio: {
        estado: caso.estado,
        fase: caso.fase,
        mensagem: caso.mensagem,
        proxima_etapa: {
          destino: caso.destino,
          ID_PERGUNTA: caso.destino === 'pergunta' ? 'B5.B03' : null,
          item_id: caso.destino === 'pergunta' ? 'D001' : null,
        },
        valor_em_destaque: caso.fase === 'plano' ? '3000.00' : null,
        plano_liberado: caso.fase !== 'coleta',
      },
    })

    await abrirTela(page, CASO, 'inicio')

    // A etapa que o servidor escolheu está na tela, com a redação do cliente.
    await expect(acaoPrincipal(page, caso.rotulo)).toBeVisible()

    // E é a ÚNICA que leva a algum lugar novo. Os rótulos de consulta são
    // nomeados um por um de propósito: um botão de fluxo novo aparecendo no
    // rodapé não passa por esta contagem sem alguém decidir incluí-lo.
    // "Ver e editar minhas respostas" entrou em T-160 e é consulta pelo mesmo
    // critério dos outros dois: não leva o caso a lugar nenhum novo, devolve
    // ao aluno o que ele já disse (`RF-68`). A escolha de fluxo segue uma só.
    // "Sair" entrou em T-188 pelo mesmo critério: não é um passo do CASO,
    // é uma ação de CONTA, presente em toda fase — nunca competindo com a
    // próxima etapa.
    const CONSULTAS = [
      'Ver meu progresso',
      'Ver meu plano',
      'Ver e editar minhas respostas',
      'Sair',
    ]
    const rotulosDoRodape = await page
      .locator('.acoes')
      .getByRole('button')
      .allInnerTexts()
    const etapas = rotulosDoRodape
      .map((texto) => texto.trim())
      .filter((texto) => !CONSULTAS.includes(texto))

    expect(etapas).toEqual([caso.rotulo])

    // `EC-25`: fora da coleta, a mensagem do ESTADO é o conteúdo — nunca uma
    // tela vazia, e nunca o erro técnico.
    if (caso.fase !== 'coleta') {
      await expect(page.getByText(caso.mensagem)).toBeVisible()
    }
  })
}

/**
 * `AC-86`, `EC-27` — o voltar do navegador.
 *
 * **A armadilha nº 1 da reescrita.** `history.pushState` NÃO dispara
 * `popstate`, então `navegacao.ts` avisa os hooks por um evento próprio
 * (`piq:navegou`). Um `useRota` que escutasse só um dos dois passaria em
 * metade dos casos — e qual metade depende de qual ele escutou. Este teste
 * exercita as DUAS direções: navegar por dentro do app, e voltar pelo
 * histórico.
 */
test('AC-86/EC-27: o voltar do navegador exibe a tela anterior', async ({ page }) => {
  await interceptarBase(page, CASO)

  const PERGUNTA_DA_RETOMADA = {
    pergunta: {
      CASO_ID: CASO,
      ID: 'B5.B03',
      bloco: 5,
      tipo: 'MOEDA',
      enunciado: 'Quanto falta pagar hoje?',
      opcoes: [],
      escopo_repeticao: 'DIVIDA_ID',
      item_id: 'D001',
      posicao: null,
      total_na_ficha: null,
      admite_nao_sei: true,
      valor_atual: null,
      respondida_como_nao_sei: false,
      valores_marcados: [],
      aviso: null,
    },
    avanco_permitido: false,
    total_pendencias: 3,
  }

  // **As DUAS rotas de pergunta.** `/inicio` nomeia onde o aluno parou
  // (`B5.B03`/`D001`), então "Continuar de onde você parou" vai para
  // `#pergunta/B5.B03/D001` e a tela pede a pergunta ESPECÍFICA. Até `T-160`
  // ela pedia a próxima e este intercept sozinho bastava — o defeito é que a
  // URL dizia uma coisa e a requisição fazia outra (`AC-102`). O glob de
  // Playwright não atravessa `/`, então o caminho com `ID` precisa do seu
  // próprio intercept; os dois devolvem a mesma pergunta porque, neste caso,
  // é a mesma.
  for (const padrao of [
    `**/caso/${CASO}/pergunta`,
    `**/caso/${CASO}/pergunta/B5.B03*`,
  ]) {
    await page.route(padrao, async (rota) => {
      await rota.fulfill({ json: PERGUNTA_DA_RETOMADA })
    })
  }

  await abrirTela(page, CASO, 'inicio')
  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()

  // Navegação POR DENTRO do app: é o caminho que depende de `piq:navegou`,
  // porque `pushState` sozinho não avisaria ninguém.
  await acaoPrincipal(page, 'Continuar de onde você parou').click()
  // O `<label>`, não `getByText`: na tela de pergunta a casca também emite um
  // `<h1 class="sr-only">` com o mesmo enunciado (`AC-84` precisa de algo para
  // focar), e casar os dois violaria o modo estrito do Playwright.
  await expect(page.locator('label', { hasText: 'Quanto falta pagar hoje?' })).toBeVisible()
  expect(page.url()).toContain('#pergunta')

  // E agora o histórico do navegador — o caminho que depende de `popstate`.
  await page.goBack()

  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()
  expect(page.url()).toContain('#inicio')
  // `EC-27`: voltar pelo histórico produz o MESMO resultado que navegar por
  // dentro — foco e título incluídos, não só o conteúdo.
  await expect.poll(() => tituloDoDocumento(page)).toBe(`${TITULO_BASE} · Início`)
  await expect.poll(async () => (await focoAtual(page)).tag).toBe('H1')
})

/**
 * `AC-84` — os três comportamentos de `aplicarFocoDeNavegacao`, juntos.
 *
 * Sempre os três: uma navegação que rola ao topo mas não move o foco deixa
 * quem usa leitor de tela ouvindo a tela anterior enquanto olha a nova. O
 * `<h1>` da tela de pergunta é `sr-only` de propósito (o enunciado já é o
 * título visível), e ainda assim tem que receber o foco — daí a asserção
 * sobre `tagName`, não sobre visibilidade.
 */
test('AC-84: cada navegação foca o <h1> e atualiza document.title', async ({ page }) => {
  await interceptarBase(page, CASO, {
    inicio: {
      fase: 'coleta',
      proxima_etapa: { destino: 'progresso', ID_PERGUNTA: null, item_id: null },
    },
  })

  await abrirTela(page, CASO, 'inicio')

  await expect.poll(() => tituloDoDocumento(page)).toBe(`${TITULO_BASE} · Início`)
  await expect.poll(async () => await focoAtual(page)).toEqual({
    tag: 'H1',
    texto: 'Início',
  })

  // Uma navegação de verdade, disparada pela ação da tela — não um `goto`,
  // que remontaria a aplicação e provaria só a carga inicial.
  await acaoPrincipal(page, 'Ver as suas respostas').click()

  // `document.title` e o `<h1>` carregam o MESMO texto, e é isso que `AC-84`
  // pede: `aplicarFocoDeNavegacao` recebe o `titulo` que a tela deu à casca,
  // então os dois não podem divergir por construção.
  const TITULO_DO_PROGRESSO = 'Onde você está'
  await expect
    .poll(() => tituloDoDocumento(page))
    .toBe(`${TITULO_BASE} · ${TITULO_DO_PROGRESSO}`)
  await expect.poll(async () => (await focoAtual(page)).tag).toBe('H1')
  await expect
    .poll(async () => (await focoAtual(page)).texto)
    .toBe(TITULO_DO_PROGRESSO)

  // A rolagem também volta ao topo — o terceiro dos três comportamentos.
  expect(await page.evaluate(() => window.scrollY)).toBe(0)
})

/**
 * `AC-85` — o rodapé `.acoes` é `sticky` DE FATO, não só declarado.
 *
 * A prova é geométrica, não textual: com o conteúdo rolado, a caixa do
 * rodapé tem que continuar dentro da janela. `toBeInViewport` é o que
 * distingue "a regra CSS está no arquivo" de "o botão está na tela" — e a
 * segunda é a promessa feita ao aluno.
 *
 * O plano abaixo tem doze posições porque a tela precisa ser mais alta que a
 * janela nos DOIS projects, e a de desktop é alta.
 */
test('AC-85: o rodapé de ações fica visível com o conteúdo rolado', async ({ page }) => {
  const ordem = Array.from({ length: 12 }, (_, i) => ({
    posicao: i + 1,
    indice: i + 1,
    total: 12,
    DIVIDA_ID: `D${String(i + 1).padStart(3, '0')}`,
    JUSTIFICATIVA_POSICAO:
      'Maior custo efetivo entre as dívidas elegíveis nesta projeção.',
    valores_de_apoio: [{ rotulo: 'SALDO_DEVEDOR_ATUAL', valor: '5000.00' }],
  }))

  await interceptarBase(page, CASO, {
    inicio: {
      estado: 'PLANO_LIBERADO',
      fase: 'acompanhamento',
      mensagem: 'Seu plano está liberado.',
      proxima_etapa: { destino: 'acoes', ID_PERGUNTA: null, item_id: null },
      plano_liberado: true,
    },
  })
  await page.route(`**/caso/${CASO}/api/plano`, async (rota) => {
    await rota.fulfill({
      json: {
        CASO_ID: CASO,
        estado: 'PLANO_LIBERADO',
        plano: {
          titulo: 'Sua ordem projetada de quitação',
          corpo: 'Com os dados e condições de hoje, esta é a ordem projetada.',
          ordem,
          PRAZO_TOTAL: '18',
          CUSTO_FUTURO_TOTAL: '1200.00',
          ENGINE_VERSION: '1.0.1',
          PARAMETROS_VERSION: '1.0.1',
          cenario: 'RECOMENDADO',
          acoes: [],
          pendencias: null,
          MODO_ESTABILIZACAO: false,
          RESULTADO_CAIXA_OBSERVADO: '7700.00',
          reserva_mobilizavel: { pendente_de_decisao: false, valor: '3000.00' },
        },
      },
    })
  })

  await abrirTela(page, CASO, 'plano')
  const rodape = page.locator('.acoes')
  await expect(rodape).toBeVisible()

  // A premissa do teste: sem conteúdo mais alto que a janela, `sticky` não
  // tem o que provar, e um teste que passasse assim não provaria nada.
  const rolavel = await page.evaluate(
    () => document.documentElement.scrollHeight > window.innerHeight,
  )
  expect(rolavel).toBe(true)

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2))

  await expect(rodape).toBeInViewport()
  await expect(page.getByRole('link', { name: 'Baixar em PDF' })).toBeInViewport()
})

/**
 * `AC-80` — a conta sem papel não vê caminho para a equipe.
 *
 * **Auditado no DOM, não no servidor.** O servidor já recusa com `403`, e
 * isso continua valendo; o que este teste cobre é o outro lado: o aluno que
 * VÊ "Fila", clica e recebe `403` conclui que o sistema está quebrado, ou que
 * há algo seu que não consegue ver. Então a auditoria varre `href` e
 * `onclick` de tudo o que existe na página, em todas as telas do fluxo do
 * aluno.
 *
 * Sem login nesta carga, `eRevisor` é `null` e `App.tsx` trata como
 * não-revisor — negar por omissão. A segunda metade do teste digita o hash da
 * fila na mão: é o caminho que um link antigo ou um colega teria dado ao
 * aluno.
 */
test('AC-80: conta sem papel não encontra caminho para a área da equipe', async ({
  page,
}) => {
  const ROTAS_DA_EQUIPE = ['#equipe-fila', '#equipe-caso', '#equipe-painel']

  await interceptarBase(page, CASO)
  await page.route(`**/api/revisao/fila`, async (rota) => {
    // Se a interface chegar a consultar a fila, o teste tem que falhar pela
    // asserção de DOM — não travar esperando um backend que não está no ar.
    await rota.fulfill({ status: 403, json: { erro: 'Acesso restrito.' } })
  })

  await abrirTela(page, CASO, 'inicio')
  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()

  const alcancaveis = await page.evaluate(() => {
    const alvos: string[] = []
    for (const elemento of document.querySelectorAll('*')) {
      const href = elemento.getAttribute('href')
      if (href) alvos.push(href)
      const clique = elemento.getAttribute('onclick')
      if (clique) alvos.push(clique)
      const acao = elemento.getAttribute('formaction')
      if (acao) alvos.push(acao)
    }
    return alvos
  })

  for (const rota of ROTAS_DA_EQUIPE) {
    for (const alvo of alcancaveis) {
      expect(alvo).not.toContain(rota.slice(1))
    }
  }

  // Nenhum texto de navegação de equipe tampouco: o aluno não deve nem
  // saber que a fila existe a partir desta tela.
  const textoDaTela = await page.locator('body').innerText()
  for (const rotulo of ['Fila de conferência', 'Painel do operador']) {
    expect(textoDaTela).not.toContain(rotulo)
  }

  // E digitar o hash não abre: a interface manda ao Início em vez de deixar
  // o aluno numa tela que o servidor vai recusar.
  await abrirTela(page, CASO, 'equipe-fila')
  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()
  await expect(
    page.getByRole('heading', { name: 'Planos aguardando conferência' }),
  ).toHaveCount(0)
})

/**
 * `AC-87` — a área da equipe usa 900px, distinta da coluna do aluno.
 *
 * A diferença não é estética: a coluna de leitura do aluno existe para uma
 * pergunta por vez; o revisor compara linhas de uma fila. A asserção é sobre
 * o `max-width` COMPUTADO, não sobre a caixa medida — no project de 360px a
 * caixa tem 360px nas duas áreas, e comparar larguras renderizadas passaria
 * por acidente de viewport em vez de provar a regra.
 *
 * **`AC-106` (Rodada 7) mudou o número do aluno, não a regra.** A coluna dele
 * continua 560px onde o protótipo foi validado — no celular —, e cresce a
 * partir de 1024px, porque *"a maior parte será preenchida no computador"*
 * (`OQ-29`) e cem perguntas por uma fresta era o desperdício relatado. A
 * área da EQUIPE segue nos 900px que `AC-87` fixou: aquele requisito é sobre
 * a tela do revisor, e nada nele foi revogado.
 *
 * O que este teste continua provando, nas duas larguras, é o que `AC-87` de
 * fato promete: as duas áreas têm colunas DISTINTAS, e a do revisor é a de
 * 900px.
 */
test('AC-87: a área da equipe usa 900px, distinta da coluna do aluno', async ({
  page,
}, infoDoTeste) => {
  const larguraDaColuna = () =>
    page.evaluate(() => {
      const corpo = document.querySelector('.corpo')
      const coluna = corpo?.parentElement
      return coluna ? getComputedStyle(coluna).maxWidth : ''
    })

  // O fluxo do aluno, para a comparação existir de fato. `T-186`: a conta
  // revisora deixou de alcançar o Início, então a largura do aluno é medida
  // numa sessão à parte, genuinamente não-revisora — comparar as duas
  // dentro da MESMA sessão de revisor não é mais possível, por desenho.
  await interceptarBase(page, CASO)
  await abrirTela(page, CASO, 'inicio')
  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()
  const doAluno = await larguraDaColuna()
  if (infoDoTeste.project.name === 'mobile-360') {
    // A tela validada com stakeholders — intocada, que é o pé de `AC-106`
    // que mais custa se quebrar.
    expect(doAluno).toBe('560px')
  } else {
    // No computador ela cresce (`AC-106`), e não para nos 900px da equipe:
    // são duas geometrias com propósitos diferentes, não uma escala.
    expect(doAluno).not.toBe('560px')
    expect(doAluno).not.toBe('900px')
  }

  // Agora a largura da equipe — sessão revisora à parte. A última rota
  // registrada vence no Playwright, então isto substitui os mocks acima.
  await interceptarBase(page, CASO, { eRevisor: true })
  await page.route(`**/api/revisao/fila`, async (rota) => {
    await rota.fulfill({ json: { itens: [] } })
  })
  // `T-186`: o login já leva direto à fila — não há mais um passo de
  // navegação do Início até lá.
  await entrarComoRevisor(page, CASO)
  expect(await larguraDaColuna()).toBe('900px')
})

/**
 * `AC-91`, `EC-26` — hash desconhecido cai no Início.
 *
 * Nunca uma tela em branco, e nunca um erro que sugira que o caso está
 * perdido: o Início é o único destino honesto para um hash que não
 * reconhecemos, porque é a tela que sabe ler a fase do caso e decidir o
 * próximo passo.
 */
test('AC-91/EC-26: hash desconhecido cai no Início, nunca em tela branca', async ({
  page,
}) => {
  await interceptarBase(page, CASO)

  await abrirTela(page, CASO, 'nao-existe')

  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()
  await expect(acaoPrincipal(page, 'Continuar de onde você parou')).toBeVisible()
  // A casca inteira está lá — um fallback que renderizasse só o `<h1>`
  // seria a tela em branco de `EC-26` com um título em cima.
  await expect(page.locator('.corpo')).toBeVisible()
  await expect(page.locator('.acoes')).toBeVisible()

  // Um parâmetro inválido em rota conhecida também não produz tela branca —
  // `#coleta-dirigida/9` é um bloco que não existe.
  await abrirTela(page, CASO, 'coleta-dirigida/9')
  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()

  // E a raiz sem hash nenhum cai no mesmo lugar (`ROTA_PADRAO`), sem o
  // "‹ Voltar" que só existe onde há para onde voltar.
  await page.goto(`/?caso=${CASO}`)
  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()
  await expect(voltarDaTela(page)).toHaveCount(0)
})

// ---------------------------------------------------------------------------
// `AC-83` — toda tela é alcançável por ação explícita da tela anterior.
//
// A revisão de T-152 encontrou SETE rotas sem porta de entrada nenhuma: só o
// `switch` do `App.tsx` as mencionava. Duas doíam de verdade — o aluno havia
// perdido o CRUD de dívidas junto com a barra de abas, e o revisor não tinha
// como abrir a tela de conferência que `T-150` criou para ele. Estes dois
// testes são a prova de que os caminhos existem, e a trava contra perdê-los
// de novo.
// ---------------------------------------------------------------------------

const CASO_ACESSO = 'CASO-ACESSO'

const INICIO_ACESSO = {
  CASO_ID: CASO_ACESSO,
  estado: 'COLETA_INICIAL',
  fase: 'coleta',
  mensagem: 'Sua coleta está em andamento.',
  proxima_etapa: { destino: 'pergunta', ID_PERGUNTA: 'B5.A01', item_id: 'D001' },
  progresso: { respondidas: 62, total: 172 },
  valor_em_destaque: null,
  plano_liberado: false,
  versao_do_plano: null,
}

test('AC-83: o progresso dá acesso às fichas — o CRUD de dívidas de RF-53', async ({
  page,
}) => {
  await page.route(`**/caso/${CASO_ACESSO}/inicio`, (r) =>
    r.fulfill({ json: INICIO_ACESSO }),
  )
  // `T-154`: o `App` pergunta quem é a sessão na carga da página — sem este
  // intercept o teste espera o proxy do Vite desistir antes de seguir.
  //
  // `e_revisor: false` — `T-186` fez o oposto redirecionar (revisor não
  // alcança tela de aluno), então esta conta precisa ser genuinamente
  // aluno para chegar ao Progresso.
  await page.route('**/api/conta/eu', (r) =>
    r.fulfill({
      json: {
        email: 'aluna@exemplo.gov.br',
        conta_id: 'C1',
        e_revisor: false,
        CASO_ID: CASO_ACESSO,
        casos: [CASO_ACESSO],
      },
    }),
  )
  await page.route(`**/caso/${CASO_ACESSO}/fichas/DIVIDA_ID`, (r) =>
    r.fulfill({
      json: {
        CASO_ID: CASO_ACESSO,
        escopo: 'DIVIDA_ID',
        fichas: [{ item_id: 'D001', completa: false, campos: [] }],
      },
    }),
  )

  await page.goto(`/?caso=${CASO_ACESSO}#progresso`)

  const irParaFichas = page
    .locator('.acoes')
    .getByRole('button', { name: /dívidas/i })
  await expect(irParaFichas).toBeVisible()
  await irParaFichas.click()

  // Sem este caminho o aluno não cadastra nem remove dívida — `AC-04`.
  await expect(page.locator('h1')).toContainText(/dívida/i)
})

test('AC-83 + AC-29: a fila abre a conferência do caso', async ({ page }) => {
  await page.route(`**/caso/${CASO_ACESSO}/inicio`, (r) =>
    r.fulfill({ json: INICIO_ACESSO }),
  )
  // `T-154`: o `App` pergunta quem é a sessão na carga da página — sem este
  // intercept o teste espera o proxy do Vite desistir antes de seguir.
  await page.route('**/api/conta/eu', (r) =>
    r.fulfill({
      json: {
        email: 'revisor@exemplo.gov.br',
        conta_id: 'C1',
        e_revisor: true,
        CASO_ID: CASO_ACESSO,
        casos: [CASO_ACESSO],
      },
    }),
  )
  await page.route('**/api/conta/login', (r) =>
    r.fulfill({ json: { email: 'revisor@exemplo.gov.br', conta_id: 'C1', e_revisor: true } }),
  )
  await page.route('**/api/revisao/fila', (r) =>
    r.fulfill({
      json: {
        itens: [
          {
            CASO_ID: 'CASO-001',
            SNAPSHOT_ID: 'S1',
            versao: 2,
            DATA_REFERENCIA: '2026-03-15',
            MOTIVO_RECALCULO: null,
            EVENTO_RECALCULO: null,
            METODO_RECOMENDADO_PIQ: 'HIBRIDO',
            STATUS_METODO: 'DEFINITIVO_NA_DATA',
            entra_por_politica: true,
            e_metodologico: false,
            ENGINE_VERSION: '1.0.1',
            PARAMETROS_VERSION: '1.0.1',
          },
        ],
      },
    }),
  )
  await page.route('**/api/revisao/caso/**', (r) =>
    r.fulfill({ status: 404, json: { erro: 'sem plano' } }),
  )
  // `TelaEquipeCaso` pede as seis classificações de erro ao abrir (elas vêm
  // do servidor, nunca codificadas no cliente — `OQ-12`).
  await page.route('**/revisao/caso/*/decisao', (r) =>
    r.fulfill({
      json: {
        classificacoes_erro: ['TEXTO', 'PARAMETRO', 'DADO', 'REGRA', 'CALCULO', 'UX'],
      },
    }),
  )

  await page.goto(`/?caso=${CASO_ACESSO}#entrada`)
  await page.getByLabel('Seu e-mail').fill('revisor@exemplo.gov.br')
  await page.getByLabel('Sua senha').fill('senha-de-teste')
  // Não é `acaoPrincipal`: `AC-82` isenta a entrada da casca `Tela`
  // (T-185), e o botão é filho direto do `<form>`, não do rodapé `.acoes`.
  await page.getByRole('button', { name: 'Entrar' }).click()

  // `T-186`: o revisor cai DIRETO na fila — nunca no Início do aluno. Não
  // há mais um botão "Ir para a fila" para clicar; `aoEntrar` já manda para
  // lá assim que sabe que a conta é revisora.
  await expect(
    page.getByRole('heading', { name: /aguardando conferência/i }),
  ).toBeVisible()

  // `AC-29`: sem este botão a tela de conferência era inalcançável, e o
  // revisor não tinha como liberar plano nenhum pela interface.
  const abrir = page.getByRole('button', { name: /abrir para conferir/i })
  await expect(abrir).toBeVisible()
  await abrir.click()

  await expect
    .poll(() => page.evaluate(() => window.location.hash))
    .toContain('equipe-caso/CASO-001')
})

test('T-169/T-171: destino e fase desconhecidos não derrubam nem mentem', async ({
  page,
}) => {
  // Um servidor mais novo que este cliente é a situação NORMAL durante um
  // deploy. Antes: `TEXTO_DA_ETAPA[destino]` devolvia `undefined`,
  // `texto.rotulo` lançava, e sem `ErrorBoundary` a aplicação inteira virava
  // tela branca — sem mensagem, sem botão, sem caminho.
  const erros: string[] = []
  page.on('pageerror', (erro) => erros.push(String(erro)))

  // O `as` é o ponto do teste, não um atalho: `DestinoDaEtapa` e `Fase` são
  // uniões fechadas, e é isso que o TypeScript garante DENTRO deste
  // cliente. O servidor não compila junto — um deploy que adicione uma fase
  // entrega exatamente este payload, que os tipos daqui não preveem. Sem o
  // `as`, o cenário seria inexprimível e o defeito continuaria sem teste.
  await interceptarBase(page, CASO, {
    inicio: {
      proxima_etapa: {
        destino: 'etapa_do_futuro' as never,
        ID_PERGUNTA: null,
        item_id: null,
      },
      fase: 'fase_do_futuro' as never,
    },
  })
  await abrirTela(page, CASO, 'inicio')

  // A tela existe e é utilizável.
  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()
  await expect(page.locator('.cartao-proximo')).toBeVisible()
  await expect(page.locator('.acoes').getByRole('button').first()).toBeVisible()
  expect(erros).toHaveLength(0)

  // `T-171`: a trilha não diz a quem talvez já tenha plano que ele voltou à
  // primeira pergunta.
  const emCurso = trilha(page).locator('li[aria-current="step"]')
  await expect(emCurso).toHaveCount(1)
  await expect(emCurso).not.toContainText('Suas respostas')
})

test('T-170: o revisor que recarrega em #equipe-fila continua lá', async ({ page }) => {
  // **O defeito.** O redirecionamento de `AC-80` usava `eRevisor !== true`,
  // e `eRevisor` nasce `null` ("ainda perguntando ao servidor"). Num F5, o
  // `null` contava como não-revisor: o revisor era mandado ao Início antes
  // de `/api/conta/eu` responder — e o `replaceState` destruía a URL, de
  // modo que nem o "voltar" do navegador o trazia de volta.
  //
  // O caminho é o do produto: F5 é o que qualquer pessoa faz.
  //
  // As rotas são declaradas aqui, não por `interceptarBase`: `CASO_ACESSO`
  // tem o próprio conjunto de mocks (ver `INICIO_ACESSO`, acima), e é o
  // padrão dos demais testes de revisor deste arquivo.
  await page.route(`**/caso/${CASO_ACESSO}/inicio`, (r) =>
    r.fulfill({ json: INICIO_ACESSO }),
  )
  await page.route('**/api/conta/eu', (r) =>
    r.fulfill({
      json: {
        email: 'revisor@exemplo.gov.br',
        conta_id: 'C1',
        e_revisor: true,
        CASO_ID: CASO_ACESSO,
        casos: [CASO_ACESSO],
      },
    }),
  )
  await page.route('**/api/revisao/fila', (r) => r.fulfill({ json: { itens: [] } }))

  await page.goto(`/?caso=${CASO_ACESSO}#equipe-fila`)
  await expect(page.getByRole('heading', { name: /aguardando conferência/i })).toBeVisible()

  // O F5 propriamente dito.
  await page.reload()

  await expect(page.getByRole('heading', { name: /aguardando conferência/i })).toBeVisible()
  expect(await page.evaluate(() => window.location.hash)).toContain('equipe-fila')
})

// ---------------------------------------------------------------------------
// `T-154` — a descoberta do caso pela sessão.
//
// Este teste nasceu de um defeito REAL que só apareceu em navegador: com a
// rota `/api/conta/eu` no ar e o `App` consultando-a na carga da página, eu
// declarei `T-154` fechada. Mas `onEntrou` atualizava só o papel, nunca o
// `casoId` — depois de entrar sem `?caso=` na URL o aluno voltava à tela de
// login com a sessão já instalada. Credencial aceita, aplicação
// inalcançável, e todos os gates verdes.
// ---------------------------------------------------------------------------

const CASO_SESSAO = 'CASO-SESSAO'

test('T-154: entrar SEM `?caso=` na URL alcança o Início', async ({ page }) => {
  // O ciclo de vida REAL da sessão: `401` antes do login, `200` depois. Um
  // mock que responda `200` desde o início não testa nada — ele descreve um
  // navegador que já tinha sessão, e aí o login nem deveria aparecer.
  let autenticado = false

  await page.route('**/api/conta/eu', (rota) =>
    autenticado
      ? rota.fulfill({
          json: {
            email: 'maria@exemplo.gov.br',
            conta_id: 'CONTA-SESSAO',
            e_revisor: false,
            CASO_ID: CASO_SESSAO,
            casos: [CASO_SESSAO],
          },
        })
      : rota.fulfill({ status: 401, json: { erro: 'Sessão inválida ou expirada.' } }),
  )

  // `POST /api/conta/login` NÃO devolve `CASO_ID` — é o contrato real, e é
  // por isso que o cliente precisa reconsultar a sessão depois de entrar.
  await page.route('**/api/conta/login', (rota) => {
    autenticado = true
    return rota.fulfill({
      json: { email: 'maria@exemplo.gov.br', conta_id: 'CONTA-SESSAO', e_revisor: false },
    })
  })

  await page.route(`**/caso/${CASO_SESSAO}/inicio`, (rota) =>
    rota.fulfill({ json: inicioEmColeta(CASO_SESSAO) }),
  )

  await page.goto('/')
  await expect(page.locator('h1')).toHaveText(
    `${TITULO.antes}${TITULO.destaque}${TITULO.depois}`,
  )

  await page.getByLabel('Seu e-mail').fill('maria@exemplo.gov.br')
  await page.getByLabel('Sua senha').fill('senha-de-teste')
  // Não é `acaoPrincipal`: `AC-82` isenta a entrada da casca `Tela`
  // (T-185), e o botão é filho direto do `<form>`, não do rodapé `.acoes`.
  await page.getByRole('button', { name: 'Entrar' }).click()

  await expect(page.locator('h1')).toHaveText('Início')
  // A prova de que o caso veio da SESSÃO, não da URL.
  expect(await page.evaluate(() => window.location.search)).not.toContain('caso=')
})

test('T-154: sessão válida na carga da página não mostra login', async ({ page }) => {
  // Quem já tem cookie não precisa entrar de novo. Mostrar login a quem tem
  // sessão seria teatro: o cliente não sabe se o cookie vale, e fingir que
  // sabe é pior que confiar no `200` do servidor.
  await page.route('**/api/conta/eu', (rota) =>
    rota.fulfill({
      json: {
        email: 'maria@exemplo.gov.br',
        conta_id: 'CONTA-SESSAO',
        e_revisor: false,
        CASO_ID: CASO_SESSAO,
        casos: [CASO_SESSAO],
      },
    }),
  )
  await page.route(`**/caso/${CASO_SESSAO}/inicio`, (rota) =>
    rota.fulfill({ json: inicioEmColeta(CASO_SESSAO) }),
  )

  await page.goto('/')

  await expect(page.locator('h1')).toHaveText('Início')
})

// ---------------------------------------------------------------------------
// Rodada 6 (`T-158`) — a orientação: onde estou, e o que é isto.
//
// **De onde estes testes vêm.** Não de uma revisão de código: do primeiro uso
// real, em que o relato foi *"não gostei, me senti perdido, sem saber o que é,
// qual o objetivo"*. A tela mostrava "Continuar de onde você parou" e "3 de
// 101" — as duas coisas corretas, e nenhuma delas respondendo à pergunta que o
// aluno tinha. `RF-64`..`RF-67` são a resposta, e o que segue é a prova de que
// ela está no navegador.
//
// A trilha (`TrilhaDaJornada`) e as boas-vindas (`TelaBoasVindas`) são
// testadas pela interface que o aluno vê, nunca pelas classes CSS: o que
// `AC-93` promete é uma lista de cinco etapas com UMA marcada como atual, e
// `aria-current="step"` é o contrato dessa marca — quem não vê a cor depende
// só dele.
// ---------------------------------------------------------------------------

const CASO_JORNADA = 'CASO-JORNADA-E2E'

/** A trilha inteira — o seletor único de `TrilhaDaJornada`. */
function trilha(page: Page) {
  return page.locator('[aria-label="Sua jornada no PIQ"]')
}

/** As cinco etapas, na ordem do DOM. */
function etapasDaTrilha(page: Page) {
  return trilha(page).locator('li')
}

/** Os rótulos das cinco etapas, na ordem em que o aluno as percorre. */
const ROTULOS_DAS_ETAPAS: readonly string[] = [
  'Suas respostas',
  'Cálculo do plano',
  'Conferência da equipe',
  'Seu plano',
  'Acompanhamento',
]

test('AC-93: a trilha mostra as cinco etapas, com exatamente uma em curso', async ({
  page,
}) => {
  await interceptarBase(page, CASO_JORNADA)
  await abrirTela(page, CASO_JORNADA, 'inicio')

  await expect(trilha(page)).toBeVisible()

  // A CONTAGEM é a asserção que carrega o requisito: `RF-64` promete a
  // jornada INTEIRA, e uma trilha de quatro etapas esconde justamente o
  // pedaço que o aluno ainda não conhece.
  await expect(etapasDaTrilha(page)).toHaveCount(5)

  // E na ordem: a jornada é uma sequência, não um conjunto. Uma trilha com as
  // mesmas cinco etapas embaralhadas responderia "onde estou" errado.
  const rotulos = await etapasDaTrilha(page).evaluateAll((itens) =>
    itens.map((item) => item.querySelector('.linha span')?.textContent?.trim() ?? ''),
  )
  expect(rotulos).toEqual([...ROTULOS_DAS_ETAPAS])

  // UMA em curso — nem zero (trilha sem "você está aqui") nem duas.
  await expect(trilha(page).locator('li[aria-current="step"]')).toHaveCount(1)
})

/**
 * `AC-94` — a etapa em curso corresponde à fase, em cada uma das cinco.
 *
 * Um teste por fase, e não um laço dentro de um teste, pelo mesmo motivo de
 * `AC-81`: quando quebra, o relatório precisa dizer QUAL fase quebrou.
 *
 * O mapeamento não é identidade, e é de propósito: `revisao` e `reprovado`
 * caem na MESMA etapa ("Conferência da equipe"), porque do ponto de vista do
 * aluno o plano segue com a equipe nos dois casos, e uma sexta etapa chamada
 * "reprovado" transformaria um passo do processo num veredito sobre ele.
 * O "cálculo do plano" (índice 1) nunca é fase própria — quem está calculando
 * espera na conferência.
 */
const ETAPA_ESPERADA_POR_FASE: readonly {
  fase: InicioDeTeste['fase']
  estado: string
  destino: InicioDeTeste['proxima_etapa']['destino']
  /** Índice 0-based da etapa que deve estar em curso. */
  indice: number
}[] = [
  { fase: 'coleta', estado: 'COLETA_INICIAL', destino: 'pergunta', indice: 0 },
  { fase: 'revisao', estado: 'AGUARDANDO_REVISAO', destino: 'aguardando', indice: 2 },
  { fase: 'reprovado', estado: 'REPROVADO', destino: 'progresso', indice: 2 },
  { fase: 'plano', estado: 'PLANO_LIBERADO', destino: 'bloco10', indice: 3 },
  { fase: 'acompanhamento', estado: 'EM_ACOMPANHAMENTO', destino: 'acoes', indice: 4 },
]

for (const caso of ETAPA_ESPERADA_POR_FASE) {
  test(`AC-94: na fase ${caso.fase} a etapa em curso é "${ROTULOS_DAS_ETAPAS[caso.indice]}"`, async ({
    page,
  }) => {
    await interceptarBase(page, CASO_JORNADA, {
      inicio: {
        estado: caso.estado,
        fase: caso.fase,
        proxima_etapa: {
          destino: caso.destino,
          ID_PERGUNTA: caso.destino === 'pergunta' ? 'B5.B03' : null,
          item_id: caso.destino === 'pergunta' ? 'D001' : null,
        },
        plano_liberado: caso.fase !== 'coleta',
      },
    })
    await abrirTela(page, CASO_JORNADA, 'inicio')

    const etapas = etapasDaTrilha(page)
    await expect(etapas).toHaveCount(5)

    // Nenhuma fase produz trilha vazia nem duas em curso — a metade do
    // critério que vale para TODAS as fases, e que um teste só da fase feliz
    // nunca pegaria.
    const emCurso = trilha(page).locator('li[aria-current="step"]')
    await expect(emCurso).toHaveCount(1)
    await expect(emCurso).toContainText(ROTULOS_DAS_ETAPAS[caso.indice])
    await expect(emCurso).toContainText('Agora')

    // As ANTERIORES aparecem como concluídas...
    for (let i = 0; i < caso.indice; i += 1) {
      await expect(etapas.nth(i)).toContainText('Feito')
      await expect(etapas.nth(i)).not.toHaveAttribute('aria-current', 'step')
    }

    // ...e as SEGUINTES não. "Feito" numa etapa futura seria promessa falsa:
    // diria ao aluno que a equipe já conferiu um plano que não existe.
    for (let i = caso.indice + 1; i < 5; i += 1) {
      await expect(etapas.nth(i)).not.toContainText('Feito')
      await expect(etapas.nth(i)).not.toHaveAttribute('aria-current', 'step')
    }
  })
}

test('AC-95: a trilha é visível sem interação e não exige rolagem horizontal', async ({
  page,
}, infoDoTeste) => {
  await interceptarBase(page, CASO_JORNADA)
  await abrirTela(page, CASO_JORNADA, 'inicio')

  // Visível SEM INTERAÇÃO: `toBeVisible` logo após a carga, sem clique nenhum
  // antes. Esconder o mapa atrás de um clique é exatamente o que produziu o
  // relato de estar perdido.
  await expect(trilha(page)).toBeVisible()

  // E não está dentro de `<details>` — um `<details>` fechado tem conteúdo que
  // o Playwright já considera invisível, mas um `<details open>` passaria pela
  // asserção acima e ainda assim daria ao aluno um triângulo para fechar o
  // mapa. A auditoria estrutural é o que fecha essa brecha.
  const dentroDeDetails = await trilha(page).evaluate(
    (elemento) => elemento.closest('details') !== null,
  )
  expect(dentroDeDetails).toBe(false)

  // As cinco etapas estão TODAS na tela, não só o cartão: uma trilha visível
  // cujas etapas 4 e 5 ficam fora do container não mostra a jornada inteira.
  const etapas = etapasDaTrilha(page)
  await expect(etapas).toHaveCount(5)
  for (let i = 0; i < 5; i += 1) {
    await expect(etapas.nth(i)).toBeVisible()
  }

  // A 360px — a largura que a NFR de responsividade fixa, e a do celular do
  // servidor público que é a persona do PIQ — nada vaza para os lados.
  if (infoDoTeste.project.name === 'mobile-360') {
    const larguras = await page.evaluate(() => ({
      conteudo: document.documentElement.scrollWidth,
      janela: window.innerWidth,
    }))
    expect(larguras.conteudo).toBeLessThanOrEqual(larguras.janela)
  }
})

test('AC-115: a trilha é informativa — nenhum degrau é clicável', async ({ page }) => {
  await interceptarBase(page, CASO_JORNADA)
  await abrirTela(page, CASO_JORNADA, 'inicio')

  await expect(trilha(page)).toBeVisible()

  // **Por que esta trava existe.** A Rodada 8 deu à trilha trilho contínuo e
  // marcas de estado — e um stepper com esse desenho é, em quase todo produto,
  // navegável. Aqui não pode ser: `RF-57`/`AC-83` mataram a barra de sete abas
  // porque, para um aluno endividado e inseguro, oferecer todas as telas de
  // uma vez devolve a pergunta "o que eu faço agora?" sem resposta.
  //
  // A trilha responde "onde estou"; o único botão da tela continua sendo o da
  // próxima etapa. Sem esta asserção, a primeira pessoa que achar natural
  // tornar os degraus clicáveis reintroduz o desenho que o produto rejeitou.
  const interativosNaTrilha = await trilha(page).evaluate(
    (elemento) =>
      elemento.querySelectorAll('button, a, [role="button"], [role="link"], [tabindex]')
        .length,
  )
  expect(interativosNaTrilha).toBe(0)

  // E a estrutura que `AC-93`/`AC-94` usam como seletor continua de pé: cinco
  // `<li>`, o rótulo em `.linha span`, `aria-current="step"` em exatamente uma.
  await expect(etapasDaTrilha(page)).toHaveCount(5)
  await expect(trilha(page).locator('li[aria-current="step"]')).toHaveCount(1)
})

/**
 * `AC-96` — o que falta vem COM unidade.
 *
 * O defeito original não era número errado: "3 de 101" estava certo. Era um
 * número sem substantivo, que o aluno não tinha como interpretar. Por isso a
 * asserção exige a palavra "perguntas", e não só o `98`: um teste que casasse
 * apenas o número passaria de volta com a barra de progresso antiga.
 */
test('AC-96: na coleta, a etapa em curso diz quantas PERGUNTAS faltam', async ({
  page,
}) => {
  await interceptarBase(page, CASO_JORNADA, {
    inicio: { progresso: { respondidas: 3, total: 101 } },
  })
  await abrirTela(page, CASO_JORNADA, 'inicio')

  await expect(trilha(page).locator('li[aria-current="step"]')).toContainText(
    'Faltam 98 perguntas',
  )
})

test('AC-96: com uma pergunta restante, a contagem vai para o singular', async ({
  page,
}) => {
  await interceptarBase(page, CASO_JORNADA, {
    inicio: { progresso: { respondidas: 100, total: 101 } },
  })
  await abrirTela(page, CASO_JORNADA, 'inicio')

  const emCurso = trilha(page).locator('li[aria-current="step"]')
  await expect(emCurso).toContainText('Falta 1 pergunta')
  // "Faltam 1 perguntas" é o que um template sem plural produz, e é o tipo de
  // detalhe que faz o texto soar automático justamente onde ele precisa soar
  // humano.
  await expect(emCurso).not.toContainText('Faltam 1')
})

/** O payload de quem ainda não respondeu nada — o gatilho de `RF-66`. */
const SEM_NENHUMA_RESPOSTA: Partial<InicioDeTeste> = {
  progresso: { respondidas: 0, total: 101 },
}

test('AC-97: sem nenhuma resposta, as boas-vindas vêm antes do Início', async ({
  page,
}) => {
  await interceptarBase(page, CASO_JORNADA, { inicio: SEM_NENHUMA_RESPOSTA })
  await abrirTela(page, CASO_JORNADA, 'inicio')

  // ANTES do Início: o `<h1>` é o das boas-vindas, e o do Início não está na
  // tela. Se as duas coexistissem, a apresentação seria só mais um bloco na
  // página que o aluno já achou confusa.
  await expect(page.locator('h1')).toHaveText('Vamos montar o seu plano de quitação')
  await expect(page.getByRole('heading', { name: 'Início' })).toHaveCount(0)

  // A promessa que mais importa de `RF-66`, porque é a que sustenta `RF-23`:
  // nenhum plano chega ao aluno sem revisão humana. Pedir cem perguntas sobre
  // o dinheiro de alguém sem dizer isso é pedir uma confiança não merecida.
  await expect(page.getByText('Uma pessoa da equipe confere')).toBeVisible()
  await expect(
    page.getByText('Nenhum plano chega a você sem alguém ter revisado antes.'),
  ).toBeVisible()

  // E as outras duas promessas de `RF-66`: o que ele recebe ao final, e que
  // pode parar e voltar (`RF-10`).
  await expect(page.getByText(/ordem de quitação/i).first()).toBeVisible()
  await expect(page.getByText(/pode parar quando quiser e voltar depois/i)).toBeVisible()
})

test('AC-98: com ao menos uma resposta, as boas-vindas NÃO aparecem', async ({
  page,
}) => {
  await interceptarBase(page, CASO_JORNADA, {
    inicio: { progresso: { respondidas: 1, total: 101 } },
  })
  await abrirTela(page, CASO_JORNADA, 'inicio')

  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()
  await expect(
    page.getByRole('heading', { name: 'Vamos montar o seu plano de quitação' }),
  ).toHaveCount(0)
  // Vai direto ao Início COM a trilha: quem já começou continua vendo o mapa,
  // que é o que `AC-93` promete "em qualquer fase".
  await expect(trilha(page)).toBeVisible()
})

test('AC-98: "Começar" nas boas-vindas leva ao Início — a tela nunca é bloqueio', async ({
  page,
}) => {
  await interceptarBase(page, CASO_JORNADA, { inicio: SEM_NENHUMA_RESPOSTA })
  await abrirTela(page, CASO_JORNADA, 'inicio')

  await expect(page.locator('h1')).toHaveText('Vamos montar o seu plano de quitação')
  await acaoPrincipal(page, 'Começar').click()

  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()
  await expect(trilha(page)).toBeVisible()
})

/**
 * `AC-99`, `RF-67` — o ponto da jornada vem do servidor, não do aparelho.
 *
 * **Duas provas, porque cada uma mente de um jeito diferente.**
 *
 * A auditoria de código (abaixo) pega o caso em que o componente leria
 * `localStorage` num caminho que o E2E não exercita — um `if` que só dispara
 * na segunda visita, por exemplo. A instrumentação em navegador (o teste
 * seguinte) pega o caso em que a leitura mora num módulo importado, onde uma
 * busca por texto nos dois arquivos não alcançaria.
 *
 * O que está em jogo não é estilo: `RF-10` promete que o aluno começa no
 * computador do trabalho e continua no celular. Uma marca gravada no aparelho
 * faria a apresentação reaparecer para quem já respondeu metade, ou sumir
 * para quem nunca a viu.
 */
test('AC-99: nem a trilha nem as boas-vindas leem localStorage/sessionStorage no código', async () => {
  const raiz = fileURLToPath(new URL('../../src/', import.meta.url))
  const ARQUIVOS = ['componentes/TrilhaDaJornada.tsx', 'telas/TelaBoasVindas.tsx']

  for (const relativo of ARQUIVOS) {
    const fonte = readFileSync(raiz + relativo, 'utf8')
    // Os comentários saem da auditoria porque o cabeçalho de
    // `TrilhaDaJornada` cita `localStorage` justamente para dizer que NÃO o
    // usa — uma asserção que casasse o comentário proibiria a documentação da
    // decisão, que é a parte que impede alguém de reintroduzi-la.
    const codigo = fonte
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/\/\/[^\n]*/g, '')

    expect(codigo, `${relativo} não pode ler localStorage`).not.toContain('localStorage')
    expect(codigo, `${relativo} não pode ler sessionStorage`).not.toContain(
      'sessionStorage',
    )
  }
})

test('AC-99: a carga do Início não lê nenhum armazenamento do navegador', async ({
  page,
}) => {
  await interceptarBase(page, CASO_JORNADA, { inicio: SEM_NENHUMA_RESPOSTA })

  // Instrumentado ANTES do carregamento do documento — depois já seria tarde:
  // um módulo que lê no topo do arquivo teria lido.
  await page.addInitScript(() => {
    const janela = window as unknown as { __chavesLidas: string[] }
    janela.__chavesLidas = []
    const original = Storage.prototype.getItem
    Storage.prototype.getItem = function (this: Storage, chave: string) {
      janela.__chavesLidas.push(chave)
      return original.call(this, chave)
    }
  })

  await abrirTela(page, CASO_JORNADA, 'inicio')
  await expect(page.locator('h1')).toHaveText('Vamos montar o seu plano de quitação')
  await acaoPrincipal(page, 'Começar').click()
  await expect(trilha(page)).toBeVisible()

  const chavesLidas = await page.evaluate(
    () => (window as unknown as { __chavesLidas: string[] }).__chavesLidas,
  )
  expect(chavesLidas).toEqual([])
})

// ---------------------------------------------------------------------------
// Rodada 7 (`T-160`, `T-161`) — rever, corrigir e caber na tela.
//
// **De onde estes testes vêm.** Do segundo teste com usuário, sobre a mesma
// tela da Rodada 6. Três relatos, três defeitos distintos: *"as perguntas que
// eu respondi não consigo editar"*, *"nem consigo ver o que foi respondido, e
// se eu esquecer"* e *"por que está com a largura fixa?"*.
//
// Os dois primeiros não eram limitação do servidor — `GET
// /caso/{id}/pergunta/{ID}` sempre devolveu qualquer pergunta com o valor
// anterior, e a gravação sempre aceitou sobrescrita. Faltava TELA. É o mesmo
// padrão da Rodada 6, e é o tipo de lacuna que só aparece quando alguém usa o
// produto de verdade.
//
// Os enunciados e valores abaixo são inventados: copiar a redação real do
// questionário para um teste criaria a segunda fonte de verdade que `AC-73`
// existe para impedir. O que se prova aqui é a ESTRUTURA — pergunta ao lado
// do valor, parte vazia que se declara vazia —, nunca o texto.
// ---------------------------------------------------------------------------

const CASO_REVISAO = 'CASO-REVISAO-E2E'

/** Uma revisão com duas respostas na parte 1 e uma (por item) na parte 5. */
function partesComRespostas(): ParteDeTeste[] {
  const partes = partesVazias()
  partes[0].respondidas = [
    {
      ID: 'B1.01',
      item_id: null,
      enunciado: 'Primeira pergunta do compromisso?',
      respondida_como_nao_sei: false,
      valores: ['A escolha que eu fiz'],
    },
    {
      ID: 'B1.02',
      item_id: null,
      enunciado: 'Segunda pergunta do compromisso?',
      respondida_como_nao_sei: true,
      valores: [],
    },
  ]
  partes[4].respondidas = [
    {
      ID: 'B5.B03',
      item_id: 'D001',
      enunciado: 'Quanto falta pagar nesta dívida?',
      respondida_como_nao_sei: false,
      valores: ['R$ 1.234,56'],
    },
  ]
  return partes
}

/** Um cartão de parte da revisão, pelo rótulo que o servidor mandou. */
function parteDaRevisao(page: Page, rotulo: string) {
  return page.locator('details').filter({ hasText: rotulo })
}

test('AC-100: a revisão mostra pergunta e VALOR respondido, agrupados por parte', async ({
  page,
}) => {
  await interceptarBase(page, CASO_REVISAO)
  await interceptarRespostas(page, CASO_REVISAO, partesComRespostas())
  await abrirTela(page, CASO_REVISAO, 'respostas')

  // As cinco partes, sempre — é contrato da rota, não filtro da tela.
  await expect(page.locator('details')).toHaveCount(5)

  const primeira = parteDaRevisao(page, ROTULOS_DAS_PARTES[0])

  // **A asserção que carrega o requisito é o VALOR.** Uma lista só com os
  // enunciados passaria por uma tela que mostra as perguntas respondidas sem
  // dizer o que o aluno respondeu — que é exatamente o defeito relatado.
  await expect(primeira).toContainText('Primeira pergunta do compromisso?')
  await expect(primeira).toContainText('A escolha que eu fiz')

  // E nunca só o identificador: "B1.01" no lugar do texto pediria ao aluno
  // que aprendesse a nossa notação para reler a própria resposta.
  await expect(primeira).not.toContainText('B1.01')

  // "Não sei" é resposta de primeira classe (`RF-11`) e aparece como tal —
  // escondê-la faria o aluno procurar uma pergunta que ele já resolveu.
  await expect(primeira).toContainText('não sei')
})

test('AC-100: cada parte traz a sua contagem de respostas', async ({ page }) => {
  await interceptarBase(page, CASO_REVISAO)
  await interceptarRespostas(page, CASO_REVISAO, partesComRespostas())
  await abrirTela(page, CASO_REVISAO, 'respostas')

  await expect(parteDaRevisao(page, ROTULOS_DAS_PARTES[0])).toContainText(
    '2 respostas de 10 perguntas',
  )
  // Singular correto: "1 respostas" é o tipo de detalhe que faz a tela
  // parecer um rascunho para quem já desconfia do sistema.
  await expect(parteDaRevisao(page, ROTULOS_DAS_PARTES[4])).toContainText(
    '1 resposta de 10 perguntas',
  )
})

test('AC-101: a parte sem respostas DIZ que está vazia — não some da lista', async ({
  page,
}) => {
  await interceptarBase(page, CASO_REVISAO)
  await interceptarRespostas(page, CASO_REVISAO, partesComRespostas())
  await abrirTela(page, CASO_REVISAO, 'respostas')

  // A parte 2 não tem nenhuma resposta no payload. Ela continua na lista...
  const vazia = parteDaRevisao(page, ROTULOS_DAS_PARTES[1])
  await expect(vazia).toHaveCount(1)
  await expect(vazia).toContainText('0 respostas de 10 perguntas')

  // ...e diz por que está vazia. Uma lista em branco sugeriria erro de
  // carregamento; sumir da tela faria o aluno procurar onde a parte foi parar.
  await vazia.locator('summary').click()
  await expect(vazia).toContainText('ainda não respondeu nada desta parte')
})

test('AC-101: a revisão de um caso sem NENHUMA resposta ainda mostra as cinco partes', async ({
  page,
}) => {
  await interceptarBase(page, CASO_REVISAO)
  await interceptarRespostas(page, CASO_REVISAO, partesVazias())
  await abrirTela(page, CASO_REVISAO, 'respostas')

  await expect(page.locator('details')).toHaveCount(5)
  for (const rotulo of ROTULOS_DAS_PARTES) {
    await expect(parteDaRevisao(page, rotulo)).toHaveCount(1)
  }
})

test('AC-100: a lista é navegável por teclado', async ({ page }) => {
  await interceptarBase(page, CASO_REVISAO)
  await interceptarRespostas(page, CASO_REVISAO, partesComRespostas())
  await abrirTela(page, CASO_REVISAO, 'respostas')

  // A parte 2 nasce fechada (só a primeira COM respostas abre). Abri-la pelo
  // teclado é o que prova que a lista não depende de mouse — NFR de
  // acessibilidade, e a persona pode estar num leitor de tela.
  const vazia = parteDaRevisao(page, ROTULOS_DAS_PARTES[1])
  await vazia.locator('summary').focus()
  await page.keyboard.press('Enter')
  await expect(vazia).toHaveAttribute('open', '')
})

/**
 * `AC-102` — o defeito de produção que T-160 corrigiu.
 *
 * A rota `#pergunta/{ID}/{item_id}` existia desde `T-149` e `TelaPergunta`
 * **ignorava os dois parâmetros**: ela chamava sempre `GET
 * /caso/{id}/pergunta` (a PRÓXIMA pendente). Este teste falha contra o código
 * anterior porque o intercept de `/pergunta/B1.01` nunca seria acionado.
 */
const PERGUNTA_B101 = {
  pergunta: {
    CASO_ID: CASO_REVISAO,
    ID: 'B1.01',
    bloco: 1,
    tipo: 'TEXTO_CURTO',
    enunciado: 'Primeira pergunta do compromisso?',
    opcoes: [],
    escopo_repeticao: 'NENHUM',
    item_id: null,
    posicao: null,
    total_na_ficha: null,
    admite_nao_sei: true,
    valor_atual: 'A escolha que eu fiz',
    respondida_como_nao_sei: false,
    valores_marcados: [],
    aviso: null,
  },
  avanco_permitido: true,
  total_pendencias: 0,
}

/** A mesma pergunta, dentro da ficha da dívida `D001` — `AC-102`, `AC-105`. */
const PERGUNTA_B5B03 = {
  pergunta: {
    CASO_ID: CASO_REVISAO,
    ID: 'B5.B03',
    bloco: 5,
    tipo: 'TEXTO_CURTO',
    enunciado: 'Quanto falta pagar nesta dívida?',
    opcoes: [],
    escopo_repeticao: 'DIVIDA_ID',
    item_id: 'D001',
    posicao: 3,
    total_na_ficha: 12,
    admite_nao_sei: true,
    valor_atual: 'R$ 1.234,56',
    respondida_como_nao_sei: false,
    valores_marcados: [],
    aviso: null,
  },
  avanco_permitido: false,
  total_pendencias: 1,
}

test('AC-102: "Editar" abre a pergunta certa, com o valor anterior preenchido', async ({
  page,
}) => {
  await interceptarBase(page, CASO_REVISAO)
  await interceptarRespostas(page, CASO_REVISAO, partesComRespostas())

  // A pergunta ESPECÍFICA — note o `valor_atual` já preenchido: é o servidor
  // que o devolve, e é isso que faz corrigir ser editar em vez de redigitar.
  await page.route(`**/caso/${CASO_REVISAO}/pergunta/B1.01*`, async (rota) => {
    await rota.fulfill({ json: PERGUNTA_B101 })
  })

  // Se a tela ainda pedisse a PRÓXIMA pergunta, este intercept responderia —
  // e a asserção final falharia com outro enunciado na tela. É a trava que
  // impede o defeito de voltar sem ninguém notar.
  await page.route(`**/caso/${CASO_REVISAO}/pergunta`, async (rota) => {
    await rota.fulfill({
      json: { pergunta: null, coleta_completa: true, CASO_ID: CASO_REVISAO },
    })
  })

  await abrirTela(page, CASO_REVISAO, 'respostas')
  await parteDaRevisao(page, ROTULOS_DAS_PARTES[0])
    .getByRole('button', { name: 'Editar' })
    .first()
    .click()

  await expect(page).toHaveURL(/#respostas\/B1\.01/)
  await expect(page.getByLabel('Primeira pergunta do compromisso?')).toHaveValue(
    'A escolha que eu fiz',
  )
})

test('AC-102: a edição de uma ficha repetível leva o item na rota', async ({ page }) => {
  await interceptarBase(page, CASO_REVISAO)
  await interceptarRespostas(page, CASO_REVISAO, partesComRespostas())
  await page.route(`**/caso/${CASO_REVISAO}/pergunta/B5.B03*`, async (rota) => {
    await rota.fulfill({ json: PERGUNTA_B5B03 })
  })

  await abrirTela(page, CASO_REVISAO, 'respostas')
  const parte = parteDaRevisao(page, ROTULOS_DAS_PARTES[4])
  await parte.locator('summary').click()
  await parte.getByRole('button', { name: 'Editar' }).click()

  // `D001` na rota não é detalhe: a mesma pergunta rende uma resposta por
  // dívida, e perder o item abriria a ficha errada com cara de certa.
  await expect(page).toHaveURL(/#respostas\/B5\.B03\/D001/)
})

/**
 * `AC-103`/`AC-104` — gravar a correção, e o que acontece quando o servidor
 * recusa. Os dois compartilham a montagem; o que muda é a resposta do `POST`.
 */
async function abrirCorrecaoDeB101(
  page: Page,
  registrarPost: () => Promise<void>,
): Promise<void> {
  await interceptarBase(page, CASO_REVISAO)
  await interceptarRespostas(page, CASO_REVISAO, partesComRespostas())
  await page.route(`**/caso/${CASO_REVISAO}/pergunta/B1.01*`, async (rota) => {
    await rota.fulfill({ json: PERGUNTA_B101 })
  })
  await registrarPost()
  await abrirTela(page, CASO_REVISAO, 'respostas/B1.01')
  await expect(page.getByLabel('Primeira pergunta do compromisso?')).toHaveValue(
    'A escolha que eu fiz',
  )
}

test('AC-103: gravada a correção, a revisão reabre com o valor NOVO', async ({
  page,
}) => {
  let corpoGravado = ''
  let jaCorrigiu = false

  await abrirCorrecaoDeB101(page, async () => {
    await page.route(`**/caso/${CASO_REVISAO}/resposta`, async (rota) => {
      corpoGravado = rota.request().postData() ?? ''
      jaCorrigiu = true
      await rota.fulfill({
        json: {
          ID_PERGUNTA: 'B1.01',
          aviso: null,
          avanco_permitido: true,
          total_pendencias: 0,
        },
      })
    })
    // A revisão relê o servidor depois da correção — e o servidor devolve o
    // valor novo, com a MESMA contagem de respostas: corrigir não é responder
    // de novo (`AC-103`, segundo pé).
    await page.route(`**/caso/${CASO_REVISAO}/respostas`, async (rota) => {
      const partes = partesComRespostas()
      if (jaCorrigiu) partes[0].respondidas[0].valores = ['O que eu escolhi depois']
      await rota.fulfill({ json: { CASO_ID: CASO_REVISAO, partes } })
    })
  })

  await page
    .getByLabel('Primeira pergunta do compromisso?')
    .fill('O que eu escolhi depois')
  await acaoPrincipal(page, 'Salvar a correção').click()

  // **A mesma rota de gravação de sempre** (`RF-69`): é `POST
  // /caso/{id}/resposta` com `ID_PERGUNTA` no corpo, não uma segunda via.
  // Um segundo caminho de escrita seria uma segunda regra de validação, e
  // `EC-01` deixaria de ser soberano.
  expect(corpoGravado).toContain('ID_PERGUNTA=B1.01')

  // Volta para a revisão, que é de onde o aluno veio — não para o meio da
  // coleta, que ele não pediu.
  await expect(page).toHaveURL(/#respostas/)
  const primeira = parteDaRevisao(page, ROTULOS_DAS_PARTES[0])
  await expect(primeira).toContainText('O que eu escolhi depois')
  await expect(primeira).not.toContainText('A escolha que eu fiz')

  // E o total de respondidas NÃO subiu: continuam duas.
  await expect(primeira).toContainText('2 respostas de 10 perguntas')
})

test('AC-104: correção recusada mostra a mensagem do servidor e não apaga o valor', async ({
  page,
}) => {
  await abrirCorrecaoDeB101(page, async () => {
    await page.route(`**/caso/${CASO_REVISAO}/resposta`, async (rota) => {
      // `EC-01`: a fronteira de conversão recusou, e nomeou o motivo. O
      // cliente NUNCA inventa esta mensagem — ele mostra a do servidor.
      await rota.fulfill({
        status: 400,
        json: { erro: 'O valor informado não foi reconhecido como dinheiro.' },
      })
    })
  })

  const campo = page.getByLabel('Primeira pergunta do compromisso?')
  await campo.fill('mil reais')
  await acaoPrincipal(page, 'Salvar a correção').click()

  // A mensagem DO SERVIDOR, anunciada como alerta.
  await expect(page.locator('[role="alert"]')).toContainText(
    'não foi reconhecido como dinheiro',
  )

  // **E o aluno continua na pergunta, com o que digitou.** Recarregar aqui
  // apagaria a digitação dele por causa de um erro que foi do valor novo. O
  // valor ANTERIOR segue gravado no servidor — ele recusou a escrita inteira,
  // não gravou pela metade —, e a revisão o prova.
  await expect(page).toHaveURL(/#respostas\/B1\.01/)
  await expect(campo).toHaveValue('mil reais')

  await abrirTela(page, CASO_REVISAO, 'respostas')
  await expect(parteDaRevisao(page, ROTULOS_DAS_PARTES[0])).toContainText(
    'A escolha que eu fiz',
  )
})

/**
 * `AC-105` — o caminho para a pergunta anterior, durante a coleta.
 *
 * **Por que a fonte é `/respostas`.** O cliente não conhece o conjunto de
 * perguntas exibíveis (`RF-45`), então "qual vem antes" não pode ser deduzido
 * aqui. `/respostas` já devolve, na ordem dos registros, exatamente as
 * perguntas que o aluno RESPONDEU — que é o conjunto que o critério pede. Um
 * histórico de navegação no cliente foi recusado: ele diz por onde o aluno
 * passou nesta sessão, e `RF-10` promete retomada em outro aparelho, onde ele
 * estaria vazio.
 */
const PROXIMA_PENDENTE = {
  pergunta: {
    CASO_ID: CASO_REVISAO,
    ID: 'B1.03',
    bloco: 1,
    tipo: 'TEXTO_CURTO',
    enunciado: 'Terceira pergunta do compromisso?',
    opcoes: [],
    escopo_repeticao: 'NENHUM',
    item_id: null,
    posicao: null,
    total_na_ficha: null,
    admite_nao_sei: true,
    valor_atual: null,
    respondida_como_nao_sei: false,
    valores_marcados: [],
    aviso: null,
  },
  avanco_permitido: false,
  total_pendencias: 2,
}

test('AC-105: na coleta há caminho para a pergunta anterior já respondida', async ({
  page,
}) => {
  await interceptarBase(page, CASO_REVISAO)
  await interceptarRespostas(page, CASO_REVISAO, partesComRespostas())
  await page.route(`**/caso/${CASO_REVISAO}/pergunta`, async (rota) => {
    await rota.fulfill({ json: PROXIMA_PENDENTE })
  })
  await page.route(`**/caso/${CASO_REVISAO}/pergunta/B5.B03*`, async (rota) => {
    await rota.fulfill({ json: PERGUNTA_B5B03 })
  })

  await abrirTela(page, CASO_REVISAO, 'pergunta')
  await expect(page.getByLabel('Terceira pergunta do compromisso?')).toBeVisible()

  // A anterior é a ÚLTIMA respondida na ordem do servidor — a da parte 5, com
  // o seu item. Ela é o destino porque a pergunta na tela ainda não foi
  // respondida.
  const anterior = acaoPrincipal(page, /Pergunta anterior/)
  await expect(anterior).toBeVisible()
  await anterior.click()
  await expect(page).toHaveURL(/#pergunta\/B5\.B03\/D001/)
})

test('AC-105: na PRIMEIRA pergunta não há "anterior" oferecido', async ({ page }) => {
  await interceptarBase(page, CASO_REVISAO)

  // Uma única resposta no caso, e é justamente a que está na tela: não há
  // nenhuma antes dela.
  const partes = partesVazias()
  partes[0].respondidas = [
    {
      ID: 'B1.03',
      item_id: null,
      enunciado: 'Terceira pergunta do compromisso?',
      respondida_como_nao_sei: false,
      valores: ['Algo'],
    },
  ]
  await interceptarRespostas(page, CASO_REVISAO, partes)
  await page.route(`**/caso/${CASO_REVISAO}/pergunta`, async (rota) => {
    await rota.fulfill({ json: PROXIMA_PENDENTE })
  })

  await abrirTela(page, CASO_REVISAO, 'pergunta')
  await expect(page.getByLabel('Terceira pergunta do compromisso?')).toBeVisible()

  // **Ausente do DOM, não desabilitado.** Um botão apagado ainda promete um
  // caminho que não existe, e a persona já chega desconfiando do sistema.
  await expect(acaoPrincipal(page, /Pergunta anterior/)).toHaveCount(0)
})

test('AC-105: num caso sem nenhuma resposta, a coleta não oferece "anterior"', async ({
  page,
}) => {
  await interceptarBase(page, CASO_REVISAO)
  await page.route(`**/caso/${CASO_REVISAO}/pergunta`, async (rota) => {
    await rota.fulfill({ json: PROXIMA_PENDENTE })
  })

  await abrirTela(page, CASO_REVISAO, 'pergunta')
  await expect(page.getByLabel('Terceira pergunta do compromisso?')).toBeVisible()
  await expect(acaoPrincipal(page, /Pergunta anterior/)).toHaveCount(0)
})

/**
 * `AC-106` — as duas geometrias, medidas no navegador.
 *
 * O critério tem dois pés opostos, e um teste que só verificasse o desktop
 * deixaria passar exatamente a regressão que mais custa: mudar a tela pequena,
 * que foi a validada com stakeholders. Por isso a asserção se divide por
 * `infoDoTeste.project.name`, como o teste de `AC-95` já faz.
 */
test('AC-106: trilha lateral no desktop, coluna única a 360px', async ({
  page,
}, infoDoTeste) => {
  await interceptarBase(page, CASO_JORNADA)
  await abrirTela(page, CASO_JORNADA, 'inicio')

  await expect(trilha(page)).toBeVisible()
  await expect(page.locator('.cartao-proximo')).toBeVisible()

  const caixas = await page.evaluate(() => {
    const trilhaEl = document.querySelector('[aria-label="Sua jornada no PIQ"]')
    const conteudoEl = document.querySelector('.cartao-proximo')
    if (!trilhaEl || !conteudoEl) return null
    const t = trilhaEl.getBoundingClientRect()
    const c = conteudoEl.getBoundingClientRect()
    return {
      trilha: { topo: t.top, esquerda: t.left, direita: t.right },
      conteudo: { topo: c.top, esquerda: c.left },
      rolagem: document.documentElement.scrollWidth,
      janela: window.innerWidth,
    }
  })
  expect(caixas).not.toBeNull()
  if (!caixas) return

  if (infoDoTeste.project.name === 'mobile-360') {
    // **Idêntico ao validado**: coluna única, trilha ACIMA do conteúdo (mesma
    // borda esquerda, topo menor) e nada vazando para os lados.
    expect(caixas.trilha.topo).toBeLessThan(caixas.conteudo.topo)
    expect(Math.abs(caixas.trilha.esquerda - caixas.conteudo.esquerda)).toBeLessThan(2)
    expect(caixas.rolagem).toBeLessThanOrEqual(caixas.janela)
  } else {
    // ≥1024px: a trilha é COLUNA LATERAL — ela termina antes de o conteúdo
    // começar, e os dois dividem a mesma faixa vertical.
    expect(caixas.trilha.direita).toBeLessThanOrEqual(caixas.conteudo.esquerda + 1)
    expect(caixas.conteudo.esquerda).toBeGreaterThan(caixas.trilha.esquerda)
  }
})

test('AC-106: no desktop o conteúdo ganha largura, sem virar linha infinita', async ({
  page,
}, infoDoTeste) => {
  test.skip(infoDoTeste.project.name === 'mobile-360', 'este é o pé desktop de AC-106')

  await interceptarBase(page, CASO_JORNADA)
  await abrirTela(page, CASO_JORNADA, 'inicio')

  const largura = await page.evaluate(() => {
    const corpo = document.querySelector('.corpo')
    return corpo ? corpo.getBoundingClientRect().width : 0
  })

  // Maior que os 560px do protótipo — era esse o desperdício relatado...
  expect(largura).toBeGreaterThan(560)
  // ...e ainda assim limitado. Linha de texto longa cansa, e "adaptar à
  // janela" não autoriza ocupar um monitor inteiro com uma frase.
  expect(largura).toBeLessThanOrEqual(1200)
})
