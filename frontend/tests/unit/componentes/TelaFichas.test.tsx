// @vitest-environment happy-dom
/**
 * `TelaFichas` — abrir uma ficha pela lista (`T-203`, `RF-53`).
 *
 * A ficha abre na pergunta que o SERVIDOR escolhe para aquele item
 * (`RF-45`): a tela pede a próxima com `item_id` e navega com o `ID` que
 * voltou. Nunca navega só com o `itemId`, que era o defeito.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaFichas from '../../../src/telas/TelaFichas'
import * as api from '../../../src/services/api'
import type { Pergunta, RespostaPergunta } from '../../../src/tipos'

afterEach(() => {
  vi.restoreAllMocks()
})

function montar(onAbrirFicha = vi.fn()) {
  vi.spyOn(api, 'listarFichas').mockResolvedValue({
    fichas: [{ item_id: 'D001', completa: false, campos: [] }],
  } as unknown as Awaited<ReturnType<typeof api.listarFichas>>)
  render(
    <TelaFichas
      casoId="CASO-1"
      escopo="DIVIDA_ID"
      titulo="Dívida"
      tituloPlural="Dívidas"
      onAbrirFicha={onAbrirFicha}
    />,
  )
  return onAbrirFicha
}

describe('TelaFichas — abrir ficha', () => {
  it('pede a próxima pergunta do item e navega com o ID devolvido', async () => {
    const obter = vi.spyOn(api, 'obterProximaPergunta').mockResolvedValue({
      pergunta: { ID: 'B5.A02', item_id: 'D001' } as Pergunta,
    } as RespostaPergunta)
    const onAbrirFicha = montar()

    await userEvent.click(await screen.findByRole('button', { name: 'Dívida D001' }))

    await waitFor(() => expect(onAbrirFicha).toHaveBeenCalledWith('D001', 'B5.A02'))
    expect(obter).toHaveBeenCalledWith('CASO-1', 'D001')
  })

  it('falha ao abrir mostra erro e não navega', async () => {
    vi.spyOn(api, 'obterProximaPergunta').mockRejectedValue(new Error('404'))
    const onAbrirFicha = montar()

    await userEvent.click(await screen.findByRole('button', { name: 'Dívida D001' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível abrir a ficha.')
    expect(onAbrirFicha).not.toHaveBeenCalled()
  })
})

describe('TelaFichas — continuar (T-212)', () => {
  it('"Continuar" segue sem exigir ficha', async () => {
    vi.spyOn(api, 'listarFichas').mockResolvedValue({
      fichas: [],
    } as unknown as Awaited<ReturnType<typeof api.listarFichas>>)
    const onContinuar = vi.fn()
    render(
      <TelaFichas
        casoId="CASO-1"
        escopo="RENDA_ADICIONAL_ID"
        titulo="Renda adicional"
        tituloPlural="Rendas adicionais"
        onAbrirFicha={vi.fn()}
        onContinuar={onContinuar}
      />,
    )

    await userEvent.click(await screen.findByRole('button', { name: 'Continuar' }))

    expect(onContinuar).toHaveBeenCalled()
  })
})

describe('TelaFichas — despesa por item (T-217)', () => {
  function montarDespesas() {
    vi.spyOn(api, 'listarFichas').mockResolvedValue({
      fichas: [
        { item_id: 'DESP001', rotulo: 'Aluguel', pede_nome: false, completa: false, campos: [] },
        { item_id: 'DESP002', rotulo: 'Outro', pede_nome: true, completa: false, campos: [] },
      ],
    } as unknown as Awaited<ReturnType<typeof api.listarFichas>>)
    render(
      <TelaFichas
        casoId="CASO-1"
        escopo="ITEM_DESPESA"
        titulo="Despesa"
        tituloPlural="Despesas"
        onAbrirFicha={vi.fn()}
      />,
    )
  }

  it('o título da ficha é o rótulo do item, não o identificador', async () => {
    montarDespesas()

    expect(await screen.findByRole('button', { name: 'Aluguel' })).toBeInTheDocument()
    expect(screen.queryByText(/DESP001/)).not.toBeInTheDocument()
  })

  it('só a ficha que pede nome tem o campo, e salvar envia o nome', async () => {
    const nomear = vi.spyOn(api, 'nomearFicha').mockResolvedValue({ rotulo: 'Jardineiro' })
    montarDespesas()

    const campo = await screen.findByLabelText('Nome da despesa')
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Jardineiro')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar nome' }))

    expect(screen.getAllByLabelText('Nome da despesa')).toHaveLength(1)
    await waitFor(() =>
      expect(nomear).toHaveBeenCalledWith('CASO-1', 'ITEM_DESPESA', 'DESP002', 'Jardineiro'),
    )
  })
})

describe('TelaFichas — margens dentro do vínculo (T-259)', () => {
  function montarVinculos() {
    vi.spyOn(api, 'listarFichas').mockResolvedValue({
      escopo_pai: null,
      escopos_filhos: ['MARGEM_ID'],
      fichas: [
        {
          item_id: 'V001',
          rotulo: null,
          pede_nome: false,
          completa: false,
          campos: [],
          margens: [
            { item_id: 'M001', rotulo: null, pede_nome: false, completa: true, campos: [] },
          ],
          dependentes: { margens: ['M001'], dividas: ['D002'] },
        },
        {
          item_id: 'V002',
          rotulo: null,
          pede_nome: false,
          completa: false,
          campos: [],
          margens: [
            { item_id: 'M002', rotulo: null, pede_nome: false, completa: false, campos: [] },
          ],
          dependentes: { margens: ['M002'], dividas: [] },
        },
      ],
    } as unknown as Awaited<ReturnType<typeof api.listarFichas>>)
    render(
      <TelaFichas
        casoId="CASO-1"
        escopo="VINCULO_ID"
        titulo="Vínculo"
        tituloPlural="Vínculos"
        onAbrirFicha={vi.fn()}
      />,
    )
  }

  it('cada margem aparece sob o seu vínculo e a nova é criada com o pai', async () => {
    const criar = vi.spyOn(api, 'criarFicha').mockResolvedValue(
      {} as Awaited<ReturnType<typeof api.criarFicha>>,
    )
    montarVinculos()

    const doV1 = await screen.findByRole('list', { name: 'Margens de Vínculo V001' })
    const doV2 = screen.getByRole('list', { name: 'Margens de Vínculo V002' })
    expect(doV1).toHaveTextContent('Margem M001')
    expect(doV1).not.toHaveTextContent('M002')
    expect(doV2).toHaveTextContent('Margem M002')
    expect(screen.queryByText(/total/i)).not.toBeInTheDocument()

    await userEvent.click(screen.getAllByRole('button', { name: '+ Adicionar margem' })[1])

    await waitFor(() => expect(criar).toHaveBeenCalledWith('CASO-1', 'MARGEM_ID', 'V002'))
  })

  it('remover vínculo lista os dependentes antes de confirmar', async () => {
    const remover = vi.spyOn(api, 'removerFicha').mockResolvedValue({ removido: 'V001' })
    montarVinculos()

    await userEvent.click(await screen.findByRole('button', { name: 'Remover Vínculo V001' }))

    const aviso = screen.getByRole('alertdialog')
    expect(aviso).toHaveTextContent('Margem M001')
    expect(aviso).toHaveTextContent('Dívida D002')
    expect(remover).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Remover assim mesmo' }))

    await waitFor(() => expect(remover).toHaveBeenCalledWith('CASO-1', 'VINCULO_ID', 'V001'))
  })

  it('a lista de margens sozinha não oferece criar margem sem vínculo', async () => {
    vi.spyOn(api, 'listarFichas').mockResolvedValue({
      escopo_pai: 'VINCULO_ID',
      escopos_filhos: [],
      fichas: [],
    } as unknown as Awaited<ReturnType<typeof api.listarFichas>>)
    render(
      <TelaFichas
        casoId="CASO-1"
        escopo="MARGEM_ID"
        titulo="Margem"
        tituloPlural="Margens"
        onAbrirFicha={vi.fn()}
      />,
    )

    await screen.findByText('Nenhuma ficha cadastrada ainda.')
    expect(screen.queryByRole('button', { name: /Adicionar margem/ })).not.toBeInTheDocument()
  })
})
