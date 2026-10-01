// @vitest-environment happy-dom
/**
 * `TelaFormulario` — a ficha curta inteira numa tela (`T-314` a `T-317`,
 * `AC-164`–`AC-167`).
 *
 * Perguntas e complementares vêm do servidor; a tela só desenha, grava em
 * sequência pela rota de sempre e volta à lista quando o item fica completo.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaFichas, { TITULOS_POR_ESCOPO } from '../../../src/telas/TelaFichas'
import TelaFormulario from '../../../src/telas/TelaFormulario'
import TelaPergunta from '../../../src/telas/TelaPergunta'
import * as api from '../../../src/services/api'
import type {
  ConfirmacaoDeResposta,
  Ficha,
  FormularioDoItem,
  Pergunta,
  TipoResposta,
} from '../../../src/tipos'

function fabricar(ID: string, tipo: TipoResposta, extra: Partial<Pergunta> = {}): Pergunta {
  return {
    CASO_ID: 'CASO-1',
    ID,
    bloco: 3,
    tipo,
    enunciado: `Pergunta ${ID}`,
    opcoes: [],
    escopo_repeticao: 'RECURSO_EXTRAORDINARIO_ID',
    item_id: 'EXT002',
    posicao: null,
    total_na_ficha: null,
    admite_nao_sei: false,
    valor_atual: null,
    respondida_como_nao_sei: false,
    valores_marcados: [],
    aviso: null,
    ...extra,
  }
}

const tipo = fabricar('B3.05A', 'SELECAO_UNICA', {
  opcoes: [
    {
      rotulo: '13º salário',
      valor_interno: '13O_SALARIO',
      admite_nao_sei: false,
    },
    { rotulo: 'Outro', valor_interno: 'OUTRO', admite_nao_sei: false },
  ],
  complementares: { OUTRO: [fabricar('B3.05AO', 'TEXTO_CURTO')] },
})

function formulario(extra: Partial<FormularioDoItem> = {}): FormularioDoItem {
  return {
    CASO_ID: 'CASO-1',
    escopo: 'RECURSO_EXTRAORDINARIO_ID',
    escopo_pai: null,
    item_id: 'EXT002',
    rotulo: null,
    pede_nome: false,
    completa: false,
    perguntas: [tipo, fabricar('B3.05C', 'TEXTO_CURTO')],
    posicao_do_item: 2,
    total_de_itens: 3,
    itens_concluidos: 1,
    trilha: null,
    ...extra,
  }
}

const ok = { avisos: [], abrir_fichas: [] } as unknown as ConfirmacaoDeResposta

function abrir(escopo = 'RECURSO_EXTRAORDINARIO_ID') {
  const onConcluir = vi.fn()
  render(
    <TelaFormulario
      casoId="CASO-1"
      escopo={escopo}
      itemId="EXT002"
      titulos={TITULOS_POR_ESCOPO[escopo]}
      onConcluir={onConcluir}
    />,
  )
  return onConcluir
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('T-314: ficha curta em uma tela', () => {
  it('mostra o aviso, a posição do item e a barra por itens concluídos (T-315, T-317)', async () => {
    vi.spyOn(api, 'obterFormulario').mockResolvedValue(formulario())
    abrir()

    expect(
      await screen.findByText('Cadastre um valor de cada vez. Depois você pode adicionar outros.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Valor extraordinário 2 de 3')).toBeInTheDocument()
    const barra = screen.getByRole('progressbar')
    expect(barra).toHaveAttribute('aria-valuenow', '1')
    expect(barra).toHaveAttribute('aria-valuetext', '1 de 3 concluídos')
    expect(screen.getByLabelText('Pergunta B3.05C')).toBeInTheDocument()
  })

  it('"Outro" mostra a descrição na mesma tela; trocar de opção esconde (T-315)', async () => {
    vi.spyOn(api, 'obterFormulario').mockResolvedValue(formulario())
    abrir()

    await userEvent.click(await screen.findByRole('radio', { name: 'Outro' }))
    expect(screen.getByLabelText('Pergunta B3.05AO')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: '13º salário' }))
    expect(screen.queryByLabelText('Pergunta B3.05AO')).toBeNull()
  })

  it('"Salvar" grava a mãe antes da filha e volta à lista com o item completo', async () => {
    vi.spyOn(api, 'obterFormulario')
      .mockResolvedValueOnce(formulario())
      .mockResolvedValueOnce(formulario({ completa: true }))
    const gravar = vi.spyOn(api, 'gravarResposta').mockResolvedValue(ok)
    const onConcluir = abrir()

    await userEvent.click(await screen.findByRole('radio', { name: 'Outro' }))
    await userEvent.type(screen.getByLabelText('Pergunta B3.05AO'), 'Venda')
    await userEvent.type(screen.getByLabelText('Pergunta B3.05C'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(onConcluir).toHaveBeenCalledWith('RECURSO_EXTRAORDINARIO_ID'))
    expect(gravar.mock.calls.map(([, entrada]) => [entrada.idPergunta, entrada.valor])).toEqual([
      ['B3.05A', 'OUTRO'],
      ['B3.05AO', 'Venda'],
      ['B3.05C', 'x'],
    ])
  })

  it('erro de um campo fica junto dele, os outros são gravados e a tela não sai', async () => {
    vi.spyOn(api, 'obterFormulario').mockResolvedValue(formulario())
    const gravar = vi
      .spyOn(api, 'gravarResposta')
      .mockRejectedValueOnce(new Error('Resposta não aceita: escolha uma opção.'))
      .mockResolvedValue(ok)
    const onConcluir = abrir()

    await userEvent.type(await screen.findByLabelText('Pergunta B3.05C'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Resposta não aceita: escolha uma opção.',
    )
    expect(gravar).toHaveBeenCalledTimes(2)
    expect(onConcluir).not.toHaveBeenCalled()
  })

  it('despesa não listada pede o nome no próprio formulário (T-316)', async () => {
    vi.spyOn(api, 'obterFormulario')
      .mockResolvedValueOnce(formulario({ escopo: 'ITEM_DESPESA', pede_nome: true, perguntas: [] }))
      .mockResolvedValueOnce(formulario({ completa: true }))
    const nomear = vi.spyOn(api, 'nomearFicha').mockResolvedValue({ rotulo: 'Pet' })
    const onConcluir = abrir('ITEM_DESPESA')

    expect(
      await screen.findByText(
        'Cadastre uma despesa de cada vez. Depois você pode adicionar outras.',
      ),
    ).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Nome da despesa'), 'Pet')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(onConcluir).toHaveBeenCalledWith('ITEM_DESPESA'))
    expect(nomear).toHaveBeenCalledWith('CASO-1', 'ITEM_DESPESA', 'EXT002', 'Pet')
  })
})

describe('T-314: a coleta e a lista levam ao formulário', () => {
  it('pergunta de ficha curta, na retomada, abre o formulário do item', async () => {
    vi.spyOn(api, 'obterProximaPergunta').mockResolvedValue({ pergunta: tipo })
    const abrirFormulario = vi.fn().mockReturnValue(true)
    render(
      <TelaPergunta casoId="CASO-1" onColetaCompleta={vi.fn()} abrirFormulario={abrirFormulario} />,
    )

    await waitFor(() => expect(abrirFormulario).toHaveBeenCalledWith(tipo))
  })

  it('na lista curta, adicionar abre o formulário do item novo, com o aviso', async () => {
    vi.spyOn(api, 'listarFichas').mockResolvedValue({
      fichas: [],
    } as unknown as Awaited<ReturnType<typeof api.listarFichas>>)
    vi.spyOn(api, 'criarFicha').mockResolvedValue({
      CASO_ID: 'CASO-1',
      escopo: 'ITEM_DESPESA',
      ficha: { item_id: 'DESP003', pede_nome: true } as Ficha,
    })
    const onAbrirFormulario = vi.fn()
    render(
      <TelaFichas
        casoId="CASO-1"
        escopo="ITEM_DESPESA"
        {...TITULOS_POR_ESCOPO.ITEM_DESPESA}
        onAbrirFicha={vi.fn()}
        onAbrirFormulario={onAbrirFormulario}
      />,
    )

    expect(
      await screen.findByText(
        'Cadastre uma despesa de cada vez. Depois você pode adicionar outras.',
      ),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '+ Adicionar despesa' }))
    await waitFor(() => expect(onAbrirFormulario).toHaveBeenCalledWith('ITEM_DESPESA', 'DESP003'))
  })
})
