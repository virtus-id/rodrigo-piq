// @vitest-environment happy-dom
/**
 * `LimiteDeErro` — nenhuma exceção vira tela branca (`T-169`).
 *
 * `happy-dom`, não `jsdom`: a cadeia de dependências do jsdom quebra neste
 * Node 22.9 (`ERR_REQUIRE_ESM` em `@csstools/css-calc`).
 *
 * **O que estes testes guardam.** Sem limite de erro, uma exceção em
 * qualquer componente desmonta a árvore inteira e o aluno recebe uma página
 * em branco — sem mensagem, sem botão, sem caminho. Não é um cenário
 * hipotético: a revisão encontrou um `destino` desconhecido do servidor
 * fazendo `TelaInicio` lançar.
 */
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import LimiteDeErro from '../../../src/componentes/LimiteDeErro'

/** Um componente que sempre lança — o defeito que se quer conter. */
function ComponenteQueQuebra(): never {
  throw new Error('falha proposital de teste')
}

describe('LimiteDeErro', () => {
  beforeEach(() => {
    // O React escreve a exceção no console mesmo quando ela É capturada;
    // silenciar mantém a saída do teste legível sem esconder regressão —
    // a asserção é sobre o que a TELA mostra.
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('deixa passar o conteúdo quando nada falha', () => {
    render(
      <LimiteDeErro>
        <p>conteúdo normal</p>
      </LimiteDeErro>,
    )

    expect(screen.getByText('conteúdo normal')).toBeInTheDocument()
  })

  it('mostra uma tela com saída quando algo lança — nunca página em branco', () => {
    render(
      <LimiteDeErro>
        <ComponenteQueQuebra />
      </LimiteDeErro>,
    )

    // Um `<h1>`: a tela de erro é uma tela, com heading, como qualquer
    // outra — é o que um leitor de tela precisa para anunciá-la.
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    // E há o que fazer: o aluno não fica sem caminho.
    expect(screen.getByRole('button', { name: /Recarregar/i })).toBeInTheDocument()
  })

  it('diz que as respostas estão guardadas — `RF-10`', () => {
    render(
      <LimiteDeErro>
        <ComponenteQueQuebra />
      </LimiteDeErro>,
    )

    // A informação que mais importa para quem está no meio de cem perguntas
    // sobre o próprio dinheiro.
    expect(screen.getByText(/continua guardado/i)).toBeInTheDocument()
  })

  it('não expõe a mensagem técnica do erro ao aluno', () => {
    render(
      <LimiteDeErro>
        <ComponenteQueQuebra />
      </LimiteDeErro>,
    )

    // "falha proposital de teste" é vocabulário de quem escreveu o código.
    // O aluno recebe o que pode fazer, não o `Error.message`.
    expect(screen.queryByText(/falha proposital/i)).toBeNull()
  })

  it('registra o erro no console — some da tela, nunca do log', () => {
    render(
      <LimiteDeErro>
        <ComponenteQueQuebra />
      </LimiteDeErro>,
    )

    // O projeto não tem coletor de erro de cliente; o console é o único
    // destino disponível, e é o que o piloto vai ter.
    const chamadas = vi.mocked(console.error).mock.calls
    expect(chamadas.some((args) => String(args[0]).includes('[PIQ]'))).toBe(true)
  })
})
