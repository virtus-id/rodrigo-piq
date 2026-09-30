// @vitest-environment happy-dom
/**
 * `TelaPlano` — o cenário adicional em seção própria (`RF-98`, `AC-152`,
 * `T-277`).
 *
 * Os números do cenário adicional são diferentes dos do plano de propósito:
 * se algum deles aparecer no resumo ou na ordem, o teste pega a mistura.
 */
import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaPlano from '../../../src/telas/TelaPlano'
import * as api from '../../../src/services/api'
import type { CenarioAdicional, Plano } from '../../../src/tipos'

afterEach(() => {
  vi.restoreAllMocks()
})

const ADICIONAL: CenarioAdicional = {
  rotulo: 'Cenário adicional: se os valores incertos chegarem',
  explicacao: 'Só passam a contar quando forem recebidos.',
  PRAZO_TOTAL: '9 meses',
  CUSTO_FUTURO_TOTAL: 'R$ 1.111,11',
  ordem: ['D002', 'D001'],
  itens: [{ ITEM_ID: 'EXT001', mes: 3, valor: 'R$ 2.000,00' }],
}

function plano(cenario_adicional: CenarioAdicional | null): Plano {
  return {
    titulo: 'Sua ordem projetada de quitação',
    corpo: 'corpo',
    ordem: [
      {
        posicao: 1,
        indice: 1,
        total: 1,
        DIVIDA_ID: 'D001',
        JUSTIFICATIVA_POSICAO: 'j',
        explicacao: 'e',
        fonte: null,
        valores_de_apoio: [],
      },
    ],
    PRAZO_TOTAL: '14 meses',
    CUSTO_FUTURO_TOTAL: 'R$ 3.333,33',
    ENGINE_VERSION: 'e',
    PARAMETROS_VERSION: 'p',
    cenario: 'AVALANCHE',
    acoes: [],
    pendencias: null,
    MODO_ESTABILIZACAO: false,
    RESULTADO_CAIXA_OBSERVADO: '',
    reserva_mobilizavel: { pendente_de_decisao: true, valor: '' },
    cenario_adicional,
    nao_projetados: [],
  }
}

function mostrar(cenario_adicional: CenarioAdicional | null) {
  vi.spyOn(api, 'obterPlano').mockResolvedValue({
    CASO_ID: 'CASO-1',
    estado: 'LIBERADO',
    plano: plano(cenario_adicional),
  })
  return render(<TelaPlano casoId="CASO-1" />)
}

describe('TelaPlano — cenário adicional (AC-152)', () => {
  it('aparece em seção própria, rotulada, abaixo do plano', async () => {
    mostrar(ADICIONAL)

    const secao = await screen.findByRole('region', { name: ADICIONAL.rotulo })
    expect(within(secao).getByText('9 meses')).toBeInTheDocument()
    expect(within(secao).getByText('R$ 1.111,11')).toBeInTheDocument()
    expect(within(secao).getByText(/EXT001/)).toBeInTheDocument()
  })

  it('nenhum número do cenário adicional fora da sua seção', async () => {
    const { container } = mostrar(ADICIONAL)

    const secao = await screen.findByRole('region', { name: ADICIONAL.rotulo })
    const fora = container.cloneNode(true) as HTMLElement
    fora.querySelector('section[aria-labelledby="titulo-cenario-adicional"]')?.remove()
    for (const numero of ['9 meses', 'R$ 1.111,11', 'R$ 2.000,00', 'EXT001']) {
      expect(fora.textContent).not.toContain(numero)
    }
    expect(fora.textContent).toContain('14 meses')
    expect(within(secao).queryByText('14 meses')).not.toBeInTheDocument()
  })

  it('ausente quando null', async () => {
    mostrar(null)

    await screen.findByText('14 meses')
    expect(screen.queryByText(/Cenário adicional/)).not.toBeInTheDocument()
  })
})
