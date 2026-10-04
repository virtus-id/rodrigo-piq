/**
 * A tela do plano no navegador — `AC-14`, `AC-16`, `AC-25`, `AC-70`,
 * `OQ-09` (T-145, migrado em T-152).
 *
 * Esta suíte nasceu quando `GET /caso/{id}/plano` (HTML) foi removida e a
 * tela passou a ser inteiramente React. O que aquela rota provava do lado
 * do servidor — título canônico, carimbo de versão, estado do caso quando
 * não há plano — continua provado em `tests/app_aluno/`; o que faltava, e
 * é o que está aqui, é a prova de que o componente de fato coloca isso na
 * tela.
 *
 * **A navegação vem de `apoio/navegacao.ts`.** Antes de `T-152` cada teste
 * clicava no botão "Plano" da barra de sete abas; agora a tela é alcançada
 * pelo hash `#plano`, e trocar isso de novo é uma edição em um arquivo.
 *
 * Rede interceptada com `page.route` (`.claude/instructions/
 * testing.instructions.md`), com payloads na forma EXATA de
 * `app/http/serializacao_plano.py::serializar_plano`.
 */
import { expect, test } from '@playwright/test'

import { abrirTela, interceptarBase } from './apoio/navegacao'

const CASO = 'CASO-PLANO-E2E'

// Plano amigável (2026-10-03): título e corpo vigentes de
// `textos-canonicos.yaml` — já não é a transcrição literal de `Q-03`.
const TITULO_Q03 = 'Seu plano inteligente de quitação de dívidas'
const CORPO_Q03 =
  'Montamos este plano a partir do que você nos contou. Ele mostra, mês a mês, quanto pagar e em qual dívida. Se algo importante mudar — sua renda, uma dívida nova, um dinheiro extra — o plano é refeito para continuar certo para você.'

const PLANO_LIBERADO = {
  CASO_ID: CASO,
  estado: 'PLANO_LIBERADO',
  plano: {
    titulo: TITULO_Q03,
    corpo: CORPO_Q03,
    ordem: [
      {
        posicao: 1,
        indice: 1,
        total: 2,
        DIVIDA_ID: 'D001',
        nome: 'Cheque especial — CAIXA ECONOMICA FEDERAL',
        explicacao: 'Maior custo efetivo entre as dívidas elegíveis.',
        mes_de_quitacao: 9,
        valores_de_apoio: [{ rotulo: 'SALDO_DEVEDOR_ATUAL', valor: '5000.00' }],
      },
      {
        posicao: 2,
        indice: 2,
        total: 2,
        DIVIDA_ID: 'D002',
        nome: 'Empréstimo consignado — BANCO DO BRASIL',
        explicacao: 'Segue a primeira na ordem projetada.',
        mes_de_quitacao: null,
        valores_de_apoio: [],
      },
    ],
    PRAZO_TOTAL: '18',
    PRAZO_TOTAL_INT: 18,
    CUSTO_FUTURO_TOTAL: '1200.00',
    valor_mensal_destinado: 'R$ 512,34',
    ENGINE_VERSION: '1.0.1',
    PARAMETROS_VERSION: '1.0.1',
    metodo: 'Avalanche',
    cenario: 'Ordem de quitação publicada',
    acoes: [],
    pendencias: null,
    MODO_ESTABILIZACAO: false,
    RESULTADO_CAIXA_OBSERVADO: '7700.00',
    reserva_mobilizavel: { pendente_de_decisao: false, valor: '3000.00' },
  },
}

/**
 * O `/inicio` deste caso — plano já liberado e conferido.
 *
 * ⚠️ Vai em TODO teste desta suíte, inclusive nos que nunca olham o Início:
 * sem o intercept, o proxy do Vite tenta o FastAPI que não está no ar e o
 * teste trava até o timeout (§R5.6 do plano).
 */
const INICIO_COM_PLANO = {
  estado: 'PLANO_LIBERADO',
  fase: 'acompanhamento' as const,
  mensagem: 'Seu plano está liberado.',
  proxima_etapa: { destino: 'acoes' as const, ID_PERGUNTA: null, item_id: null },
  plano_liberado: true,
  versao_do_plano: 1,
}

async function abrirPlano(page: import('@playwright/test').Page) {
  await abrirTela(page, CASO, 'plano')
}

