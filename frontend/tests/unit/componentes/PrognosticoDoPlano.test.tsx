// @vitest-environment happy-dom
/** `PrognosticoDoPlano` — uma linha por caminho: título, veredito, barra com pontos e lista. */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import PrognosticoDoPlano from '../../../src/componentes/PrognosticoDoPlano'

const BASE = {
  nota: 'nota',
  marcador: '',
  escala: 56,
  marcos: [] as { mes: number; numero: number }[],
  itens: [] as string[],
  economia: '',
  rotulo_curto: '',
}
const PROGNOSTICO = {
  titulo: 'Seu plano em números',
  introducao: 'Três caminhos.',
  caminhos: [
    {
      ...BASE,
      cor: 'vermelho' as const,
      titulo: 'Se nada mudar',
      veredito: 'No Mês 56, você ainda deve R$ 101.158,00.',
      destaques: [
        { rotulo: 'Dívida inicial', valor: 'R$ 168.199,23' },
        { rotulo: 'Primeira quitação prevista', valor: 'Mês 12' },
      ],
      mes_fim: 56,
    },
    {
      ...BASE,
      cor: 'azul' as const,
      titulo: 'Seguindo o seu plano',
      veredito: 'Quitação prevista em 56 meses. Até R$ 4.724,51 para dívidas por mês.',
      destaques: [{ rotulo: 'Aporte extra inicial / mês', valor: 'R$ 848,13' }],
      mes_fim: 56,
      marcos: [
        { mes: 1, numero: 1 },
        { mes: 3, numero: 2 },
        { mes: 56, numero: 3 },
      ],
      itens: ['M1 · Quita Cheque Itaú', 'M3 · Quita Mercado Pago', 'M56 · Quita Santander 1.948'],
    },
    {
      ...BASE,
      cor: 'verde' as const,
      titulo: 'Plano acelerado',
      veredito: 'Quitação prevista em 47 meses: 9 meses antes. Até R$ 5.324,51 por mês.',
      destaques: [{ rotulo: 'Aporte extra inicial / mês', valor: 'R$ 1.448,13' }],
      mes_fim: 47,
      marcos: [
        { mes: 1, numero: 1 },
        { mes: 47, numero: 2 },
      ],
      itens: ['M1 · Quita Cheque Itaú', 'M47 · Quita Santander 1.948'],
      economia: 'Economia frente ao plano base: R$ 17.501,71',
    },
  ],
  detalhes: [],
}

describe('PrognosticoDoPlano', () => {
  it('mostra uma linha por caminho, na ordem, com o veredito em texto', () => {
    render(<PrognosticoDoPlano prognostico={PROGNOSTICO} />)
    const linhas = Array.from(document.querySelectorAll('[data-caminho]'))
    expect(linhas.map((l) => l.getAttribute('data-caminho'))).toEqual(['vermelho', 'azul', 'verde'])
    expect(screen.getByText('No Mês 56, você ainda deve R$ 101.158,00.')).toBeTruthy()
    expect(screen.getByText(/Até R\$ 5\.324,51 por mês/)).toBeTruthy()
    expect(screen.getByText('Economia frente ao plano base: R$ 17.501,71')).toBeTruthy()
  })

  it('a barra do plano acelerado termina antes da do plano seguido', () => {
    render(<PrognosticoDoPlano prognostico={PROGNOSTICO} />)
    const barras = document.querySelectorAll('[role="img"]')
    expect((barras[2].children[0] as HTMLElement).style.width).toBe(`${(47 / 56) * 100}%`)
    expect((barras[1].children[0] as HTMLElement).style.width).toBe('100%')
  })

  it('azul e verde têm um ponto "M<mês>" por dívida quitada; o vermelho não tem', () => {
    render(<PrognosticoDoPlano prognostico={PROGNOSTICO} />)
    const rotulos = (cor: string) =>
      Array.from(document.querySelectorAll(`[data-caminho="${cor}"] [data-marco]`)).map(
        (m) => m.textContent,
      )
    expect(rotulos('azul')).toEqual(['M1', 'M3', 'M56'])
    expect(rotulos('verde')).toEqual(['M1', 'M47'])
    expect(rotulos('vermelho')).toEqual([])
  })

  it('lista "M7 · Quita …" dentro do bloco, uma linha por dívida', () => {
    render(<PrognosticoDoPlano prognostico={PROGNOSTICO} />)
    const itens = (cor: string) =>
      Array.from(document.querySelectorAll(`[data-caminho="${cor}"] [data-item]`)).map(
        (i) => i.textContent,
      )
    expect(itens('azul')).toEqual([
      'M1 · Quita Cheque Itaú',
      'M3 · Quita Mercado Pago',
      'M56 · Quita Santander 1.948',
    ])
    expect(itens('vermelho')).toEqual([])
    expect(document.body.innerHTML).not.toContain('D9A400')
  })

  it('sem verde mostra só duas linhas', () => {
    render(
      <PrognosticoDoPlano
        prognostico={{ ...PROGNOSTICO, caminhos: PROGNOSTICO.caminhos.slice(0, 2) }}
      />,
    )
    expect(document.querySelectorAll('[data-caminho]')).toHaveLength(2)
  })
})
