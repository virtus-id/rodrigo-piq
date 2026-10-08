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
        quitas: ['Quita Cartão Itaú'],
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
  rotulo_deve: 'Ainda deve',
  rotulo_extra_mes: 'Pagar a mais',
  pagina_quitacao: 'Quitação prevista',
  pagina_subtitulo: 'Mês {de_total} · Quanto pagar.',
  pagina_total_pagar: 'Total a pagar neste mês',
  fecha_conta: '{inicio} + {juros} - {pagamentos} = {restante}',
  fecha_total: 'Total a pagar = habitual {habitual} + extra {extra}',
  executar_titulo: 'QUANDO E COMO VOU EXECUTAR',
  executar_1: 'Conferir descontos em folha.',
  executar_2: 'Aplicar o extra neste mês.',
  executar_3: 'Conferir saldos com o credor.',
  linha_quita: 'Quitação prevista neste mês',
  linha_apoio: 'Vencimento / folha + extra no mês',
  texto_coloque: 'Pagar a mais: {valor}, inteiro para essa dívida.',
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
    expect(screen.getAllByText(/Pagar a mais: R\$ 500,00, inteiro para essa dívida/).length).toBe(2)
    expect(screen.getByText(/R\$ 4\.200,00/)).toBeTruthy()
    const ultimo = document.getElementById('mes-azul-02') as HTMLElement
    expect(ultimo.textContent).toContain('Cartão rotativo')
  })

  it('o mês com quitação leva o troféu no canto e "Quita <nome>"; sem check nem anel dourado', () => {
    render(<MuralDoPlano detalhes={DETALHES} textos={TEXTOS} />)
    const bloco = document.querySelector('a[data-mes="mes-azul-02"]') as HTMLElement
    expect(bloco.querySelector('[data-trofeu]')).not.toBeNull()
    expect(bloco.textContent).toContain('Quita Cartão Itaú')
    expect(bloco.textContent).not.toContain('✓')
    expect(bloco.className).not.toContain('D9A400')
    expect(document.querySelector('a[data-mes="mes-azul-01"] [data-trofeu]')).toBeNull()
  })

  it('o bloco diz "Pagar a mais" e "Ainda deve"', () => {
    render(<MuralDoPlano detalhes={DETALHES} textos={TEXTOS} />)
    const bloco = document.querySelector('a[data-mes="mes-azul-01"]') as HTMLElement
    expect(bloco.textContent).toContain('Ainda deve')
    expect(bloco.textContent).toContain('Pagar a mais')
    expect(bloco.textContent).toContain('R$ 500,00')
  })

  it('com a página do mês: resumo, tabela por dívida, contas e o que executar; troféu na quitação', () => {
    const pagina = {
      numero: '02',
      de_total: '02 de 02',
      total_pagar: 'R$ 200,00',
      extra_aplicado: 'R$ 0,00',
      divida_apos: 'R$ 0,00',
      linhas: [
        {
          nome: 'Cartão rotativo',
          saldo_antes: '200,00',
          juros: '0,00',
          habitual: '200,00',
          extra: '0,00',
          total: '200,00',
          saldo_depois: '0,00',
          quita: true,
        },
      ],
      inicio: 'R$ 200,00',
      juros: 'R$ 0,00',
      pagamentos: 'R$ 200,00',
      restante: 'R$ 0,00',
      habitual_total: 'R$ 200,00',
      extra_total: 'R$ 0,00',
      quitacao: true,
    }
    const detalhes: PlanoDetalhado[] = [
      { ...DETALHES[0], meses: [{ ...DETALHES[0].meses[1], pagina }] },
    ]
    window.location.hash = '#mes-azul-02'
    render(<MesesDetalhados detalhes={detalhes} textos={TEXTOS} />)
    const cartao = document.getElementById('mes-azul-02') as HTMLDetailsElement
    expect(cartao.tagName).toBe('DETAILS')
    expect(cartao.open).toBe(true) // o link do mural abre a página
    expect(cartao.textContent).toContain('Total a pagar neste mês')
    expect(cartao.textContent).toContain('R$ 200,00 + R$ 0,00 - R$ 200,00 = R$ 0,00')
    expect(cartao.textContent).toContain('Conferir saldos com o credor.')
    expect(cartao.querySelector('[data-trofeu]')).not.toBeNull()
    expect(cartao.querySelector('tr[data-quita="sim"]')).not.toBeNull()
    window.location.hash = ''
  })
})
