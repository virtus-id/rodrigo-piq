// @vitest-environment happy-dom
/**
 * `TelaEquipeCaso` — pendências de homologação e fontes (`T-266`, `RF-93`,
 * `AC-142`, `AC-155`).
 *
 * A lista e os rótulos vêm do servidor (`GET .../decisao`); a tela só os
 * mostra e desabilita "Liberar" — a recusa de verdade é o `409`.
 */
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaEquipeCaso from '../../../src/telas/TelaEquipeCaso'
import * as api from '../../../src/services/api'
import type { CasoParaRevisao, OpcoesDeDecisao } from '../../../src/services/api'

afterEach(() => {
  vi.restoreAllMocks()
})

const CASO = {
  CASO_ID: 'CASO-1',
  plano: {
    titulo: 'Sua ordem projetada de quitação',
    corpo: '',
    ordem: [],
    PRAZO_TOTAL: '',
    CUSTO_FUTURO_TOTAL: '',
    ENGINE_VERSION: 'e',
    PARAMETROS_VERSION: 'p',
    cenario: '',
    acoes: [],
    pendencias: null,
    MODO_ESTABILIZACAO: false,
    RESULTADO_CAIXA_OBSERVADO: '',
    reserva_mobilizavel: { pendente_de_decisao: false, valor: null },
  },
  estado_inputs: { campos: [], perfil_comportamental: [], sinais_comportamentais: [], dividas: [] },
  fila: {
    CASO_ID: 'CASO-1',
    SNAPSHOT_ID: 'S1',
    versao: 1,
    DATA_REFERENCIA: '2026-09-30',
    MOTIVO_RECALCULO: null,
    EVENTO_RECALCULO: null,
    METODO_RECOMENDADO_PIQ: 'AVALANCHE',
    STATUS_METODO: 'DEFINITIVO_NA_DATA',
    metodo: 'Avalanche',
    status_metodo: 'Definitivo na data',
    motivo: 'Primeiro cálculo, sem evento de recálculo',
    entra_por_politica: true,
    e_metodologico: false,
    ENGINE_VERSION: 'e',
    PARAMETROS_VERSION: 'p',
  },
} as unknown as CasoParaRevisao

function montar(opcoes: OpcoesDeDecisao, caso: CasoParaRevisao = CASO) {
  vi.spyOn(api, 'obterCasoParaRevisao').mockResolvedValue(caso)
  vi.spyOn(api, 'obterOpcoesDeDecisao').mockResolvedValue(opcoes)
  render(<TelaEquipeCaso casoId="CASO-1" voltar={vi.fn()} />)
}

