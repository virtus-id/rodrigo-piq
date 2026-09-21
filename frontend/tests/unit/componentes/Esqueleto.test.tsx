// @vitest-environment happy-dom
/**
 * `Esqueleto` — o carregamento não pode custar acessibilidade (`RF-75`,
 * `AC-112`, T-164).
 *
 * `happy-dom`, não `jsdom`: a cadeia de dependências do jsdom quebra neste
 * Node 22.9 (`ERR_REQUIRE_ESM` em `@csstools/css-calc`).
 *
 * **O que estes testes guardam.** A troca de `<p role="status">Carregando…</p>`
 * por um desenho é uma melhoria visual que poderia, sem querer, remover
 * informação da árvore de acessibilidade — quem usa leitor de tela deixaria
 * de saber que a tela está carregando, e receberia silêncio no lugar. `AC-112`
 * proíbe isso, e é o que se verifica aqui.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import Esqueleto, { type FormaDoEsqueleto } from '../../../src/componentes/Esqueleto'

const FORMAS: readonly FormaDoEsqueleto[] = ['resumo', 'lista', 'pergunta', 'texto']

describe('Esqueleto', () => {
  it('anuncia o carregamento a leitor de tela — AC-112', () => {
    render(<Esqueleto forma="resumo" anuncio="Carregando seu plano" />)

    // `getByRole('status')` é a mesma query que encontraria o
    // `<p role="status">Carregando…</p>` de antes: a informação continua
    // exatamente onde estava.
    expect(screen.getByRole('status')).toHaveTextContent('Carregando seu plano')
  })

  it.each(FORMAS)('mantém o anúncio na forma %s — AC-112', (forma) => {
    render(<Esqueleto forma={forma} anuncio="Carregando…" />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('esconde o desenho da árvore de acessibilidade — AC-112', () => {
    const { container } = render(<Esqueleto forma="lista" itens={3} />)

    const desenho = container.querySelector('[aria-hidden="true"]')
    expect(desenho).not.toBeNull()
    // As barras do desenho vivem DENTRO do bloco escondido. Para um leitor
    // de tela elas seriam uma sequência de caixas vazias — ruído puro.
    expect(desenho?.querySelectorAll('.sk').length).toBeGreaterThan(0)
  })

  it('desenha um item por entrada pedida', () => {
    const { container } = render(<Esqueleto forma="lista" itens={4} />)
    // Cada item da lista traz uma marca circular — contá-las conta os itens.
    expect(container.querySelectorAll('.rounded-full').length).toBe(4)
  })

  it('usa "Carregando…" quando a tela não passa anúncio', () => {
    render(<Esqueleto />)
    expect(screen.getByRole('status')).toHaveTextContent('Carregando…')
  })

  it('não emite nenhum elemento focável — o esqueleto não é controle', () => {
    const { container } = render(<Esqueleto forma="pergunta" />)

    // Um esqueleto que capturasse foco deixaria o usuário de teclado preso
    // num placeholder. Nenhuma das quatro formas emite botão, link ou campo.
    expect(container.querySelector('button, a, input, [tabindex]')).toBeNull()
  })
})
