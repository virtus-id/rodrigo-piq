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