test.describe('plano liberado', () => {
  test.beforeEach(async ({ page }) => {
    await interceptarBase(page, CASO, { inicio: INICIO_COM_PLANO })
    await page.route(`**/caso/${CASO}/api/plano`, async (rota) => {
      await rota.fulfill({ json: PLANO_LIBERADO })
    })
  })

  test('AC-14: o título e o corpo canônicos aparecem sem reescrita', async ({ page }) => {
    await abrirPlano(page)

    // Igualdade exata do que está na tela: um resumo, uma reticência ou uma
    // troca de "projetada" por "definitiva" falhariam aqui.
    await expect(page.getByRole('heading', { name: TITULO_Q03 })).toBeVisible()
    await expect(page.getByText(CORPO_Q03, { exact: true })).toBeVisible()
  })

  test('AC-15: "inteligente" está na tela e os qualificadores proibidos não', async ({
    page,
  }) => {
    await abrirPlano(page)
    await expect(page.getByRole('heading', { name: TITULO_Q03 })).toBeVisible()

    const textoDaTela = (await page.locator('body').innerText()).toLowerCase()
    expect(textoDaTela).toContain('inteligente')
    for (const proibida of ['definitiva', 'fixa']) {
      expect(textoDaTela).not.toContain(proibida)
    }
  })

  test('AC-16: o carimbo de versão aparece — sem ele a tela não diz de qual cálculo veio', async ({
    page,
  }) => {
    await abrirPlano(page)
    await expect(page.getByText(/versão do cálculo 1\.0\.1/)).toBeVisible()
    await expect(page.getByText(/parâmetros 1\.0\.1/)).toBeVisible()
  })

  test('AC-109: o resumo do plano vem antes da ordem de quitação', async ({ page }) => {
    await abrirPlano(page)

    // **Por que a ordem importa.** Prazo e custo ficavam DEPOIS da ordem de
    // quitação, num cartão igual a todos os outros. Mas é esta a resposta que
    // o aluno abriu a tela para ver — quanto tempo, e quanto custa. A ordem é
    // o detalhe que sustenta a resposta, não a resposta.
    const resumo = page.locator('.cartao-destaque')
    await expect(resumo).toBeVisible()

    const primeiraPosicao = page.getByText(
      PLANO_LIBERADO.plano.ordem[0].explicacao,
    )
    await expect(primeiraPosicao).toBeVisible()

    const caixaResumo = await resumo.boundingBox()
    const caixaOrdem = await primeiraPosicao.boundingBox()
    expect(caixaResumo).not.toBeNull()
    expect(caixaOrdem).not.toBeNull()
    expect(caixaResumo!.y).toBeLessThan(caixaOrdem!.y)

    // E o cartão "Por mês" que repetia prazo e custo no pé da tela saiu em
    // T-167: dois lugares mostrando o mesmo número com formatações diferentes
    // foi o defeito que a Rodada 6 já removeu do Início.
    await expect(page.getByText('Por mês')).toHaveCount(0)

    // Os dois valores do resumo estão dentro do cartão de destaque — não
    // sobrou uma segunda cópia deles em outro ponto da tela.
    await expect(resumo).toContainText(PLANO_LIBERADO.plano.PRAZO_TOTAL)
    await expect(resumo).toContainText(PLANO_LIBERADO.plano.CUSTO_FUTURO_TOTAL)
  })

  test('AC-17: cada posição traz sua justificativa, nunca só o identificador', async ({
    page,
  }) => {
    await abrirPlano(page)

    for (const posicao of PLANO_LIBERADO.plano.ordem) {
      // `T-326` (`RF-111`, `AC-174`): a dívida por "tipo — credor"; o
      // código não aparece ao aluno.
      await expect(page.getByText(posicao.nome, { exact: true })).toBeVisible()
      await expect(page.getByText(posicao.DIVIDA_ID, { exact: true })).toHaveCount(0)
      // `T-305`: a explicação ao aluno — o payload dele não traz mais a
      // justificativa técnica.
      await expect(page.getByText(posicao.explicacao)).toBeVisible()
    }
  })

  test('T-305: mesmo que o payload traga o texto técnico, a tela não o mostra', async ({
    page,
  }) => {
    // O servidor deixou de enviar `JUSTIFICATIVA_POSICAO` ao aluno (`T-305`);
    // a tela também não a usa mais como fallback. O aluno não deve precisar
    // ler "critério: maior BENEFICIO_MARGINAL_AMORTIZACAO … (O-01)".
    const tecnica = 'critério: maior BENEFICIO_MARGINAL_AMORTIZACAO (O-01)'
    await page.route(`**/caso/${CASO}/api/plano`, async (rota) => {
      await rota.fulfill({
        json: {
          ...PLANO_LIBERADO,
          plano: {
            ...PLANO_LIBERADO.plano,
            ordem: PLANO_LIBERADO.plano.ordem.map((posicao) => ({
              ...posicao,
              JUSTIFICATIVA_POSICAO: tecnica,
            })),
          },
        },
      })
    })

    await abrirPlano(page)

    await expect(page.getByText(PLANO_LIBERADO.plano.ordem[0].explicacao)).toBeVisible()
    await expect(page.getByText(tecnica)).toHaveCount(0)
  })

  test('T-304: mês previsto de quitação por dívida e valor mensal destinado', async ({
    page,
  }) => {
    await abrirPlano(page)

    // Revisão de design (2026-10-03): o mês de quitação é o quadro "Termina
    // no" do cartão de cada dívida, à vista.
    const cartao = (nome: string) => page.locator('li.cartao').filter({ hasText: nome })
    const [primeira, segunda] = PLANO_LIBERADO.plano.ordem
    await expect(cartao(primeira.nome).getByText('Mês 9', { exact: true })).toBeVisible()
    await expect(cartao(segunda.nome).getByText('não disponível', { exact: true })).toBeVisible()
    await expect(page.locator('.cartao-destaque')).toContainText('R$ 512,34')
  })

  test('OQ-09: o PDF é alcançável pela tela, apontando para a rota real', async ({
    page,
  }) => {
    await abrirPlano(page)

    // O link tem que existir NA TELA: enquanto o PDF só era alcançável
    // digitando a URL, a metade "documento" de `OQ-09` não existia de fato
    // para o aluno.
    const link = page.getByRole('link', { name: 'Baixar em PDF' })
    await expect(link).toBeVisible()
    await expect(link).toHaveAttribute('href', `/caso/${CASO}/plano/pdf`)
  })
})

