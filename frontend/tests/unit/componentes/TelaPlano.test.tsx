// @vitest-environment happy-dom
/**
 * `TelaPlano` — o cenário adicional em seção própria (`RF-98`, `AC-152`,
 * `T-277`).
 *
 * Os números do cenário adicional são diferentes dos do plano de propósito:
 * se algum deles aparecer no resumo ou na ordem, o teste pega a mistura.
 */
import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaPlano from '../../../src/telas/TelaPlano'
import * as api from '../../../src/services/api'
import type { CenarioAdicional, Plano, PosicaoDaOrdem } from '../../../src/tipos'

afterEach(() => {
  vi.restoreAllMocks()
})

const ADICIONAL: CenarioAdicional = {
  rotulo: 'Cenário adicional: se os valores incertos chegarem',
  explicacao: 'Só passam a contar quando forem recebidos.',
  PRAZO_TOTAL: '9 meses',
  CUSTO_FUTURO_TOTAL: 'R$ 1.111,11',
  ordem: ['D002', 'D001'],
  itens: [{ ITEM_ID: 'EXT001', mes: 3, valor: 'R$ 2.000,00' }],
}

function plano(
  cenario_adicional: CenarioAdicional | null,
  orientacao_seguro: string | null = null,
): Plano {
  return {
    titulo: 'Sua ordem projetada de quitação',
    corpo: 'corpo',
    ordem: [
      {
        posicao: 1,
        indice: 1,
        total: 1,
        DIVIDA_ID: 'D001',
        nome: 'Cheque especial — CAIXA ECONOMICA FEDERAL',
        JUSTIFICATIVA_POSICAO: 'j',
        explicacao: 'e',
        fonte: null,
        orientacao_seguro,
        valores_de_apoio: [],
      },
    ],
    PRAZO_TOTAL: '14 meses',
    PRAZO_TOTAL_INT: 14,
    CUSTO_FUTURO_TOTAL: 'R$ 3.333,33',
    ENGINE_VERSION: 'e',
    PARAMETROS_VERSION: 'p',
    metodo: 'Avalanche',
    cenario: 'Ordem de quitação publicada',
    acoes: [],
    pendencias: null,
    MODO_ESTABILIZACAO: false,
    RESULTADO_CAIXA_OBSERVADO: '',
    reserva_mobilizavel: { pendente_de_decisao: true, valor: '' },
    cenario_adicional,
    nao_projetados: [],
  }
}

function mostrar(cenario_adicional: CenarioAdicional | null) {
  vi.spyOn(api, 'obterPlano').mockResolvedValue({
    CASO_ID: 'CASO-1',
    estado: 'LIBERADO',
    plano: plano(cenario_adicional),
  })
  return render(<TelaPlano casoId="CASO-1" />)
}

describe('TelaPlano — cenário adicional (AC-152)', () => {
  it('aparece em seção própria, rotulada, abaixo do plano', async () => {
    mostrar(ADICIONAL)

    const secao = await screen.findByRole('region', { name: ADICIONAL.rotulo })
    expect(within(secao).getByText('9 meses')).toBeInTheDocument()
    expect(within(secao).getByText('R$ 1.111,11')).toBeInTheDocument()
    expect(within(secao).getByText('R$ 2.000,00 no Mês 3')).toBeInTheDocument()
    // Plano amigável (2026-10-03): o código do item (`EXT001`) não aparece
    // ao aluno — só o revisor recebe (`para_revisor=True`), a mesma
    // disciplina de `DIVIDA_ID`/`JUSTIFICATIVA_POSICAO` (T-305/T-306).
    expect(secao.textContent).not.toMatch(/EXT001/)
  })

  it('nenhum número do cenário adicional fora da sua seção', async () => {
    const { container } = mostrar(ADICIONAL)

    const secao = await screen.findByRole('region', { name: ADICIONAL.rotulo })
    const fora = container.cloneNode(true) as HTMLElement
    fora.querySelector('section[aria-labelledby="titulo-cenario-adicional"]')?.remove()
    for (const numero of ['9 meses', 'R$ 1.111,11', 'R$ 2.000,00']) {
      expect(fora.textContent).not.toContain(numero)
    }
    expect(fora.textContent).toContain('14 meses')
    expect(within(secao).queryByText('14 meses')).not.toBeInTheDocument()
  })

  it('ausente quando null', async () => {
    mostrar(null)

    await screen.findByText('14 meses')
    expect(screen.queryByText(/Cenário adicional/)).not.toBeInTheDocument()
  })
})

describe('TelaPlano — orientação do seguro prestamista (RF-82, T-245)', () => {
  it('aparece na dívida quando o servidor manda o texto', async () => {
    vi.spyOn(api, 'obterPlano').mockResolvedValue({
      CASO_ID: 'CASO-1',
      estado: 'LIBERADO',
      plano: plano(null, 'Esta dívida tem seguro prestamista.'),
    })
    render(<TelaPlano casoId="CASO-1" />)

    expect(await screen.findByText('Esta dívida tem seguro prestamista.')).toBeInTheDocument()
  })

  it('ausente quando null', async () => {
    mostrar(null)

    await screen.findByText('14 meses')
    expect(screen.queryByText(/seguro prestamista/)).not.toBeInTheDocument()
  })
})

