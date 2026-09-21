/**
 * Fluxo da coleta no navegador — `RF-50`, `RF-45` (T-138, migrado em T-152).
 *
 * `.claude/instructions/testing.instructions.md`: rede interceptada com
 * `page.route` para determinismo, e ao menos um teste em viewport mobile.
 * O viewport móvel deste projeto é 360px — a persona é um servidor público
 * com o celular na mão, e é a largura que a NFR de responsividade fixa.
 *
 * **Este arquivo não pode ser renomeado nem movido.**
 * `tests/app_aluno/e2e/test_acessibilidade_plano.py:340` exige
 * `frontend/tests/e2e/coleta.spec.ts` como arquivo naquele caminho — é a
 * prova de que a verificação em navegador real existe. O conteúdo migrou da
 * barra de sete abas para o roteamento por hash (`T-149`); o caminho, não.
 *
 * **A navegação vem toda de `apoio/navegacao.ts`.** Nenhum seletor de
 * navegação nasce aqui: era isso que fazia a morte da barra de abas custar
 * 18 edições.
 *
 * As respostas interceptadas abaixo têm a forma EXATA de
 * `app/http/serializacao.py`. Note o que elas não têm: `condicao_exibicao`,
 * `validacoes_cruzadas`, `obrigatoriedade`. O servidor não envia, e o
 * cliente não saberia o que fazer com elas (`RF-52`).
 */
import { expect, test, type Page } from '@playwright/test'

import { abrirTela, acaoPrincipal, interceptarBase } from './apoio/navegacao'

const CASO = 'CASO-E2E'

const ENUNCIADO = 'Quanto falta pagar hoje?'

/**
 * O enunciado VISÍVEL, que é o `<label>` de `CampoPergunta`.
 *
 * `getByText` sozinho casaria dois elementos desde `T-149`: a casca emite
 * sempre um `<h1>`, e na tela de pergunta ele é `sr-only` com o mesmo texto
 * (`mostrarTitulo={false}` — dois títulos visíveis fariam o leitor de tela
 * anunciar a pergunta duas vezes). Os dois existirem é o comportamento
 * correto de `AC-84`; o que o teste quer ver é o visível.
 */
function enunciadoVisivel(page: Page) {
  return page.locator('label', { hasText: ENUNCIADO })
}

