// @vitest-environment happy-dom
/** Capítulo "Seu plano em números": linhas da projeção com prognóstico; três números sem ele. */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import PlanoDoAluno from '../../../src/componentes/PlanoDoAluno'
import type { Plano } from '../../../src/tipos'

const PROGNOSTICO = {
  titulo: 'Seu plano em números',
  introducao: 'Veja o que acontece em cada caminho.',
  caminhos: [
    {
      cor: 'azul' as const,
      titulo: 'Seguindo o seu plano',
      veredito: 'Você quita tudo em 14 meses.',
      nota: 'nota',
      marcador: 'dívida zero',
      destaques: [{ rotulo: 'Valor a mais por mês', valor: 'R$ 500,00' }],
      mes_fim: 14,
      escala: 14,
      mes_sombra: null,
      marcos: [],
      itens: [],
      rotulo_curto: 'Seu plano',
    },
  ],
  mes_a_mes: [],
}

const POSICAO = {
  posicao: 1,
  indice: 1,
  total: 1,
  DIVIDA_ID: 'D1',
  nome: 'Cartão',
  JUSTIFICATIVA_POSICAO: '',
  explicacao: '',
  fonte: null,
  orientacao_seguro: null,
  valores_de_apoio: [],
  incomodo: '',
  aviso_incomodo: '',
} as never

function plano(extra: Partial<Plano>): Plano {
  return {
    titulo: 'Plano',
    corpo: 'corpo',
    ordem: [],
    PRAZO_TOTAL: '14 meses',
    PRAZO_TOTAL_INT: 14,
    CUSTO_FUTURO_TOTAL: 'R$ 1,00',
    ENGINE_VERSION: 'e',
    PARAMETROS_VERSION: 'p',
    metodo: 'Avalanche',
    cenario: 'x',
    acoes: [],
    pendencias: null,
    MODO_ESTABILIZACAO: false,
    RESULTADO_CAIXA_OBSERVADO: '',
    reserva_mobilizavel: { pendente_de_decisao: false, valor: '' },
    cenario_adicional: null,
    nao_projetados: [],
    ...extra,
  } as Plano
}

describe('PlanoDoAluno — Seu plano em números', () => {
  it('com prognóstico mostra as linhas e não os três números', () => {
    render(<PlanoDoAluno plano={plano({ prognostico: PROGNOSTICO, ordem: [POSICAO] })} />)
    expect(screen.getByRole('heading', { name: 'Seu plano em números' })).toBeTruthy()
    expect(screen.getByText('Você quita tudo em 14 meses.')).toBeTruthy()
    expect(screen.queryByText('Se você seguir este plano')).toBeNull()
  })

  it('sem prognóstico (plano antigo) mantém os três números', () => {
    render(<PlanoDoAluno plano={plano({ prognostico: null })} />)
    expect(screen.getByText('Se você seguir este plano')).toBeTruthy()
    expect(screen.queryByText('Veja o que acontece em cada caminho.')).toBeNull()
  })
})
