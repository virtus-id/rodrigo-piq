// @vitest-environment happy-dom
/**
 * `CampoPergunta` — os widgets dos nove `TipoResposta` (`RF-50`, T-137).
 *
 * `happy-dom`, não `jsdom`: a cadeia de dependências do jsdom quebra neste
 * Node 22.9 (`ERR_REQUIRE_ESM` em `@csstools/css-calc`).
 *
 * Queries acessíveis (`getByRole`, `getByLabelText`), nunca seletor por
 * classe — `.claude/instructions/testing.instructions.md`. Isso também
 * testa a acessibilidade de graça: se o rótulo não estiver associado ao
 * campo, a query falha.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import CampoPergunta from '../../../src/componentes/CampoPergunta'
import type { Pergunta, TipoResposta } from '../../../src/tipos'

function fabricar(tipo: TipoResposta, extra: Partial<Pergunta> = {}): Pergunta {
  return {
    CASO_ID: 'CASO-1',
    ID: 'Q1',
    bloco: 5,
    tipo,
    enunciado: `Campo de teste ${tipo}`,
    opcoes: [],
    // `VARIAVEL_GRAVADA` saiu do fixture em `T-155`: o servidor deixou de
    // enviá-lo em T-144 e `tipos.ts` não o declara. Um fixture com campo que
    // o payload real não tem faz o teste exercitar uma forma que não existe —
    // e este ficou dois releases mentindo, porque nada type-checkava `tests/`.
    escopo_repeticao: 'NENHUM',
    item_id: null,
    // `RF-63`: `null` fora de ficha repetível — é o caso deste fixture, que
    // tem `escopo_repeticao: NENHUM`. Quem usa os dois é o localizador da
    // casca, não `CampoPergunta`.
    posicao: null,
    total_na_ficha: null,
    admite_nao_sei: false,
    valor_atual: null,
    respondida_como_nao_sei: false,
    valores_marcados: [],
    aviso: null,
    ...extra,
  }
}

describe('MOEDA', () => {
  it('formata enquanto digita e mostra o R$ FORA do campo', async () => {
    const aoValor = vi.fn()
    const usuario = userEvent.setup()
    render(
      <CampoPergunta
        pergunta={fabricar('MOEDA')}
        valor=""
        naoSei={false}
        onValor={aoValor}
        onNaoSei={vi.fn()}
      />,
    )

    await usuario.type(screen.getByLabelText(/Campo de teste MOEDA/), '1')

    // O "R$" é prefixo visual: nunca entra no valor submetido.
    expect(aoValor).toHaveBeenCalledWith('0,01')
    expect(screen.getByLabelText(/Campo de teste MOEDA/)).not.toHaveValue('R$')
  })
})

describe('TAXA', () => {
  it('AC-76: o % fica fora do input', () => {
    render(
      <CampoPergunta
        pergunta={fabricar('TAXA')}
        valor="4,5"
        naoSei={false}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    expect(screen.getByLabelText(/Campo de teste TAXA/)).toHaveValue('4,5')
    // O símbolo existe na tela, mas como texto irmão — não no campo.
    expect(screen.getByText('%')).toBeInTheDocument()
  })
})

describe('SELECAO_UNICA', () => {
  it('desenha uma opção por registro, com o rótulo do YAML', async () => {
    const aoValor = vi.fn()
    const usuario = userEvent.setup()
    render(
      <CampoPergunta
        pergunta={fabricar('SELECAO_UNICA', {
          opcoes: [
            { rotulo: 'Cartão de crédito', valor_interno: 'CARTAO', admite_nao_sei: false },
            { rotulo: 'Consignado', valor_interno: 'CONSIGNADO', admite_nao_sei: false },
          ],
        })}
        valor=""
        naoSei={false}
        onValor={aoValor}
        onNaoSei={vi.fn()}
      />,
    )

    const opcoes = screen.getAllByRole('radio')
    expect(opcoes).toHaveLength(2)

    await usuario.click(screen.getByRole('radio', { name: /Cartão de crédito/ }))
    // O que sobe é o `valor_interno`, nunca o rótulo.
    expect(aoValor).toHaveBeenCalledWith('CARTAO')
  })
})

describe('ESCALA_0_10', () => {
  it('oferece as onze posições, de 0 a 10', () => {
    render(
      <CampoPergunta
        pergunta={fabricar('ESCALA_0_10')}
        valor="7"
        naoSei={false}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    expect(screen.getAllByRole('radio')).toHaveLength(11)
    expect(screen.getByRole('radio', { name: '7' })).toHaveAttribute('aria-checked', 'true')
  })
})

describe('não sei', () => {
  it('RF-48/AC-78: marcar "não sei" deixa o campo inerte', () => {
    render(
      <CampoPergunta
        pergunta={fabricar('MOEDA', { admite_nao_sei: true })}
        valor=""
        naoSei={true}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    expect(screen.getByLabelText(/Campo de teste MOEDA/)).toBeDisabled()
  })

  it('só aparece quando o registro admite', () => {
    render(
      <CampoPergunta
        pergunta={fabricar('MOEDA', { admite_nao_sei: false })}
        valor=""
        naoSei={false}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    expect(screen.queryByLabelText('Não sei')).not.toBeInTheDocument()
  })
})

describe('aviso de materialidade', () => {
  it('é anunciado a leitor de tela e vinculado ao campo', () => {
    render(
      <CampoPergunta
        pergunta={fabricar('MOEDA', {
          aviso: 'pode deixar seu plano provisório',
          admite_nao_sei: true,
        })}
        valor=""
        naoSei={false}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    const aviso = screen.getByRole('status')
    expect(aviso).toHaveTextContent(/pode deixar seu plano provisório/)
    expect(screen.getByLabelText(/Campo de teste MOEDA/)).toHaveAttribute(
      'aria-describedby',
      aviso.id,
    )
  })
})
