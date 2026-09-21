// @vitest-environment happy-dom
/**
 * `TrilhaDaJornada` — o mapa nunca mente sobre onde o aluno está (`RF-64`,
 * `AC-93`, `AC-94`, `T-171`).
 *
 * `happy-dom`, não `jsdom`: a cadeia de dependências do jsdom quebra neste
 * Node 22.9 (`ERR_REQUIRE_ESM` em `@csstools/css-calc`).
 *
 * Os testes de navegador (`tests/e2e/navegacao.spec.ts`) já cobrem `AC-93`/
 * `AC-94` nas cinco fases conhecidas. O que falta — e o que este arquivo
 * acrescenta — é a SEXTA: a fase que o servidor pode passar a emitir e que
 * este cliente ainda não conhece, situação normal durante um deploy.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import TrilhaDaJornada from '../../../src/componentes/TrilhaDaJornada'
import type { Inicio } from '../../../src/tipos'

function fabricarInicio(fase: string, respondidas = 3, total = 101): Inicio {
  return {
    CASO_ID: 'CASO-TESTE',
    estado: 'ESTADO-QUALQUER',
    fase,
    mensagem: 'mensagem de teste',
    proxima_etapa: { destino: 'pergunta', ID_PERGUNTA: null, item_id: null },
    progresso: { respondidas, total },
    valor_em_destaque: null,
    plano_liberado: false,
    versao_do_plano: null,
  } as unknown as Inicio
}

/** O rótulo da etapa marcada como em curso. */
function etapaEmCurso(): string {
  const atual = document.querySelector('li[aria-current="step"]')
  return atual?.querySelector('.linha span')?.textContent ?? ''
}

describe('TrilhaDaJornada', () => {
  it('AC-94: exatamente uma etapa em curso, nas cinco fases conhecidas', () => {
    for (const fase of ['coleta', 'revisao', 'reprovado', 'plano', 'acompanhamento']) {
      const { unmount } = render(<TrilhaDaJornada inicio={fabricarInicio(fase)} />)
      expect(document.querySelectorAll('li[aria-current="step"]')).toHaveLength(1)
      unmount()
    }
  })

  it('T-171: fase desconhecida NÃO diz que o aluno voltou ao começo', () => {
    // Um servidor mais novo emite uma fase que este cliente não conhece.
    // Antes, o fallback era o índice 0 — e a trilha dizia a quem já tem
    // plano que ele está de volta à primeira pergunta.
    render(<TrilhaDaJornada inicio={fabricarInicio('fase_que_o_cliente_nao_conhece')} />)

    expect(document.querySelectorAll('li[aria-current="step"]')).toHaveLength(1)
    expect(etapaEmCurso()).not.toBe('Suas respostas')
    expect(etapaEmCurso()).toBe('Conferência da equipe')
  })

  it('T-171: fase desconhecida não dá uma ORDEM a quem não sabemos o estado', () => {
    render(<TrilhaDaJornada inicio={fabricarInicio('fase_futura')} />)

    // "Faça a próxima ação e conte como foi" é instrução para quem está em
    // acompanhamento — dizê-la a alguém de cuja situação não sabemos nada
    // manda executar um plano que talvez não exista.
    expect(screen.queryByText(/Faça a próxima ação/i)).toBeNull()
    expect(screen.getByText(/está com a equipe/i)).toBeInTheDocument()
  })

  it('AC-96: na coleta, o que falta vem COM unidade', () => {
    render(<TrilhaDaJornada inicio={fabricarInicio('coleta', 3, 101)} />)

    // "3 de 101" não informa: 101 do quê. `RF-65`.
    expect(screen.getByText('Faltam 98 perguntas.')).toBeInTheDocument()
  })

  it('AC-96: uma pergunta restante fala no singular', () => {
    render(<TrilhaDaJornada inicio={fabricarInicio('coleta', 100, 101)} />)

    expect(screen.getByText('Falta 1 pergunta.')).toBeInTheDocument()
  })

  it('AC-115: nenhum degrau é clicável — a trilha informa, não navega', () => {
    const { container } = render(<TrilhaDaJornada inicio={fabricarInicio('plano')} />)

    // Tornar os degraus clicáveis restabeleceria a barra de abas que
    // `RF-57`/`AC-83` mataram.
    expect(container.querySelector('button, a, [role="button"], [tabindex]')).toBeNull()
  })
})
