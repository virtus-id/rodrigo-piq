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

function montarEmConferencia(extra: { editavel?: boolean; pode_retomar_edicao?: boolean }) {
  vi.spyOn(api, 'obterRespostasDoCaso').mockResolvedValue({
    CASO_ID: 'C1',
    partes: PARTES,
    ...extra,
  })
  const editar = vi.fn()
  render(
    <TelaRespostas casoId="C1" voltar={vi.fn()} bloco={1} escolherBloco={vi.fn()} editar={editar} />,
  )
  return { editar }
}

describe('TelaRespostas — só leitura em conferência (T-337, RF-114/RF-115)', () => {
  it('em conferência: sem "Editar", com o aviso e a ação de retirar o plano', async () => {
    montarEmConferencia({ editavel: false, pode_retomar_edicao: true })

    expect(await screen.findByText('Seu plano está em conferência.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()
    expect(screen.getByText('Enunciado B1.01?')).toBeInTheDocument() // ler continua livre
    expect(screen.getByRole('button', { name: 'Quero editar minhas respostas' })).toBeInTheDocument()
  })

  it('em cálculo: sem "Editar" e sem a ação de retirar', async () => {
    montarEmConferencia({ editavel: false, pode_retomar_edicao: false })

    expect(await screen.findByText('Estamos montando o seu plano.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Quero editar minhas respostas' })).not.toBeInTheDocument()
  })

  it('pede confirmação, retira o plano e a lista volta a ter "Editar"', async () => {
    const retomar = vi.spyOn(api, 'retomarEdicao').mockResolvedValue({ estado: 'COLETA_INICIAL' })
    const obter = vi
      .spyOn(api, 'obterRespostasDoCaso')
      .mockResolvedValueOnce({ CASO_ID: 'C1', partes: PARTES, editavel: false, pode_retomar_edicao: true })
      .mockResolvedValue({ CASO_ID: 'C1', partes: PARTES, editavel: true, pode_retomar_edicao: false })
    render(<TelaRespostas casoId="C1" voltar={vi.fn()} bloco={1} escolherBloco={vi.fn()} editar={vi.fn()} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Quero editar minhas respostas' }))
    // Nada acontece até confirmar: o texto de RF-115 aparece primeiro.
    expect(retomar).not.toHaveBeenCalled()
    expect(
      screen.getByText('Seu plano sai da conferência. Quando você enviar de novo, ele volta para a fila.'),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Retirar o plano e editar' }))
    expect(await screen.findByRole('button', { name: 'Editar' })).toBeInTheDocument()
    expect(retomar).toHaveBeenCalledWith('C1')
    expect(obter).toHaveBeenCalledTimes(2)
  })

  it('cancelar não retira nada', async () => {
    const retomar = vi.spyOn(api, 'retomarEdicao')
    montarEmConferencia({ editavel: false, pode_retomar_edicao: true })
    fireEvent.click(await screen.findByRole('button', { name: 'Quero editar minhas respostas' }))
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(retomar).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Quero editar minhas respostas' })).toBeInTheDocument()
  })

  it('o servidor recusa (409): a mensagem dele aparece e o plano segue em conferência', async () => {
    vi.spyOn(api, 'retomarEdicao').mockRejectedValue(new Error('Seu plano não está em conferência.'))
    montarEmConferencia({ editavel: false, pode_retomar_edicao: true })
    fireEvent.click(await screen.findByRole('button', { name: 'Quero editar minhas respostas' }))
    fireEvent.click(screen.getByRole('button', { name: 'Retirar o plano e editar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Seu plano não está em conferência.')
    expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()
  })

  it('sem o campo (servidor antigo) a tela é editável como sempre', async () => {
    montarEmConferencia({})
    expect((await screen.findAllByRole('button', { name: 'Editar' })).length).toBeGreaterThan(0)
  })
})

describe('TelaRespostas — foco (T-339)', () => {
  it('abrir a tela não puxa o foco para o título da parte', async () => {
    montar()
    await screen.findByRole('navigation', { name: 'Partes das respostas' })
    expect(document.activeElement).not.toBe(screen.getByRole('heading', { level: 2 }))
  })
})

describe('TelaRespostas — taxa e dinheiro como o aluno digitou (T-335)', () => {
  it('TAXA aparece como "8%" e MOEDA como "R$ 2.276,76"', async () => {
    vi.spyOn(api, 'obterRespostasDoCaso').mockResolvedValue({
      CASO_ID: 'C1',
      partes: [
        {
          bloco: 5,
          rotulo: 'Parte Cinco',
          total_de_perguntas: 2,
          respondidas: [
            resposta('B5.D01A', 'D006', { tipo: 'TAXA', valores: ['0.08'] }),
            resposta('B5.B03', 'D006', { tipo: 'MOEDA', valores: ['2276.76'] }),
          ],
        },
      ],
    })
    render(<TelaRespostas casoId="C1" voltar={vi.fn()} bloco={5} escolherBloco={vi.fn()} editar={vi.fn()} />)

    expect(await screen.findByText('8%')).toBeInTheDocument()
    expect(screen.getByText('R$ 2.276,76')).toBeInTheDocument()
    expect(screen.queryByText('0.08')).not.toBeInTheDocument()
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
