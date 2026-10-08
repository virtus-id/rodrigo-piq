// @vitest-environment happy-dom
/**
 * `PontoDePartida` — o que entra (verde, +) e o que sai (vermelho, −): a cor
 * não é o único sinal; o leitor de tela ouve "Entra" ou "Sai".
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import PontoDePartida from '../../../src/componentes/PontoDePartida'

const PONTO = {
  renda: 'R$ 8.000,00',
  gastos: 'R$ 3.000,00',
  gastos_ocasionais: 'R$ 500,00',
  parcelas: 'R$ 700,00',
  valor_extra: 'R$ 1.000,00',
  quantidade_de_dividas: 2,
}

describe('PontoDePartida — entrada e saída', () => {
  it('renda é entrada; gastos, gastos ocasionais e parcelas são saída; a contagem é neutra', () => {
    render(<PontoDePartida ponto={PONTO} textos={{}} titulo="" mostrarValorExtra={false} />)

    expect(screen.getAllByText('Entra')).toHaveLength(1)
    expect(screen.getAllByText('Sai')).toHaveLength(3)
    expect(screen.getAllByText('+')).toHaveLength(1)
    expect(screen.getAllByText('\u2212')).toHaveLength(3)

    const renda = screen.getByText('R$ 8.000,00').closest('dd')
    expect(renda?.className).toContain('text-accent')
    const parcelas = screen.getByText('R$ 700,00').closest('dd')
    expect(parcelas?.className).toContain('text-bad')
    const contagem = screen.getByText('2').closest('dd')
    expect(contagem?.className).not.toMatch(/text-accent|text-bad/)
  })
})
