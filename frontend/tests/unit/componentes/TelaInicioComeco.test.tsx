// @vitest-environment happy-dom
/**
 * `T-313` — "continuar" pressupõe que algo foi começado.
 *
 * Relato do produto (2026-10-01): com nenhuma resposta gravada, o Início e o
 * "Onde você está" ofereciam "Continuar de onde você parou". Quem decide se o
 * aluno começou é o servidor (`progresso.respondidas`).
 */
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaInicio from '../../../src/telas/TelaInicio'
import TelaProgresso from '../../../src/telas/TelaProgresso'
import * as api from '../../../src/services/api'
import type { Inicio } from '../../../src/tipos'

afterEach(() => {
  vi.restoreAllMocks()
})

function inicio(respondidas: number): Inicio {
  return {
    CASO_ID: 'CASO-1',
    estado: 'COLETA_INICIAL',
    fase: 'coleta',
    mensagem: 'Sua coleta está em andamento.',
    proxima_etapa: { destino: 'pergunta', ID_PERGUNTA: 'B1.01', item_id: null },
    progresso: { respondidas, total: 195 },
    valor_em_destaque: null,
    plano_liberado: false,
    versao_do_plano: null,
  } as Inicio
}

describe('Início — começar × continuar', () => {
  it('sem nenhuma resposta, oferece começar', () => {
    render(<TelaInicio inicio={inicio(0)} irPara={vi.fn()} eRevisor={false} aoSair={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Começar o questionário' })).toBeInTheDocument()
    expect(screen.queryByText(/de onde você parou/)).not.toBeInTheDocument()
  })

  it('com respostas, oferece continuar', () => {
    render(<TelaInicio inicio={inicio(3)} irPara={vi.fn()} eRevisor={false} aoSair={vi.fn()} />)

    expect(
      screen.getByRole('button', { name: 'Continuar de onde você parou' }),
    ).toBeInTheDocument()
  })
})

describe('Onde você está — começar × continuar', () => {
  it.each([
    [0, 'Começar o questionário'],
    [3, 'Continuar de onde parei'],
  ])('com %i respostas, o botão diz "%s"', async (respondidas, rotulo) => {
    vi.spyOn(api, 'listarEscopos').mockResolvedValue({ CASO_ID: 'CASO-1', escopos: [] })
    render(
      <TelaProgresso
        casoId="CASO-1"
        inicio={inicio(respondidas)}
        voltar={vi.fn()}
        continuar={vi.fn()}
      />,
    )

    expect(await screen.findByRole('button', { name: rotulo })).toBeInTheDocument()
  })
})
