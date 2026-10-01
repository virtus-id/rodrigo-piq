/**
 * Depois de registrar o consentimento, o Início nunca mostra a etapa velha.
 *
 * Relato do produto (2026-10-01): ao aceitar o consentimento, o Início
 * aparecia por um instante ainda oferecendo "Registrar o seu consentimento" e
 * só depois mudava. Causa: a navegação desenhava o Início com o `/inicio` em
 * memória e só então buscava o novo. O teste atrasa o `/inicio` posterior ao
 * aceite para tornar a janela visível.
 */
import { expect, test } from '@playwright/test'

import { abrirTela, inicioEmColeta, interceptarBase } from './apoio/navegacao'

const CASO = 'CASO-CONSENT-E2E'

test('após o aceite, o Início não oferece de novo o consentimento', async ({ page }) => {
  const antes = {
    ...inicioEmColeta(CASO),
    estado: 'CADASTRADO',
    proxima_etapa: { destino: 'consentimento' as const, ID_PERGUNTA: null, item_id: null },
    progresso: { respondidas: 3, total: 195 },
  }
  const depois = { ...inicioEmColeta(CASO), progresso: { respondidas: 3, total: 195 } }
  let aceito = false

  await interceptarBase(page, CASO, { inicio: antes })
  await page.route(`**/caso/${CASO}/inicio`, async (rota) => {
    if (!aceito) return rota.fulfill({ json: antes })
    await new Promise((r) => setTimeout(r, 1500))
    return rota.fulfill({ json: depois })
  })
  await page.route(`**/api/caso/${CASO}/consentimento`, (rota) =>
    rota.fulfill({
      json: { CASO_ID: CASO, QUESTIONARIO_VERSION: '1.0.3', titulo: 'Consentimento', corpo: 'Texto.' },
    }),
  )
  await page.route(`**/caso/${CASO}/consentimento`, (rota) => {
    if (rota.request().method() !== 'POST') return rota.fallback()
    aceito = true
    return rota.fulfill({ json: { estado: 'COLETA_INICIAL' } })
  })

  await abrirTela(page, CASO, 'consentimento')
  await page.getByLabel('Li e concordo').check()
  await page.getByRole('button', { name: 'Concordar e começar' }).click()

  // Dentro da janela do `/inicio` atrasado: a etapa velha não pode aparecer.
  // Leitura instantânea: `expect(...).toHaveCount(0)` repetiria até o texto
  // sumir e esconderia justamente o instante que este teste existe para ver.
  await page.waitForTimeout(600)
  expect(await page.getByText('Registrar o seu consentimento').count()).toBe(0)

  // E ao fim o Início chega com a etapa nova.
  await expect(page).toHaveURL(/#inicio/)
  await expect(page.getByText('Registrar o seu consentimento')).toHaveCount(0)
})