describe('TelaPlano — mês de quitação e valor mensal (T-304, DE-08)', () => {
  function mostrarCom(posicao: Partial<PosicaoDaOrdem>, extra: Partial<Plano> = {}) {
    const base = plano(null)
    vi.spyOn(api, 'obterPlano').mockResolvedValue({
      CASO_ID: 'CASO-1',
      estado: 'LIBERADO',
      plano: { ...base, ...extra, ordem: [{ ...base.ordem[0], ...posicao }] },
    })
    return render(<TelaPlano casoId="CASO-1" />)
  }

  /** O cartão da dívida (o `<li>` que contém o nome dela). */
  async function cartaoDaDivida() {
    const nome = await screen.findByText('Cheque especial — CAIXA ECONOMICA FEDERAL')
    const cartao = nome.closest('li')
    expect(cartao).not.toBeNull()
    return cartao as HTMLElement
  }

  it('mostra o mês previsto de cada dívida e o valor mensal destinado', async () => {
    mostrarCom({ mes_de_quitacao: 7 }, { valor_mensal_destinado: 'R$ 500,00' })

    // Revisão de design (2026-10-03): o mês de quitação é um quadro do
    // cartão da dívida ("Termina no" / "Mês 7"), à vista, como no PDF.
    const cartao = await cartaoDaDivida()
    expect(within(cartao).getByText('Termina no')).toBeInTheDocument()
    expect(within(cartao).getByText('Mês 7')).toBeInTheDocument()
    expect(screen.getByText('a mais todo mês, além das parcelas')).toBeInTheDocument()
    expect(screen.getByText('R$ 500,00')).toBeInTheDocument()
  })

  it('sem o dado no snapshot, "não disponível" — nunca um mês estimado', async () => {
    mostrarCom({ mes_de_quitacao: null })

    const cartao = await cartaoDaDivida()
    expect(within(cartao).getByText('Termina no')).toBeInTheDocument()
    expect(within(cartao).getByText('não disponível')).toBeInTheDocument()
    expect(within(cartao).queryByText(/^Mês \d+$/)).not.toBeInTheDocument()
  })
})

describe('TelaPlano — sem texto técnico ao aluno (T-305)', () => {
  it('mostra a explicação; a JUSTIFICATIVA_POSICAO não aparece nem como fallback', async () => {
    const base = plano(null)
    vi.spyOn(api, 'obterPlano').mockResolvedValue({
      CASO_ID: 'CASO-1',
      estado: 'LIBERADO',
      plano: {
        ...base,
        ordem: [
          {
            ...base.ordem[0],
            explicacao: '',
            JUSTIFICATIVA_POSICAO: 'critério: maior BENEFICIO_MARGINAL_AMORTIZACAO (O-01)',
          },
        ],
      },
    })
    const { container } = render(<TelaPlano casoId="CASO-1" />)

    await screen.findByText('14 meses')
    expect(container.textContent).not.toContain('BENEFICIO_MARGINAL_AMORTIZACAO')
  })
})

describe('TelaPlano — linguagem humana (T-326, RF-111, AC-174; T-306)', () => {
  it('a dívida aparece por "tipo — credor"; o código não aparece', async () => {
    const { container } = mostrar(null)

    expect(
      await screen.findByText('Cheque especial — CAIXA ECONOMICA FEDERAL'),
    ).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\bD0\d\d\b/)
  })

  it('o carimbo traz o rótulo do método, não o código do cenário', async () => {
    mostrar(null)

    expect(await screen.findByText(/método Avalanche/)).toBeInTheDocument()
    expect(screen.queryByText(/Ordem de quitação publicada/)).not.toBeInTheDocument()
  })

  it('ordem vazia: a ação em português com o nome da dívida, sem método no carimbo', async () => {
    const base = plano(null)
    vi.spyOn(api, 'obterPlano').mockResolvedValue({
      CASO_ID: 'CASO-1',
      estado: 'LIBERADO',
      plano: {
        ...base,
        ordem: [],
        acoes: [
          {
            DIVIDA_ID: 'D001',
            nome_divida: 'Cartão de crédito — saldo rotativo — NUBANK',
            descricao: 'Informar o dado que falta desta dívida.',
            prioridade_excepcional: false,
          },
        ],
        pendencias: {
          inventario_incompleto: false,
          campos_faltantes_por_divida: [
            {
              DIVIDA_ID: 'D001',
              nome: 'Cartão de crédito — saldo rotativo — NUBANK',
              campos: ['quanto você ainda deve'],
            },
          ],
        },
      },
    })
    const { container } = render(<TelaPlano casoId="CASO-1" />)

    expect(await screen.findByText('Informar o dado que falta desta dívida.')).toBeInTheDocument()
    expect(
      screen.getByText('Cartão de crédito — saldo rotativo — NUBANK: falta quanto você ainda deve'),
    ).toBeInTheDocument()
    expect(container.textContent).not.toContain('D001')
    expect(container.textContent).not.toContain('método')
  })
})
