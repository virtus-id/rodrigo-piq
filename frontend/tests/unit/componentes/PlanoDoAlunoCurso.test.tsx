// @vitest-environment happy-dom
/**
 * `PlanoDoAluno` — curso de entrada, aviso de plano sem valor extra, nota de
 * incômodo e respostas de risco do revisor (`T-352` a `T-354`).
 *
 * Todo texto vem do servidor; o componente só o mostra e some com o que
 * chega vazio.
 */
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import PlanoDoAluno from '../../../src/componentes/PlanoDoAluno'
import type { Plano } from '../../../src/tipos'

const CURSO = {
  introducao_titulo: 'O curso Servidor Sem Dívidas e o seu plano',
  introducao: 'Recomendamos fortemente que você faça o curso.',
  quadro_titulo: 'Aulas do curso que ajudam no seu plano',
  aulas: [
    { numero: '12', titulo: 'Métodos de Quitação', motivo: 'Explica como concentrar o extra.' },
  ],
  melhorar_titulo: 'Como melhorar o seu plano',
  melhorar_intro: 'Não existe percentual que sirva para todo mundo.',
  melhorar: [{ texto: 'Reduzir despesas.', aula: 'Aula 5' }],
}

function plano(extra: Partial<Plano> = {}, incomodo = '', aviso = ''): Plano {
  return {
    titulo: 'Plano',
    corpo: 'corpo',
    ordem: [
      {
        posicao: 2,
        indice: 2,
        total: 2,
        DIVIDA_ID: 'D002',
        nome: 'Empréstimo consignado',
        JUSTIFICATIVA_POSICAO: '',
        explicacao: 'Critério do método.',
        fonte: null,
        orientacao_seguro: null,
        valores_de_apoio: [],
        incomodo,
        aviso_incomodo: aviso,
        fatos_de_risco: [{ nome: 'Tempo de atraso', valor: '4 a 6 meses' }],
      },
    ],
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

describe('PlanoDoAluno — curso de entrada', () => {
  it('mostra a introdução, a aula e as orientações sem percentual', () => {
    render(<PlanoDoAluno plano={plano({ curso_ssd: CURSO })} />)

    const secao = screen.getByRole('region', { name: CURSO.introducao_titulo })
    expect(within(secao).getByText(CURSO.introducao)).toBeInTheDocument()
    expect(within(secao).getByText(/Aula 12: Métodos de Quitação/)).toBeInTheDocument()
    expect(within(secao).getByText(CURSO.melhorar_intro)).toBeInTheDocument()
    expect(within(secao).getByText(/Reduzir despesas\./)).toBeInTheDocument()
  })

  it('some quando o servidor não manda o curso', () => {
    render(<PlanoDoAluno plano={plano({ curso_ssd: null })} />)
    expect(screen.queryByText(/Servidor Sem Dívidas/)).not.toBeInTheDocument()
  })
})

describe('PlanoDoAluno — sem valor extra', () => {
  it('mostra o aviso só quando ele vem preenchido', () => {
    const { rerender } = render(
      <PlanoDoAluno plano={plano({ aviso_sem_valor_extra: 'Neste mês não há valor extra.' })} />,
    )
    expect(screen.getByText('Neste mês não há valor extra.')).toBeInTheDocument()

    rerender(<PlanoDoAluno plano={plano({ aviso_sem_valor_extra: '' })} />)
    expect(screen.queryByText(/não há valor extra/)).not.toBeInTheDocument()
  })
})

describe('PlanoDoAluno — nota de incômodo', () => {
  it('mostra a nota e o aviso na dívida', () => {
    render(
      <PlanoDoAluno
        plano={plano({}, 'Você deu nota 9 de incômodo a esta dívida.', 'Avise a nossa equipe.')}
      />,
    )
    expect(
      screen.getByText(/Você deu nota 9 de incômodo a esta dívida\. Avise a nossa equipe\./),
    ).toBeInTheDocument()
  })

  it('não mostra nada quando a nota vem vazia', () => {
    render(<PlanoDoAluno plano={plano()} />)
    expect(screen.queryByText(/nota .* de incômodo/)).not.toBeInTheDocument()
  })

  it('o aluno nunca vê as respostas de risco; o revisor, sim', () => {
    const { rerender } = render(<PlanoDoAluno plano={plano()} />)
    expect(screen.queryByText(/Tempo de atraso/)).not.toBeInTheDocument()

    rerender(
      <PlanoDoAluno
        plano={plano()}
        revisor={{
          entradas: {
            campos: [],
            perfil_comportamental: [],
            sinais_comportamentais: [],
            dividas: [],
          },
        }}
      />,
    )
    expect(screen.getByText(/Tempo de atraso/)).toBeInTheDocument()
    expect(screen.getByText('4 a 6 meses')).toBeInTheDocument()
  })
})
