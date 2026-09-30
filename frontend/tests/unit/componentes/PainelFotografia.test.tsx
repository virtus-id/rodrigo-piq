// @vitest-environment happy-dom
/**
 * `PainelFotografia` — a fotografia do mês na `B3.C00` (`RF-79`, `RF-80`,
 * `EC-28`, T-228). Os números são do servidor: o componente só exibe.
 */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import PainelFotografia from '../../../src/componentes/PainelFotografia'
import type { PainelFotografia as Painel } from '../../../src/tipos'

function painel(extra: Partial<Painel> = {}): Painel {
  return {
    tipo: 'FOTOGRAFIA_DO_MES',
    renda_total: '8000.00',
    despesas_totais: '5500.00',
    sobra_antes_das_dividas: '2500.00',
    parcial: { renda: false, despesas: false, sobra: false },
    despesas_por_item: [
      {
        item_id: 'I001',
        rotulo: 'Aluguel',
        valor_mensal: '3000.00',
        corrigir: { ID_PERGUNTA: 'B3.DF01', item_id: 'I001' },
      },
    ],
    nao_mensais_por_item: [
      {
        item_id: 'NM001',
        rotulo: 'IPTU',
        valor_mensal: '500.00',
        corrigir: { ID_PERGUNTA: 'B3.NM02B', item_id: 'NM001' },
      },
    ],
    ...extra,
  }
}

describe('PainelFotografia', () => {
  it('AC-117: três valores, com a sobra rotulada "antes das dívidas"', () => {
    render(<PainelFotografia painel={painel()} />)

    expect(screen.getByText('R$ 8.000,00')).toBeInTheDocument()
    expect(screen.getByText('R$ 5.500,00')).toBeInTheDocument()
    expect(screen.getByText('R$ 2.500,00')).toBeInTheDocument()
    expect(screen.getByText(/antes das dívidas/)).toBeInTheDocument()
    expect(screen.queryByText(/parcial/)).toBeNull()
  })

  it('EC-28: null é "não informado", nunca R$ 0,00; "parcial" quando o servidor marca', () => {
    render(
      <PainelFotografia
        painel={painel({
          renda_total: null,
          sobra_antes_das_dividas: null,
          parcial: { renda: false, despesas: true, sobra: false },
        })}
      />,
    )

    expect(screen.getAllByText('não informado')).toHaveLength(2)
    expect(screen.queryByText('R$ 0,00')).toBeNull()
    expect(screen.getByText(/parcial \(há itens sem valor\)/)).toBeInTheDocument()
  })

  it('sobra negativa sai com sinal, sem cálculo no cliente', () => {
    render(<PainelFotografia painel={painel({ sobra_antes_das_dividas: '-150.50' })} />)

    expect(screen.getByText('−R$ 150,50')).toBeInTheDocument()
  })

  it('RF-80: decomposições num <details>, alcançáveis por teclado, com "corrigir"', async () => {
    const aoCorrigir = vi.fn()
    const usuario = userEvent.setup()
    const { container } = render(<PainelFotografia painel={painel()} aoCorrigir={aoCorrigir} />)

    const detalhes = container.querySelector('details')
    expect(detalhes).not.toBeNull()
    expect(detalhes?.open).toBe(false)

    // O `<summary>` é o primeiro alvo do Tab: alcançável por teclado. (O
    // happy-dom não abre `<details>` por Enter; o navegador abre — o clique
    // abaixo é a mesma ativação.)
    await usuario.tab()
    expect(screen.getByText('Ver de onde vêm as despesas')).toHaveFocus()
    await usuario.click(screen.getByText('Ver de onde vêm as despesas'))
    expect(detalhes?.open).toBe(true)

    await usuario.click(
      within(detalhes as HTMLElement).getByRole('button', { name: 'Corrigir IPTU' }),
    )
    expect(aoCorrigir).toHaveBeenCalledWith('B3.NM02B', 'NM001')
  })
})
