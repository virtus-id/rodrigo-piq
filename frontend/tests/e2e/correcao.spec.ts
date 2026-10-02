/**
 * "Pedir correção" no Início do aluno — `RF-113`, `AC-175` (T-333).
 *
 * O servidor devolve a mensagem do revisor e os dados a conferir; a tela
 * mostra o aviso fixo, leva cada dado à correção (`RF-69`) e oferece o
 * reenvio como a próxima etapa. Rede interceptada (`apoio/navegacao.ts`).
 */
import { expect, test } from '@playwright/test'

import { abrirTela, acaoPrincipal, interceptarBase } from './apoio/navegacao'

const CASO = 'CASO-CORRECAO-E2E'

test('AC-175: aviso com a mensagem, dados a conferir e "Enviar para nova conferência"', async ({
  page,
}) => {
  await interceptarBase(page, CASO, {
    inicio: {
      mensagem: 'Seu plano voltou para você conferir.',
      proxima_etapa: { destino: 'calculando', ID_PERGUNTA: null, item_id: null },
      correcao_pedida: {
        mensagem: 'Informe a taxa do cheque especial',
        dados_a_conferir: [
          {
            nome: 'Cheque especial — CAIXA ECONOMICA FEDERAL',
            enunciado: 'Você sabe qual é a taxa de juros desta operação?',
            ID_PERGUNTA: 'B5.D01',
            item_id: 'D001',
          },
        ],
      },
    },
  })

  // A correção abre a pergunta — fora do escopo daqui, só não vai ao proxy.
  await page.route(`**/caso/${CASO}/pergunta/**`, (r) => r.fulfill({ status: 404, json: {} }))

  await abrirTela(page, CASO, 'inicio')

  await expect(page.getByText('Seu plano voltou para você conferir.')).toBeVisible()
  await expect(page.getByText('Informe a taxa do cheque especial')).toBeVisible()
  await expect(page.getByText(/em revisão/)).toHaveCount(0)
  await expect(acaoPrincipal(page, 'Enviar para nova conferência')).toBeVisible()

  await page
    .getByRole('button', {
      name: 'Cheque especial — CAIXA ECONOMICA FEDERAL · Você sabe qual é a taxa de juros desta operação?',
    })
    .click()
  await expect
    .poll(() => page.evaluate(() => window.location.hash))
    .toContain('respostas/B5.D01/D001')
})
