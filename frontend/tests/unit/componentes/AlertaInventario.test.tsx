// @vitest-environment happy-dom
/**
 * `AlertaInventario` — o alerta permanente de inventário incompleto
 * (`RF-86`, `RF-87`, `AC-133`, `AC-154`, T-251).
 *
 * O componente só mostra o que o servidor devolveu: mensagem e ações por
 * pendência; sem pendência, nada no DOM.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import AlertaInventario, { ContextoDoAlerta } from '../../../src/componentes/AlertaInventario'
import * as api from '../../../src/services/api'

afterEach(() => {
  vi.restoreAllMocks()
})

const FALTANDO: api.PendenciaDeInventario = {
  tipo: 'INVENTARIO',
  codigo: 'DIVIDAS_FALTANDO',
  ID: 'B5.00',
  ID_PARA_CORRIGIR: 'B5.00',
  item_id: null,
  escopo: 'DIVIDA_ID',
  enunciado: 'Você declarou 7 dívidas e cadastrou 5. Faltam 2 fichas.',
  mensagem: 'Você declarou 7 dívidas e cadastrou 5. Faltam 2 fichas.',
}

function montar(pendencias: api.PendenciaDeInventario[], irPara = vi.fn()) {
  const obter = vi.spyOn(api, 'obterInventario').mockResolvedValue({ pendencias })
  const utilidades = render(
    <ContextoDoAlerta.Provider value={{ casoId: 'CASO-1', irPara, navegacao: { tela: 'inicio' } }}>
      <AlertaInventario />
    </ContextoDoAlerta.Provider>,
  )
  return { irPara, obter, ...utilidades }
}

describe('AlertaInventario', () => {
  it('AC-133: anuncia a mensagem do servidor, com uma ação por pendência', async () => {
    const { irPara } = montar([FALTANDO])

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent('Você declarou 7 dívidas e cadastrou 5. Faltam 2 fichas.')

    const cadastrar = screen.getByRole('button', { name: 'Cadastrar as fichas' })
    expect(cadastrar).toHaveAccessibleDescription(FALTANDO.mensagem)
    await userEvent.click(cadastrar)
    expect(irPara).toHaveBeenCalledWith({ tela: 'fichas', escopo: 'DIVIDA_ID' })

    await userEvent.click(screen.getByRole('button', { name: 'Corrigir a resposta' }))
    expect(irPara).toHaveBeenCalledWith({ tela: 'respostas', idPergunta: 'B5.00' })
  })

  it('AC-154: pendência sem escopo oferece só a correção da declaração', async () => {
    montar([{ ...FALTANDO, codigo: 'DIVIDAS_ACIMA', escopo: null, mensagem: 'Acima.' }])

    await screen.findByRole('alert')
    expect(screen.queryByRole('button', { name: 'Cadastrar as fichas' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Corrigir a resposta' })).toBeInTheDocument()
  })

  it('sem pendência, nada é renderizado', async () => {
    const { obter, container } = montar([])

    await waitFor(() => expect(obter).toHaveBeenCalledWith('CASO-1'))
    expect(container).toBeEmptyDOMElement()
  })

  it('fora do contexto de um caso (tela da equipe, testes da casca), nada', () => {
    const { container } = render(<AlertaInventario />)
    expect(container).toBeEmptyDOMElement()
  })
})
