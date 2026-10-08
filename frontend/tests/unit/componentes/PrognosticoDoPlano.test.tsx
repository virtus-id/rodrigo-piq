// @vitest-environment happy-dom
/** `PrognosticoDoPlano` — uma linha por caminho, veredito em texto e barra na mesma escala. */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import PrognosticoDoPlano from '../../../src/componentes/PrognosticoDoPlano'

const BASE = {
  nota: 'nota',
  marcador: '',
  mes_sombra: null,
  escala: 56,
  marcos: [] as { mes: number; numero: number }[],
  itens: [] as { numero: number; texto: string }[],
  rotulo_curto: '',
}
const PROGNOSTICO = {
  titulo: 'Seu prognóstico: qual caminho seguir?',
  introducao: 'Três caminhos.',
  caminhos: [
    {
      ...BASE,
      cor: 'vermelho' as const,
      titulo: 'Se nada mudar',
      veredito: 'Em 56 meses, você ainda deve R$ 71.200,00.',
      marcador: 'ainda deve R$ 71.200,00',
      destaques: [{ rotulo: 'Hoje você deve', valor: 'R$ 68.500,00' }],
      mes_fim: 56,
    },
    {
      ...BASE,
      cor: 'azul' as const,
      titulo: 'Seguindo o seu plano',
      veredito: 'Você quita tudo em 56 meses.',
      marcador: 'dívida zero',
      destaques: [{ rotulo: 'Valor por mês', valor: 'R$ 1.300,00' }],
      mes_fim: 56,
    },
    {
      ...BASE,
      cor: 'verde' as const,
      titulo: 'Plano acelerado (+ R$ 500,00 por mês)',
      veredito: 'Você quita tudo em 38 meses: 18 meses antes do plano.',
      marcador: 'dívida zero',
      destaques: [{ rotulo: 'A menos de custo', valor: 'R$ 17.400,00' }],
      mes_fim: 38,
      mes_sombra: 56,
      marcos: [
        { mes: 10, numero: 1 },
        { mes: 38, numero: 2 },
      ],
      itens: [
        { numero: 1, texto: 'M10 - Quita Cartão Itaú' },
        { numero: 2, texto: 'M38 - Quita Consignado Caixa' },
      ],
      rotulo_curto: 'Acelerado',
    },
  ],
  detalhes: [],
}

describe('PrognosticoDoPlano', () => {
  it('mostra uma linha por caminho, na ordem, com o veredito em texto', () => {
    render(<PrognosticoDoPlano prognostico={PROGNOSTICO} />)

    const linhas = Array.from(document.querySelectorAll('[data-caminho]'))
    expect(linhas.map((l) => l.getAttribute('data-caminho'))).toEqual(['vermelho', 'azul', 'verde'])
    expect(screen.getByText('Você quita tudo em 56 meses.')).toBeTruthy()
    expect(screen.getByText('Você quita tudo em 38 meses: 18 meses antes do plano.')).toBeTruthy()
    expect(screen.getByText('R$ 17.400,00')).toBeTruthy()
    expect(linhas[0].className).toContain('border-l-bad')
    expect(linhas[1].className).toContain('border-l-azul')
  })

  it('a barra do verde é mais curta que a do azul e leva a sombra do plano', () => {
    render(<PrognosticoDoPlano prognostico={PROGNOSTICO} />)
    const barras = document.querySelectorAll('[role="img"]')
    const verde = barras[2]
    expect((verde.children[0] as HTMLElement).style.width).toBe(`${(38 / 56) * 100}%`)
    expect((verde.children[1] as HTMLElement).style.width).toBe('100%')
    expect((barras[1].firstElementChild as HTMLElement).style.width).toBe('100%')
  })

  it('marca cada dívida quitada na barra', () => {
    render(<PrognosticoDoPlano prognostico={PROGNOSTICO} />)
    const marcos = document.querySelectorAll('[data-caminho="verde"] [data-marco]')
    expect(Array.from(marcos).map((m) => m.textContent)).toEqual(['1', '2'])
    expect((marcos[1] as HTMLElement).style.left).toBe(`${(38 / 56) * 100}%`)
  })

  it('cada bloco traz uma linha por dívida ("M10 - Quita …"), sem anel dourado', () => {
    render(<PrognosticoDoPlano prognostico={PROGNOSTICO} />)
    const itens = document.querySelectorAll('[data-caminho="verde"] [data-item]')
    expect(Array.from(itens).map((i) => i.textContent)).toEqual([
      '1M10 - Quita Cartão Itaú',
      '2M38 - Quita Consignado Caixa',
    ])
    expect(document.querySelectorAll('[data-caminho="vermelho"] [data-item]')).toHaveLength(0)
    expect(document.body.innerHTML).not.toContain('D9A400')
  })

  it('sem verde mostra só duas linhas', () => {
    render(
      <PrognosticoDoPlano
        prognostico={{
          ...PROGNOSTICO,
          caminhos: PROGNOSTICO.caminhos.slice(0, 2),
        }}
      />,
    )
    expect(document.querySelectorAll('[data-caminho]')).toHaveLength(2)
  })
})
