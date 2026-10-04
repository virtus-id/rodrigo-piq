// @vitest-environment happy-dom
/**
 * `JornadaDoPlano` — "Seu plano, mês a mês". Até 12 meses, um cartão por
 * mês; acima disso, calendário por ano (uma linha por ano, 12 meses lado a
 * lado), com os anos já montados pelo servidor em `grade_anos`.
 */
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import JornadaDoPlano from '../../../src/componentes/JornadaDoPlano'
import type { AnoDaGrade, MesDaGrade } from '../../../src/tipos'

afterEach(() => {
  cleanup()
})

const CARTAO = 'Cartão de crédito rotativo (NUBANK)'

const TEXTOS: Record<string, string> = {
  introducao: 'Cada quadro é um mês do plano.',
  introducao_anos: 'Cada linha é um ano do plano.',
  rotulo_mes: 'Mês',
  rotulo_ano: 'Ano',
  meses_do_ano: 'Mês {inicio} a {fim}',
  mes_unico_do_ano: 'Mês {inicio}',
  valor_do_ano: 'Valor extra de cada mês: {valores}',
  separador_de_valores: ', depois ',
  quitacao_do_ano: 'Mês {mes}: quitação de {divida}',
  quitada: 'dívida quitada',
  chegada: 'fim das dívidas',
  primeira_vitoria: '1ª quitação',
  legenda_comum: 'Mês de pagamento.',
}

function mes(numero: number, tipo: MesDaGrade['tipo'] = 'ATAQUE'): MesDaGrade {
  return {
    mes: numero,
    tipo,
    alvo: tipo === 'CHEGADA' ? null : CARTAO,
    valor_extra: tipo === 'CHEGADA' ? null : 'R$ 300,00',
    dividas_quitadas: tipo === 'QUITACAO' ? [CARTAO] : [],
    eh_primeira_vitoria: tipo === 'QUITACAO',
    tem_aporte: false,
  }
}

function grade(total: number): MesDaGrade[] {
  return Array.from({ length: total }, (_, indice) => {
    const numero = indice + 1
    if (numero === total) return mes(numero, 'CHEGADA')
    if (numero === 8) return mes(numero, 'QUITACAO')
    return mes(numero)
  })
}

function anos(meses: MesDaGrade[]): AnoDaGrade[] {
  return [
    {
      numero: 1,
      mes_inicio: 1,
      mes_fim: 12,
      meses: meses.slice(0, 12),
      valores_extras: ['R$ 300,00', 'R$ 500,00'],
      quitacoes: [{ mes: 8, nome: CARTAO }],
    },
    {
      numero: 2,
      mes_inicio: 13,
      mes_fim: 24,
      meses: meses.slice(12, 24),
      valores_extras: ['R$ 500,00'],
      quitacoes: [],
    },
    {
      numero: 3,
      mes_inicio: 25,
      mes_fim: 30,
      meses: meses.slice(24),
      valores_extras: ['R$ 500,00'],
      quitacoes: [{ mes: 30, nome: 'Cheque especial (CAIXA)' }],
    },
  ]
}

describe('JornadaDoPlano', () => {
  it('plano de até 12 meses: um cartão por mês, sem calendário', () => {
    render(<JornadaDoPlano grade={grade(5)} anos={[]} textos={TEXTOS} titulo="Seu plano, mês a mês" />)

    expect(screen.getByText(TEXTOS.introducao)).toBeTruthy()
    expect(screen.queryByText(TEXTOS.introducao_anos)).toBeNull()
    expect(screen.queryByRole('heading', { level: 3, name: /Ano 1/ })).toBeNull()
    expect(screen.getByText('fim das dívidas')).toBeTruthy()
  })

  it('plano de 30 meses: uma linha por ano, com os meses de cada uma', () => {
    const meses = grade(30)
    render(
      <JornadaDoPlano grade={meses} anos={anos(meses)} textos={TEXTOS} titulo="Seu plano, mês a mês" />,
    )

    expect(screen.getByText(TEXTOS.introducao_anos)).toBeTruthy()
    expect(screen.queryByText(TEXTOS.introducao)).toBeNull()

    const titulos = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(titulos).toEqual(['Ano 1Mês 1 a 12', 'Ano 2Mês 13 a 24', 'Ano 3Mês 25 a 30'])

    const ano3 = screen.getByRole('heading', { level: 3, name: /Ano 3/ }).closest('li')!
    expect(within(ano3).getAllByRole('listitem')).toHaveLength(6)
    expect(within(ano3).getByLabelText('Mês 30: fim das dívidas')).toBeTruthy()
  })

  it('cada ano mostra o valor extra e as quitações, e o mês da 1ª quitação é anunciado', () => {
    const meses = grade(30)
    render(
      <JornadaDoPlano grade={meses} anos={anos(meses)} textos={TEXTOS} titulo="Seu plano, mês a mês" />,
    )

    const valores = screen.getAllByText(/^Valor extra de cada mês:/)
    expect(valores[0].textContent).toBe('Valor extra de cada mês: R$ 300,00, depois R$ 500,00')
    expect(screen.getByText(`Mês 8: quitação de ${CARTAO}`)).toBeTruthy()
    expect(screen.getByLabelText('Mês 8: 1ª quitação')).toBeTruthy()
    expect(screen.getByLabelText('Mês 2: R$ 300,00')).toBeTruthy()
  })
})