test.describe('sem plano liberado', () => {
  test('AC-25: mostra o ESTADO do caso, nunca uma tela de plano vazia', async ({
    page,
  }) => {
    await interceptarBase(page, CASO, {
      inicio: {
        estado: 'AGUARDANDO_REVISAO',
        fase: 'revisao',
        mensagem: 'Seu plano está em revisão.',
        proxima_etapa: { destino: 'aguardando', ID_PERGUNTA: null, item_id: null },
      },
    })
    await page.route(`**/caso/${CASO}/api/plano`, async (rota) => {
      await rota.fulfill({
        json: {
          CASO_ID: CASO,
          estado: 'AGUARDANDO_REVISAO',
          plano: null,
          mensagem: 'Seu plano está em revisão.',
        },
      })
    })

    await abrirPlano(page)

    // A mensagem é a DAQUELE estado — "em revisão" explica o que está
    // acontecendo; um "nenhum plano liberado" genérico deixaria o aluno sem
    // saber se falhou, se falta algo dele, ou se é só esperar.
    await expect(page.getByText('Seu plano está em revisão.')).toBeVisible()
    await expect(page.getByText(TITULO_Q03)).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Baixar em PDF' })).toHaveCount(0)
  })

  test('AC-70: reserva pendente é estado explícito, nunca R$ 0,00', async ({ page }) => {
    await interceptarBase(page, CASO, { inicio: INICIO_COM_PLANO })
    await page.route(`**/caso/${CASO}/api/plano`, async (rota) => {
      await rota.fulfill({
        json: {
          ...PLANO_LIBERADO,
          plano: {
            ...PLANO_LIBERADO.plano,
            reserva_mobilizavel: { pendente_de_decisao: true, valor: null },
          },
        },
      })
    })

    await abrirPlano(page)

    await expect(page.getByText('Decisão pendente.')).toBeVisible()
    // Zero seria uma afirmação sobre o dinheiro do aluno que ninguém calculou.
    const textoDaTela = await page.locator('body').innerText()
    expect(textoDaTela).not.toContain('0,00')
  })
})

test.describe('ordem vazia', () => {
  test('EC-07: sem ordem, a tela diz o que resolver antes — nunca uma lista em branco', async ({
    page,
  }) => {
    await interceptarBase(page, CASO, { inicio: INICIO_COM_PLANO })
    await page.route(`**/caso/${CASO}/api/plano`, async (rota) => {
      await rota.fulfill({
        json: {
          ...PLANO_LIBERADO,
          plano: {
            ...PLANO_LIBERADO.plano,
            ordem: [],
            acoes: [
              {
                DIVIDA_ID: 'D001',
                nome_divida: 'Empréstimo consignado — BANCO DO BRASIL',
                descricao: 'Renegociar o consignado antes de projetar a ordem.',
                prioridade_excepcional: false,
              },
            ],
          },
        },
      })
    })

    await abrirPlano(page)

    // Uma lista vazia sem explicação leria como "seu plano não tem nada" —
    // o aluno precisa saber que há um passo antes, e qual é.
    await expect(
      page.getByRole('heading', { name: 'Primeiro, o que precisa ser resolvido' }),
    ).toBeVisible()
    await expect(
      page.getByText('Renegociar o consignado antes de projetar a ordem.'),
    ).toBeVisible()
    // `T-306`/`T-326`: a dívida pelo nome, e o carimbo sem código de cenário.
    await expect(page.getByText('Empréstimo consignado — BANCO DO BRASIL')).toBeVisible()
    await expect(page.getByText('D001', { exact: true })).toHaveCount(0)
    await expect(page.locator('.carimbo')).not.toContainText('método')
  })
})
