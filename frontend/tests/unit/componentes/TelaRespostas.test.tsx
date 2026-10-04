// @vitest-environment happy-dom
/**
 * `TelaRespostas` — menu de partes, ficha visual e agrupamento por item
 * (`T-334`; `RF-68`, `RF-69`, `AC-100`, `AC-101`).
 *
 * Textos inventados: o que se prova é a ESTRUTURA, não a redação do questionário.
 */
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaRespostas, { agruparPorItem } from '../../../src/telas/TelaRespostas'
import * as api from '../../../src/services/api'
import type { ParteDasRespostas, RespostaDada } from '../../../src/tipos'

afterEach(() => {
  vi.restoreAllMocks()
})

function resposta(ID: string, item_id: string | null, extra: Partial<RespostaDada> = {}): RespostaDada {
  return {
    ID,
    item_id,
    enunciado: `Enunciado ${ID}${item_id ? ` (${item_id})` : ''}?`,
    respondida_como_nao_sei: false,
    valores: [`valor ${ID}`],
    ...extra,
  }
}

const PARTES: ParteDasRespostas[] = [
  { bloco: 1, rotulo: 'Parte Um', total_de_perguntas: 10, respondidas: [resposta('B1.01', null)] },
  { bloco: 2, rotulo: 'Parte Dois', total_de_perguntas: 4, respondidas: [] },
  {
    bloco: 3,
    rotulo: 'Parte Três',
    total_de_perguntas: 8,
    // Ordem do servidor: pergunta a pergunta, intercalando as dívidas.
    respondidas: [
      resposta('B5.A', 'D001'),
      resposta('B5.A', 'D002'),
      resposta('B5.B', 'D001', { respondida_como_nao_sei: true, valores: [] }),
      resposta('B5.B', 'D002'),
    ],
  },
]

function montar(bloco?: number) {
  vi.spyOn(api, 'obterRespostasDoCaso').mockResolvedValue({ CASO_ID: 'C1', partes: PARTES })
  const escolherBloco = vi.fn()
  const editar = vi.fn()
  render(
    <TelaRespostas
      casoId="C1"
      voltar={vi.fn()}
      bloco={bloco}
      escolherBloco={escolherBloco}
      editar={editar}
    />,
  )
  return { escolherBloco, editar }
}

describe('agruparPorItem', () => {
  it('soltas primeiro; um grupo por item, na ordem de aparição, sem reordenar as perguntas', () => {
    const grupos = agruparPorItem(PARTES[2].respondidas)
    expect(grupos.map((g) => g.titulo)).toEqual(['Dívida 1', 'Dívida 2'])
    expect(grupos[0].respostas.map((r) => r.ID)).toEqual(['B5.A', 'B5.B'])
    expect(grupos[1].respostas.map((r) => r.item_id)).toEqual(['D002', 'D002'])

    const mistas = agruparPorItem([resposta('X', 'D001'), resposta('Y', null)])
    expect(mistas[0]).toMatchObject({ itemId: null, titulo: null })
  })
})

describe('TelaRespostas — menu e painel (T-334)', () => {
  it('menu com todas as partes, contagem e "Vazia"; abre a primeira com resposta', async () => {
    montar()
    const menu = await screen.findByRole('navigation', { name: 'Partes das respostas' })
    expect(within(menu).getAllByRole('button')).toHaveLength(3)
    expect(within(menu).getByText('1 resposta de 10 perguntas')).toBeInTheDocument()
    expect(within(menu).getByText('Vazia')).toBeInTheDocument()
    expect(within(menu).getByRole('button', { name: /Parte Um/ })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByText('Enunciado B1.01?')).toBeInTheDocument()
  })

  it('a parte da rota abre no painel; clicar numa parte pede a troca pela rota', async () => {
    const { escolherBloco } = montar(3)
    const menu = await screen.findByRole('navigation', { name: 'Partes das respostas' })
    expect(within(menu).getByRole('button', { name: /Parte Três/ })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.queryByText('Enunciado B1.01?')).not.toBeInTheDocument()

    fireEvent.click(within(menu).getByRole('button', { name: /Parte Dois/ }))
    expect(escolherBloco).toHaveBeenCalledWith(2)
  })

  it('parte vazia diz que está vazia (AC-101)', async () => {
    montar(2)
    expect(await screen.findByText(/ainda não respondeu nada desta parte/)).toBeInTheDocument()
  })

  it('fichas em cartões por dívida; "não sei" com selo', async () => {
    montar(3)
    expect(await screen.findByText('Dívida 1')).toBeInTheDocument()
    expect(screen.getByText('Dívida 2')).toBeInTheDocument()
    expect(screen.getByText('Você respondeu: não sei.')).toBeInTheDocument()
    expect(screen.getByText('Não sei')).toBeInTheDocument()
  })

  it('"Editar" leva ID, item e a parte aberta (RF-69)', async () => {
    const { editar } = montar(3)
    await screen.findByText('Dívida 1')
    fireEvent.click(screen.getAllByRole('button', { name: 'Editar' })[1])
    expect(editar).toHaveBeenCalledWith('B5.B', 'D001', 3)
  })
})
