// @vitest-environment happy-dom
/**
 * `TelaOperador` — o Painel de usuários (`RF-112`, `T-331`; e-mail do aluno
 * de `RF-111` e, `T-327`).
 *
 * Tabela Nome · E-mail · Etapa · Status, uma linha por aluno. A etapa chega
 * do servidor por rótulo — a tela não traduz código. Nome do comprador na
 * Hotmart (`T-332`, `OQ-68`); sem nome, "—".
 */
import { render, screen, within } from '@testing-library/react'
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
  etapa: 'Respondendo o questionário · Parte 2 de 5 · Como você controla os gastos',
  aguardando_revisao: false,
  tempo_desde_ultima_atividade: 'há 2 horas',
}

describe('TelaOperador — Painel de usuários (T-331, RF-112)', () => {
  it('título e tabela Nome · E-mail · Etapa · Status', async () => {
    vi.spyOn(api, 'obterPainelDoOperador').mockResolvedValue({
      linhas: [{ ...LINHA, email_do_aluno: 'fulano@exemplo.com' }],
    })
    render(<TelaOperador voltar={vi.fn()} />)

    const tabela = await screen.findByRole('table')
    expect(screen.getByRole('heading', { level: 1, name: 'Painel de usuários' })).toBeTruthy()
    const colunas = within(tabela)
      .getAllByRole('columnheader')
      .map((th) => th.textContent)
    expect(colunas).toEqual(['Nome', 'E-mail', 'Etapa', 'Status'])
    expect(within(tabela).getAllByRole('columnheader')[0]).toHaveAttribute('scope', 'col')
  })

  it('a linha traz nome, e-mail, etapa por rótulo (nunca o código) e o tempo parado', async () => {
    vi.spyOn(api, 'obterPainelDoOperador').mockResolvedValue({
      linhas: [{ ...LINHA, nome_do_aluno: 'Fulano de Tal', email_do_aluno: 'fulano@exemplo.com' }],
    })
    render(<TelaOperador voltar={vi.fn()} />)

    const linha = (await screen.findAllByRole('row'))[1]
    const celulas = within(linha).getAllByRole('cell')
    expect(celulas[0]).toHaveTextContent('Fulano de Tal')
    expect(celulas[1]).toHaveTextContent('fulano@exemplo.com')
    expect(celulas[2]).toHaveTextContent(LINHA.etapa)
    expect(celulas[3]).toHaveTextContent('parado há 2 horas')
    expect(linha).not.toHaveTextContent('COLETA_INICIAL')
    expect(linha).not.toHaveTextContent('CASO-1')
  })

  it('status combina aguarda conferência e cálculo bloqueado', async () => {
    vi.spyOn(api, 'obterPainelDoOperador').mockResolvedValue({
      linhas: [
        {
          ...LINHA,
          aguardando_revisao: true,
          bloqueio_inventario: ['DIVIDA_SEM_SALDO'],
          tempo_desde_ultima_atividade: 'agora mesmo',
        },
      ],
    })
    render(<TelaOperador voltar={vi.fn()} />)

    const status = within((await screen.findAllByRole('row'))[1]).getAllByRole('cell')[3]
    expect(status).toHaveTextContent('Aguarda conferência')
    expect(status).toHaveTextContent('Cálculo bloqueado: inventário incompleto')
    expect(status).toHaveTextContent('agora mesmo')
  })

  it('sem e-mail, cai no CASO_ID', async () => {
    vi.spyOn(api, 'obterPainelDoOperador').mockResolvedValue({
      linhas: [{ ...LINHA, email_do_aluno: null }],
    })
    render(<TelaOperador voltar={vi.fn()} />)

    expect(await screen.findByText('CASO-1')).toBeTruthy()
  })

  it('sem nome, a célula Nome mostra "—" (T-332)', async () => {
    vi.spyOn(api, 'obterPainelDoOperador').mockResolvedValue({
      linhas: [{ ...LINHA, email_do_aluno: 'fulano@exemplo.com', nome_do_aluno: null }],
    })
    render(<TelaOperador voltar={vi.fn()} />)

    const celulas = within((await screen.findAllByRole('row'))[1]).getAllByRole('cell')
    expect(celulas[0]).toHaveTextContent('—')
  })

  it('nenhum aluno: estado vazio, sem tabela', async () => {
    vi.spyOn(api, 'obterPainelDoOperador').mockResolvedValue({ linhas: [] })
    render(<TelaOperador voltar={vi.fn()} />)

    expect(await screen.findByText('Nenhum aluno no piloto ainda.')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
  })
})