describe('TelaEquipeCaso — pendências de homologação (T-266)', () => {
  it('lista cada pendência nomeando dívida e dado, e desabilita Liberar', async () => {
    montar({
      classificacoes_erro: [],
      fontes: [
        { item_id: 'D001', origem: 'B5.I02', nivel: 'PENDENTE_DE_CONFIRMACAO', rotulo: 'Pendente de confirmação' },
      ],
      seguros_nao_informados: ['D001'],
      rotulo_nao_informado: 'Não informado',
      pendencias_homologacao: [
        {
          item_id: 'D001',
          ID_PERGUNTA: 'B5.B03',
          enunciado: 'Qual é o saldo devedor atual desta dívida?',
          motivo: 'PENDENTE_DE_CONFIRMACAO',
        },
      ],
    })

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent('D001 · Qual é o saldo devedor atual desta dívida?')
    expect(screen.getByRole('button', { name: 'Liberar para o aluno' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Pedir correção' })).toBeEnabled()
    expect(screen.getByText('D001 · B5.I02: Pendente de confirmação')).toBeInTheDocument()
    expect(screen.getByText('D001 · seguro: Não informado')).toBeInTheDocument()
  })

  it('sem pendência, Liberar fica disponível', async () => {
    montar({ classificacoes_erro: [], pendencias_homologacao: [] })

    expect(await screen.findByRole('button', { name: 'Liberar para o aluno' })).toBeEnabled()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('TelaEquipeCaso — registro de homologação (T-304, RF-96)', () => {
  it('mostra os cinco itens de DE-08, com "não disponível" e o motivo', async () => {
    montar({
      classificacoes_erro: [],
      pendencias_homologacao: [],
      homologacao: {
        homologavel: true,
        itens: {
          ordem_final_de_ataque: { valor: ['D002', 'D001'], origem: ['o'], motivo: null },
          mes_de_quitacao_por_divida: { valor: { D002: 4, D001: 9 }, origem: ['o'], motivo: null },
          valor_mensal_destinado: { valor: 'R$ 500,00', origem: ['o'], motivo: null },
          custo_total_de_juros: { valor: 'R$ 321,00', origem: ['o'], motivo: null },
          uso_da_reserva: {
            valor: 'não disponível',
            origem: [],
            motivo: 'RESERVA_RECOMENDADA não gravada (R9-6)',
          },
        },
      },
    })

    const secao = await screen.findByRole('region', { name: 'Registro de homologação' })
    expect(secao).toHaveTextContent('Ordem final de ataqueD002 → D001')
    expect(secao).toHaveTextContent('D002: mês 4 · D001: mês 9')
    expect(secao).toHaveTextContent('Valor mensal destinadoR$ 500,00')
    expect(secao).toHaveTextContent('Custo total de jurosR$ 321,00')
    expect(secao).toHaveTextContent('não disponívelRESERVA_RECOMENDADA não gravada (R9-6)')
    expect(secao).toHaveTextContent('Pode ser homologadosim')
  })
})

describe('TelaEquipeCaso — linguagem humana (T-326, RF-111, AC-174)', () => {
  const JUSTIFICATIVA =
    'Posição 1: D011 — método HIBRIDO, critério: D_ESTRELA prioritária (H-05, H-06, H-07).'

  function casoComDados(): CasoParaRevisao {
    return {
      ...CASO,
      plano: {
        ...CASO.plano,
        ordem: [
          {
            posicao: 1,
            indice: 1,
            total: 1,
            DIVIDA_ID: 'D011',
            nome: 'Cheque especial — CAIXA ECONOMICA FEDERAL',
            JUSTIFICATIVA_POSICAO: JUSTIFICATIVA,
            explicacao: 'É a dívida que mais destrava o seu orçamento agora.',
            valores_de_apoio: [],
          },
        ],
      },
      estado_inputs: {
        campos: [
          { nome: 'Renda total recorrente', valor: 'R$ 10.350,92', codigo: 'RENDA_TOTAL_RECORRENTE' },
        ],
        perfil_comportamental: [
          { nome: 'Registro dos gastos', valor: 'A maior parte, mas alguns ficam de fora.', codigo: 'REGISTRO_GASTOS' },
        ],
        sinais_comportamentais: [],
        dividas: [
          {
            DIVIDA_ID: 'D011',
            nome: 'Cheque especial — CAIXA ECONOMICA FEDERAL',
            campos: [{ nome: 'Custo efetivo total (CET)', valor: 'Não informado', codigo: 'CET' }],
          },
        ],
      },
    }
  }

  it('posição por "tipo — credor" e explicação; justificativa só no detalhe recolhido', async () => {
    montar({ classificacoes_erro: [], pendencias_homologacao: [] }, casoComDados())

    expect(
      await screen.findAllByText('Cheque especial — CAIXA ECONOMICA FEDERAL', { exact: false }),
    ).not.toHaveLength(0)
    expect(
      screen.getByText('É a dívida que mais destrava o seu orçamento agora.'),
    ).toBeInTheDocument()
    const justificativa = screen.getByText(JUSTIFICATIVA)
    expect(justificativa.closest('details')).not.toBeNull()
    expect(justificativa.closest('details')).not.toHaveAttribute('open')
    expect(screen.getByText('Detalhe técnico')).toBeInTheDocument()
  })

  it('dados com rótulo e valor do servidor; o código fica como detalhe', async () => {
    montar({ classificacoes_erro: [], pendencias_homologacao: [] }, casoComDados())

    const cet = (await screen.findByText('Custo efetivo total (CET)', { exact: false })).closest('dt')
    expect(cet).toHaveTextContent('Custo efetivo total (CET) CET')
    expect(cet?.nextElementSibling).toHaveTextContent('Não informado')
    expect(screen.getByText('R$ 10.350,92')).toBeInTheDocument()
    expect(screen.getByText('A maior parte, mas alguns ficam de fora.')).toBeInTheDocument()
    expect(
      screen.getByRole('region', { name: 'Cheque especial — CAIXA ECONOMICA FEDERAL' }),
    ).toHaveTextContent('D011')
  })

  it('método e status por rótulo no carimbo', async () => {
    montar({ classificacoes_erro: [], pendencias_homologacao: [] })

    expect(
      await screen.findByText(/Método: Avalanche · Definitivo na data/),
    ).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('DEFINITIVO_NA_DATA')
  })
})
