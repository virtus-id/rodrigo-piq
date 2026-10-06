// @vitest-environment happy-dom
/** `PrognosticoDoPlano` — um cartão por caminho, com título próprio (a cor não é o único sinal). */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import PrognosticoDoPlano from '../../../src/componentes/PrognosticoDoPlano'

const PROGNOSTICO = {
  titulo: 'Seu prognóstico: três caminhos',
  introducao: 'Veja onde você chegaria.',
  caminhos: [
    {
      cor: 'vermelho' as const,
      titulo: 'Se nada mudar',
      descricao: 'Sem ação.',
      linhas: [{ rotulo: 'Hoje você deve', valor: 'R$ 10.000,00' }],
    },
    {
      cor: 'azul' as const,
      titulo: 'Seguindo o seu plano',
      descricao: 'O plano.',
      linhas: [{ rotulo: 'Prazo para quitar tudo', valor: '20 meses' }],
    },
  ],
}

describe('PrognosticoDoPlano', () => {
  it('mostra um cartão por caminho, na cor do caminho, com os valores do servidor', () => {
    render(<PrognosticoDoPlano prognostico={PROGNOSTICO} />)

    expect(screen.getByRole('heading', { name: 'Seu prognóstico: três caminhos' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Se nada mudar' })).toBeTruthy()
    expect(screen.getByText('R$ 10.000,00')).toBeTruthy()
    expect(screen.getByText('20 meses')).toBeTruthy()
    expect(screen.queryByText('Seu plano com um esforço extra')).toBeNull()
    expect(document.querySelector('[data-caminho="vermelho"]')?.className).toContain('text-bad')
    expect(document.querySelector('[data-caminho="azul"]')?.className).toContain('text-azul')
  })
})