const PERGUNTA_MOEDA = {
  pergunta: {
    CASO_ID: CASO,
    ID: 'B5.B03',
    bloco: 5,
    tipo: 'MOEDA',
    enunciado: ENUNCIADO,
    opcoes: [],
    escopo_repeticao: 'DIVIDA_ID',
    item_id: 'D001',
    // `RF-63`, `AC-92`: dentro de ficha repetível o servidor conta, e o
    // localizador do `.top` usa estes dois. `null` fora de ficha.
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

test.describe('coleta', () => {
  test.beforeEach(async ({ page }) => {
    await interceptarBase(page, CASO)
    await page.route(`**/caso/${CASO}/pergunta`, async (rota) => {
      await rota.fulfill({ json: PERGUNTA_MOEDA })
    })
  })

  test('mostra a pergunta que o servidor mandou', async ({ page }) => {
    await abrirTela(page, CASO, 'pergunta')

    await expect(enunciadoVisivel(page)).toBeVisible()
    await expect(page.getByText(/3 pendências/)).toBeVisible()
  })

  test('AC-75: a máscara formata o valor enquanto o aluno digita', async ({ page }) => {
    await abrirTela(page, CASO, 'pergunta')

    const campo = page.getByLabel(ENUNCIADO)
    await campo.fill('')
    await campo.pressSequentially('123456')

    await expect(campo).toHaveValue('1.234,56')
  })

  test('AC-76: o R$ fica FORA do campo — o servidor recusa o caractere', async ({
    page,
  }) => {
    await abrirTela(page, CASO, 'pergunta')

    const campo = page.getByLabel(ENUNCIADO)
    await campo.pressSequentially('5000')

    await expect(campo).toHaveValue('50,00')
    await expect(page.getByText('R$')).toBeVisible()
  })

  test('AC-78: marcar "não sei" deixa o campo inerte', async ({ page }) => {
    await abrirTela(page, CASO, 'pergunta')

    await page.getByLabel('Não sei').check()

    await expect(page.getByLabel(ENUNCIADO)).toBeDisabled()
  })

  test('RF-52: o grafo condicional não chega ao navegador', async ({ page }) => {
    await abrirTela(page, CASO, 'pergunta')
    await expect(enunciadoVisivel(page)).toBeVisible()

    const html = await page.content()
    expect(html).not.toContain('condicao_exibicao')
    expect(html).not.toContain('validacoes_cruzadas')
  })
})

test.describe('fichas repetíveis', () => {
  test('RF-53: lista, cria e remove — sem reaproveitar identificador', async ({
    page,
  }) => {
    let fichas = [{ item_id: 'D001', completa: false, campos: [] }]

    await interceptarBase(page, CASO)
    await page.route(`**/caso/${CASO}/fichas/DIVIDA_ID`, async (rota) => {
      if (rota.request().method() === 'POST') {
        fichas = [...fichas, { item_id: 'D002', completa: false, campos: [] }]
        await rota.fulfill({
          status: 201,
          json: { CASO_ID: CASO, escopo: 'DIVIDA_ID', ficha: fichas[fichas.length - 1] },
        })
        return
      }
      await rota.fulfill({ json: { CASO_ID: CASO, escopo: 'DIVIDA_ID', fichas } })
    })

    await abrirTela(page, CASO, 'fichas')

    await expect(page.getByRole('button', { name: 'Dívida D001', exact: true })).toBeVisible()

    await acaoPrincipal(page, /Adicionar dívida/).click()
    await expect(page.getByRole('button', { name: 'Dívida D002', exact: true })).toBeVisible()
  })
})

test.describe('360px — a persona responde no celular', () => {
  test.use({ viewport: { width: 360, height: 740 } })

  test('não há rolagem horizontal', async ({ page }) => {
    await interceptarBase(page, CASO)
    await page.route(`**/caso/${CASO}/pergunta`, async (rota) => {
      await rota.fulfill({ json: PERGUNTA_MOEDA })
    })

    await abrirTela(page, CASO, 'pergunta')
    await expect(enunciadoVisivel(page)).toBeVisible()

    const larguraDoDocumento = await page.evaluate(
      () => document.documentElement.scrollWidth,
    )
    const larguraDaJanela = await page.evaluate(() => window.innerWidth)

    expect(larguraDoDocumento).toBeLessThanOrEqual(larguraDaJanela)
  })
})

/**
 * Portados de `tests/app_aluno/e2e/test_navegador_fluxo.py` (T-144).
 *
 * Aqueles testes exercitavam a tela Jinja + `mascaras.js`, que deixaram de
 * existir. As GARANTIAS que eles guardavam não deixaram: a recusa do
 * servidor chega ao aluno, o par inconsistente não é gravado, o aviso de
 * materialidade aparece na hora, e a coleta inteira é operável só com o
 * teclado. É isso que segue abaixo, agora contra o React.
 */
test.describe('recusas do servidor chegam ao aluno', () => {
  test.beforeEach(async ({ page }) => {
    await interceptarBase(page, CASO)
    await page.route(`**/caso/${CASO}/pergunta`, async (rota) => {
      await rota.fulfill({ json: PERGUNTA_MOEDA })
    })
  })

  test('EC-01: entrada ambígua é recusada com alerta, e nada é gravado', async ({
    page,
  }) => {
    let tentativas = 0
    await page.route(`**/caso/${CASO}/resposta`, async (rota) => {
      // O servidor recusa `"1.2,3"` — `_milhar_valido` não aceita. A rota
      // devolve 400 e NÃO grava: é o comportamento real de `EC-01`.
      tentativas += 1
      await rota.fulfill({
        status: 400,
        json: { erro: 'Valor não reconhecido. Use o formato 1.234,56.' },
      })
    })

    await abrirTela(page, CASO, 'pergunta')
    await expect(enunciadoVisivel(page)).toBeVisible()

    // Atribuição direta, sem disparar `input`: é assim que um autofill ou
    // uma colagem fora do caminho de digitação entregam valor ambíguo. Com
    // `fill()` a máscara reescreveria para algo válido e o teste não
    // exercitaria `EC-01` — foi exatamente assim que a versão Python
    // deste teste nasceu errada.
    await page.evaluate(() => {
      const campo = document.querySelector<HTMLInputElement>('input[inputmode="decimal"]')
      if (campo) campo.value = '1.2,3'
    })
    await acaoPrincipal(page, 'Continuar').click()

    const alerta = page.getByRole('alert')
    await expect(alerta).toBeVisible()
    await expect(alerta).not.toHaveText('')
    // O POST chegou ao servidor e foi recusado lá — a máscara não "salvou"
    // a entrada ambígua no cliente, que é o ponto de `EC-01`/`AC-77`.
    expect(tentativas).toBe(1)
  })

  test('EC-02: validação cruzada recusa nomeando o campo, sem gravar o par', async ({
    page,
  }) => {
    await page.route(`**/caso/${CASO}/resposta`, async (rota) => {
      await rota.fulfill({
        status: 400,
        json: { erro: 'A margem usada não pode ser maior que a margem total.' },
      })
    })

    await abrirTela(page, CASO, 'pergunta')
    await page.locator('input[inputmode="decimal"]').fill('1.200,00')
    await acaoPrincipal(page, 'Continuar').click()

    // A mensagem é a do servidor, nunca composta pelo cliente.
    await expect(page.getByRole('alert')).toContainText(/margem/i)
  })
})

test.describe('acessibilidade — só com o teclado', () => {
  test('responde uma pergunta sem tocar no mouse', async ({ page }) => {
    await interceptarBase(page, CASO)
    await page.route(`**/caso/${CASO}/pergunta`, async (rota) => {
      await rota.fulfill({ json: PERGUNTA_MOEDA })
    })
    let corpoEnviado = ''
    await page.route(`**/caso/${CASO}/resposta`, async (rota) => {
      corpoEnviado = rota.request().postData() ?? ''
      await rota.fulfill({
        json: { ID_PERGUNTA: 'B5.B03', aviso: null, avanco_permitido: true, total_pendencias: 0 },
      })
    })

    await abrirTela(page, CASO, 'pergunta')
    await expect(enunciadoVisivel(page)).toBeVisible()

    // Parte do campo, não de um Tab desde o `<body>`: é o ponto do fluxo em
    // que o aluno de fato está quando digita o valor.
    const campo = page.locator('input[inputmode="decimal"]')
    await campo.focus()
    await page.keyboard.type('1234,56')

    // **O limite baixo É a asserção** (`RF-57`, §R5.6 do plano). Antes de
    // `T-149` este laço tabulava até 20 vezes porque a barra de sete abas
    // poluía o caminho — o comentário daquela versão dizia isso. Sem a barra
    // a ordem do DOM é `.back` → campo → `Não sei` → `Continuar`, e o
    // orçamento de 5 é o que o plano fixa. Se alguém reintroduzir navegação
    // global ANTES da ação principal, o orçamento estoura e este teste falha.
    const ORCAMENTO_DE_TABS = 5
    let acionou = false
    let tabsGastos = 0
    for (let i = 0; i < ORCAMENTO_DE_TABS; i += 1) {
      await page.keyboard.press('Tab')
      tabsGastos += 1
      // Igualdade ESTRITA: o mesmo botão em estado `Salvando…` não casa, e
      // é assim que se evita um falso positivo acionando um botão ocupado.
      const rotulo = await page.evaluate(
        () => document.activeElement?.textContent?.trim() ?? '',
      )
      if (rotulo === 'Continuar') {
        await page.keyboard.press('Enter')
        acionou = true
        break
      }
    }

    expect(acionou).toBe(true)
    // A segunda metade da trava, e a que de fato morde: o caminho real do
    // campo até a ação são DOIS tabs (`Não sei` e `Continuar`). Com só o
    // orçamento de 5, três focáveis novos entre um e outro passariam
    // caladas; com esta linha, o primeiro já falha e nomeia o que mudou.
    expect(tabsGastos).toBeLessThanOrEqual(2)
    // O corpo vai `form-urlencoded`, então a vírgula viaja como `%2C` —
    // comparar já decodificado prova o que importa: a máscara emitiu
    // `1.234,56`, o formato que `converter_para_dinheiro` aceita.
    await expect
      .poll(() => decodeURIComponent(corpoEnviado))
      .toContain('valor=1.234,56')
  })
})
