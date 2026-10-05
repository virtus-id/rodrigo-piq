// @vitest-environment happy-dom
/**
 * `T-342` (`RF-118`) — com plano liberado e o caso de volta à coleta, o plano
 * atual continua à vista e a tela diz por quê.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import TelaInicio from '../../../src/telas/TelaInicio'
import type { Inicio } from '../../../src/tipos'

function inicio(extra: Partial<Inicio>): Inicio {
  return {
    CASO_ID: 'CASO-1',
    estado: 'COLETA_INICIAL',
    fase: 'coleta',
    mensagem: 'Sua coleta está em andamento.',
    proxima_etapa: { destino: 'calculando', ID_PERGUNTA: null, item_id: null },
    progresso: { respondidas: 337, total: 337 },
    valor_em_destaque: null,
    plano_liberado: true,
    versao_do_plano: 1,
    correcao_pedida: null,
    ...extra,
  } as Inicio
}

const renderizar = (i: Inicio) =>
  render(<TelaInicio inicio={i} irPara={vi.fn()} eRevisor={false} aoSair={vi.fn()} />)

describe('Início — plano novo depois da liberação', () => {
  it('em coleta COM plano liberado: "Ver meu plano" continua e a nota explica', () => {
    renderizar(inicio({}))

    expect(screen.getByRole('button', { name: 'Ver meu plano' })).toBeInTheDocument()
    expect(screen.getByText('Seu plano atual continua disponível.')).toBeInTheDocument()
  })

  it('primeira coleta (sem plano liberado): nada disso aparece', () => {
    renderizar(inicio({ plano_liberado: false, versao_do_plano: null }))

    expect(screen.queryByRole('button', { name: 'Ver meu plano' })).not.toBeInTheDocument()
    expect(screen.queryByText('Seu plano atual continua disponível.')).not.toBeInTheDocument()
  })
})
