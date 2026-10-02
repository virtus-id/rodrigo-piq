// @vitest-environment happy-dom
/**
 * `T-313` — "continuar" pressupõe que algo foi começado.
 *
 * Relato do produto (2026-10-01): com nenhuma resposta gravada, o Início e o
 * "Onde você está" ofereciam "Continuar de onde você parou". Quem decide se o
 * aluno começou é o servidor (`progresso.respondidas`).
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

describe('Início — correção pedida pela conferência (T-333, RF-113)', () => {
  const devolvido = {
    ...inicio(40),
    mensagem: 'Seu plano voltou para você conferir.',
    proxima_etapa: { destino: 'calculando', ID_PERGUNTA: null, item_id: null },
    correcao_pedida: {
      mensagem: 'Informe a taxa do cheque especial',
      dados_a_conferir: [
        {
          nome: 'Cheque especial — CAIXA ECONOMICA FEDERAL',
          enunciado: 'Você sabe qual é a taxa de juros desta operação?',
          ID_PERGUNTA: 'B5.D01',
          item_id: 'D001',
        },
      ],
    },
  } as Inicio

  it('mostra a mensagem, os dados a conferir e o reenvio', () => {
    render(<TelaInicio inicio={devolvido} irPara={vi.fn()} eRevisor={false} aoSair={vi.fn()} />)

    expect(screen.getByText('Seu plano voltou para você conferir.')).toBeInTheDocument()
    expect(screen.getByText('Informe a taxa do cheque especial')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Enviar para nova conferência' }),
    ).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/em revisão|\bD0\d\d\b|\bB\d+\.[A-Z0-9]+\b/)
  })

  it('cada dado leva à pergunta pela rota de correção; o reenvio, ao cálculo', async () => {
    const irPara = vi.fn()
    render(<TelaInicio inicio={devolvido} irPara={irPara} eRevisor={false} aoSair={vi.fn()} />)

    await userEvent.click(
      screen.getByRole('button', {
        name: 'Cheque especial — CAIXA ECONOMICA FEDERAL · Você sabe qual é a taxa de juros desta operação?',
      }),
    )
    expect(irPara).toHaveBeenCalledWith({ tela: 'respostas', idPergunta: 'B5.D01', itemId: 'D001' })

    await userEvent.click(screen.getByRole('button', { name: 'Enviar para nova conferência' }))
    expect(irPara).toHaveBeenLastCalledWith({ tela: 'calculando' })
  })

  it('sem correção pedida, nenhum aviso', () => {
    render(<TelaInicio inicio={inicio(3)} irPara={vi.fn()} eRevisor={false} aoSair={vi.fn()} />)

    expect(screen.queryByText(/voltou para você/)).not.toBeInTheDocument()
  })
})
