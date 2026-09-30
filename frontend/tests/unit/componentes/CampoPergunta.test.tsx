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
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
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

describe('T-194: estado por opção, nunca `valor_interno ?? ""`', () => {
  // Checklist como o registro ainda o traz (D1 em aberto): duas opções sem
  // `valor_interno`. Antes, as duas viravam `''` e marcar uma marcava todas.
  const checklist = fabricar('SELECAO_MULTIPLA', {
    opcoes: [
      { rotulo: 'Aluguel', valor_interno: null, admite_nao_sei: false },
      { rotulo: 'Condomínio', valor_interno: null, admite_nao_sei: false },
      { rotulo: 'Energia', valor_interno: 'ENERGIA', admite_nao_sei: false },
    ],
  })

  it('SELECAO_MULTIPLA: com valor vazio, nenhuma opção de valor nulo aparece marcada', () => {
    render(
      <CampoPergunta
        pergunta={checklist}
        valor={['']}
        naoSei={false}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    expect(screen.getByRole('checkbox', { name: 'Aluguel' })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Condomínio' })).not.toBeChecked()
  })

  it('SELECAO_MULTIPLA: marcar uma opção envia só ela, e nunca `""`', async () => {
    const aoValor = vi.fn()
    const usuario = userEvent.setup()
    render(
      <CampoPergunta
        pergunta={checklist}
        valor={[]}
        naoSei={false}
        onValor={aoValor}
        onNaoSei={vi.fn()}
      />,
    )

    await usuario.click(screen.getByRole('checkbox', { name: 'Energia' }))
    await usuario.click(screen.getByRole('checkbox', { name: 'Aluguel' }))

    expect(aoValor).toHaveBeenCalledTimes(1)
    expect(aoValor).toHaveBeenCalledWith(['ENERGIA'])
  })

  it('SELECAO_UNICA: a opção escolhida aparece marcada, e só ela', () => {
    render(
      <CampoPergunta
        pergunta={fabricar('SELECAO_UNICA', {
          opcoes: [
            { rotulo: 'Sim', valor_interno: 'SIM', admite_nao_sei: false },
            { rotulo: 'Não', valor_interno: 'NAO', admite_nao_sei: false },
            { rotulo: 'Talvez', valor_interno: null, admite_nao_sei: false },
          ],
        })}
        valor="SIM"
        naoSei={false}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    expect(screen.getByRole('radio', { name: 'Sim' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Não' })).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByRole('radio', { name: 'Talvez' })).toHaveAttribute('aria-checked', 'false')
  })

  it('SIM_NAO_TALVEZ: opção de valor nulo não envia `""`', async () => {
    const aoValor = vi.fn()
    const usuario = userEvent.setup()
    render(
      <CampoPergunta
        pergunta={fabricar('SIM_NAO_TALVEZ', {
          opcoes: [
            { rotulo: 'Sim', valor_interno: null, admite_nao_sei: false },
            { rotulo: 'Não', valor_interno: null, admite_nao_sei: false },
          ],
        })}
        valor=""
        naoSei={false}
        onValor={aoValor}
        onNaoSei={vi.fn()}
      />,
    )

    await usuario.click(screen.getByRole('radio', { name: 'Sim' }))

    expect(aoValor).not.toHaveBeenCalled()
    expect(screen.getByRole('radio', { name: 'Sim' })).toBeDisabled()
  })
})

describe('T-207: um só "Não sei"', () => {
  const comOpcaoNaoSei = fabricar('SELECAO_UNICA', {
    admite_nao_sei: true,
    opcoes: [
      { rotulo: 'Sim', valor_interno: 'SIM', admite_nao_sei: false },
      { rotulo: 'Não sei', valor_interno: 'NAO_SEI', admite_nao_sei: true },
    ],
  })

  it('pergunta com opção "Não sei" não desenha o checkbox genérico', () => {
    render(
      <CampoPergunta
        pergunta={comOpcaoNaoSei}
        valor=""
        naoSei={false}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    expect(screen.getAllByText('Não sei')).toHaveLength(1)
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('"não sei" gravado antes não trava as opções, e escolher uma o desfaz', async () => {
    const aoValor = vi.fn()
    const aoNaoSei = vi.fn()
    const usuario = userEvent.setup()
    render(
      <CampoPergunta
        pergunta={comOpcaoNaoSei}
        valor=""
        naoSei={true}
        onValor={aoValor}
        onNaoSei={aoNaoSei}
      />,
    )

    await usuario.click(screen.getByRole('radio', { name: 'Sim' }))

    expect(aoValor).toHaveBeenCalledWith('SIM')
    expect(aoNaoSei).toHaveBeenCalledWith(false)
  })

  it('MOEDA mantém o checkbox, no estilo das opções', () => {
    render(
      <CampoPergunta
        pergunta={fabricar('MOEDA', { admite_nao_sei: true })}
        valor=""
        naoSei={false}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    const caixa = screen.getByRole('checkbox', { name: 'Não sei' })
    // Exceção deliberada à regra de não consultar classe: o critério de aceite
    // É o estilo `.opt`.
    expect(caixa.closest('label')).toHaveClass('opt')
  })
})

describe('T-213: opção que abre campo de data', () => {
  // Como `B5.B05B`: "Data" sem `valor_interno`, marcada por `abre_campo`.
  const comData = fabricar('SELECAO_UNICA', {
    opcoes: [
      { rotulo: 'Data', valor_interno: null, admite_nao_sei: false, abre_campo: 'DATA' },
      {
        rotulo: 'Validade não informada.',
        valor_interno: 'VALIDADE_DESCONHECIDA',
        admite_nao_sei: false,
      },
    ],
  })

  function ComEstado({ inicial = '' }: { inicial?: string }) {
    const [valor, setValor] = useState<string | string[]>(inicial)
    return (
      <>
        <CampoPergunta
          pergunta={comData}
          valor={valor}
          naoSei={false}
          onValor={setValor}
          onNaoSei={vi.fn()}
        />
        <output data-testid="valor">{String(valor)}</output>
      </>
    )
  }

  it('escolher "Data" mostra o campo de data; o rádio sozinho não envia nada', async () => {
    const usuario = userEvent.setup()
    render(<ComEstado />)
    expect(screen.queryByLabelText('Data')).not.toBeInTheDocument()

    await usuario.click(screen.getByRole('radio', { name: 'Data' }))

    const campo = screen.getByLabelText('Data')
    expect(campo).toHaveAttribute('type', 'date')
    expect(screen.getByRole('radio', { name: 'Data' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByTestId('valor')).toHaveTextContent(/^$/)

    fireEvent.change(campo, { target: { value: '2026-12-31' } })
    expect(screen.getByTestId('valor')).toHaveTextContent('2026-12-31')
  })

  it('AC-102: a data gravada reaparece preenchida ao reabrir', () => {
    render(<ComEstado inicial="2026-12-31" />)

    expect(screen.getByRole('radio', { name: 'Data' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByLabelText('Data')).toHaveValue('2026-12-31')
  })

  it('outra opção grava o valor_interno e fecha o campo', async () => {
    const usuario = userEvent.setup()
    render(<ComEstado inicial="2026-12-31" />)

    await usuario.click(screen.getByRole('radio', { name: 'Validade não informada.' }))

    expect(screen.getByTestId('valor')).toHaveTextContent('VALIDADE_DESCONHECIDA')
    expect(screen.queryByLabelText('Data')).not.toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Data' })).toHaveAttribute('aria-checked', 'false')
  })
})
