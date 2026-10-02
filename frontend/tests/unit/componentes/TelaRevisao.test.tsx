// @vitest-environment happy-dom
/**
 * `TelaRevisao` — a fila em linguagem humana (`RF-111`, `AC-174`, `T-326`).
 *
 * Método, status e motivo vêm do servidor já rotulados; a tela não mostra
 * os códigos do motor nem o `MOTIVO_RECALCULO` técnico.
 */
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaRevisao from '../../../src/telas/TelaRevisao'
import * as api from '../../../src/services/api'
import type { ItemDaFila } from '../../../src/tipos'

afterEach(() => {
  vi.restoreAllMocks()
})

const ITEM: ItemDaFila = {
  CASO_ID: 'CASO-1',
  SNAPSHOT_ID: 'S1',
  versao: 1,
  DATA_REFERENCIA: '2026-10-01',
  MOTIVO_RECALCULO: 'Nenhum EVENTO_RECALCULO observado — (R-02, AC-13).',
  EVENTO_RECALCULO: null,
  METODO_RECOMENDADO_PIQ: 'HIBRIDO',
  STATUS_METODO: 'DEFINITIVO_NA_DATA',
  metodo: 'Híbrido',
  status_metodo: 'Definitivo na data',
  motivo: 'Primeiro cálculo, sem evento de recálculo',
  entra_por_politica: true,
  e_metodologico: false,
  ENGINE_VERSION: 'e',
  PARAMETROS_VERSION: 'p',
}

describe('TelaRevisao — linguagem humana (T-326)', () => {
  it('método, status e motivo por rótulo; nenhum código do motor', async () => {
    vi.spyOn(api, 'obterFilaDeRevisao').mockResolvedValue({ itens: [ITEM] })
    const { container } = render(<TelaRevisao aoSair={vi.fn()} />)

    expect(await screen.findByText('Híbrido')).toBeInTheDocument()
    expect(screen.getByText('Definitivo na data')).toBeInTheDocument()
    expect(screen.getByText('Primeiro cálculo, sem evento de recálculo')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/[A-Z]+_[A-Z_]+/)
  })
})
