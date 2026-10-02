// @vitest-environment happy-dom
/**
 * `TelaOperador` — o caso pelo e-mail do aluno (`RF-111` e, `T-327`).
 *
 * O e-mail é a identificação principal; o `CASO_ID` fica como detalhe
 * discreto, e é o que sobra quando a conta não tem e-mail.
 */
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaOperador from '../../../src/telas/TelaOperador'
import * as api from '../../../src/services/api'
import type { LinhaDoPainel } from '../../../src/services/api'

afterEach(() => {
  vi.restoreAllMocks()
})

const LINHA: LinhaDoPainel = {
  CASO_ID: 'CASO-1',
  estado: 'COLETA_INICIAL',
  aguardando_revisao: false,
  tempo_desde_ultima_atividade: 'há 2 horas',
}

describe('TelaOperador — o caso pelo e-mail do aluno (T-327, RF-111)', () => {
  it('linha pelo e-mail; o CASO_ID fica como detalhe discreto', async () => {
    vi.spyOn(api, 'obterPainelDoOperador').mockResolvedValue({
      linhas: [{ ...LINHA, email_do_aluno: 'fulano@exemplo.com' }],
    })
    render(<TelaOperador voltar={vi.fn()} />)

    expect(await screen.findByText('fulano@exemplo.com')).toHaveClass('font-bold')
    expect(screen.getByText('CASO-1').tagName).toBe('SMALL')
  })

  it('sem e-mail, cai no CASO_ID', async () => {
    vi.spyOn(api, 'obterPainelDoOperador').mockResolvedValue({
      linhas: [{ ...LINHA, email_do_aluno: null }],
    })
    render(<TelaOperador voltar={vi.fn()} />)

    expect(await screen.findByText('CASO-1')).toHaveClass('font-bold')
  })
})
