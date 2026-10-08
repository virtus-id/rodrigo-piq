// @vitest-environment happy-dom
/** Mural e cartões de cada mês: links por âncora, referência "Mês 01" e dois planos. */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MesesDetalhados, MuralDoPlano } from '../../../src/componentes/MuralEMeses'
import type { PlanoDetalhado } from '../../../src/tipos'

const MES = {
  divida_da_vez: { numero: 1, nome: 'Cartão rotativo' },
  valor_extra: 'R$ 500,00',
  quitadas: [] as { numero: number; nome: string }[],
  primeira_quitacao: false,
  ultimo: false,
}

const DETALHES: PlanoDetalhado[] = [
  {
    cor: 'azul',
    titulo: 'Seguindo o seu plano',
    meses: [
      { ...MES, rotulo: 'Mês 01', ancora: 'mes-azul-01', saldo: 'R$ 4.200,00' },
      {
        ...MES,
        rotulo: 'Mês 02',
        ancora: 'mes-azul-02',
        saldo: 'R$ 0,00',
        quitadas: [{ numero: 1, nome: 'Cartão rotativo' }],
        primeira_quitacao: true,
        ultimo: true,
        divida_da_vez: null,
      },
    ],
  },
  {
    cor: 'verde',
    titulo: 'Plano acelerado',
    meses: [{ ...MES, rotulo: 'Mês 01', ancora: 'mes-verde-01', saldo: 'R$ 3.700,00' }],
  },
]

const TEXTOS = {
  mural_titulo: 'Seu plano detalhado',
  meses_titulo: 'Mês a mês, em detalhe',
  rotulo_deve: 'Deve',
  rotulo_extra_mes: 'Extra',
  texto_coloque: 'Coloque {valor} nela, depois das parcelas.',
  instrucao_parcelas: 'Pague as parcelas de sempre.',
  voltar: 'Voltar ao mural',
}

describe('MuralDoPlano e MesesDetalhados', () => {
  it('cada bloco do mural aponta para o cartão do mesmo mês', () => {
    render(
      <>
        <MuralDoPlano detalhes={DETALHES} textos={TEXTOS} />
        <MesesDetalhados detalhes={DETALHES} textos={TEXTOS} />
      </>,
    )
    const links = Array.from(document.querySelectorAll('a[data-mes]')).map((a) =>
      a.getAttribute('href'),
    )
    expect(links).toEqual(['#mes-azul-01', '#mes-azul-02', '#mes-verde-01'])
    for (const href of links) expect(document.querySelector(href as string)).not.toBeNull()
    expect(screen.getAllByText('Mês 01').length).toBeGreaterThanOrEqual(4)
  })

  it('o cartão mostra a dívida da vez, o extra e o saldo; o último mês diz que acabou', () => {
    render(<MesesDetalhados detalhes={DETALHES} textos={TEXTOS} />)
    expect(screen.getAllByText(/Coloque R\$ 500,00 nela/).length).toBe(2)
    expect(screen.getByText(/R\$ 4\.200,00/)).toBeTruthy()
    const ultimo = document.getElementById('mes-azul-02') as HTMLElement
    expect(ultimo.textContent).toContain('Cartão rotativo')
  })

  it('o mural não usa anel dourado: só o bloco forte e o número da dívida marcam a quitação', () => {
    render(<MuralDoPlano detalhes={DETALHES} textos={TEXTOS} />)
    const bloco = document.querySelector('a[data-mes="mes-azul-02"]') as HTMLElement
    expect(bloco.className).not.toContain('D9A400')
    expect(bloco.textContent).toContain('✓ 1')
  })
})
