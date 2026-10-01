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
import { fireEvent, render, screen, within } from '@testing-library/react'
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
    // `T-323`: nos tipos de valor, inerte = vazio (o digitado não aparece
    // nem vai junto); digitar de novo desfaz o "não sei".
    render(
      <CampoPergunta
        pergunta={fabricar('MOEDA', { admite_nao_sei: true })}
        valor="50,00"
        naoSei={true}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    expect(screen.getByLabelText(/Campo de teste MOEDA/)).toHaveValue('')
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

  it('MOEDA mantém o "Não sei", no estilo das opções (rádio desde T-323)', () => {
    render(
      <CampoPergunta
        pergunta={fabricar('MOEDA', { admite_nao_sei: true })}
        valor=""
        naoSei={false}
        onValor={vi.fn()}
        onNaoSei={vi.fn()}
      />,
    )

    // Exceção deliberada à regra de não consultar classe: o critério de aceite
    // É o estilo `.opt`.
    expect(screen.getByRole('radio', { name: 'Não sei' })).toHaveClass('opt')
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

describe('T-299: opções e "Não sei" nos tipos de valor', () => {
  // Como `B5.B03` (indispensável): o "Não sei." é opção do registro.
  const saldo = fabricar('MOEDA', {
    admite_nao_sei: true,
    opcoes: [
      { rotulo: 'R$ ______', valor_interno: null, admite_nao_sei: false },
      { rotulo: 'Não sei.', valor_interno: null, admite_nao_sei: true },
    ],
  })
  // Como `B3.01`: a renda variável é alternativa ao campo.
  const renda = fabricar('MOEDA', {
    opcoes: [
      { rotulo: 'R$ ______', valor_interno: null, admite_nao_sei: false },
      {
        rotulo: 'Minha renda é variável.',
        valor_interno: 'RENDA_VARIAVEL',
        admite_nao_sei: false,
      },
    ],
  })

  function ComEstado({ pergunta, inicial = '' }: { pergunta: Pergunta; inicial?: string }) {
    const [valor, setValor] = useState<string | string[]>(inicial)
    const [naoSei, setNaoSei] = useState(false)
    return (
      <>
        <CampoPergunta
          pergunta={pergunta}
          valor={valor}
          naoSei={naoSei}
          onValor={setValor}
          onNaoSei={setNaoSei}
        />
        <output data-testid="valor">{`${String(valor)}|${String(naoSei)}`}</output>
      </>
    )
  }

  it('MOEDA com opção "Não sei." mostra um "Não sei", e marcá-lo grava NAO_SEI', async () => {
    const usuario = userEvent.setup()
    render(<ComEstado pergunta={saldo} />)

    // Um só, com o rótulo do registro; o "R$ ______" não vira opção.
    expect(screen.getAllByText('Não sei.')).toHaveLength(1)
    expect(screen.queryByText('R$ ______')).not.toBeInTheDocument()
    await usuario.click(screen.getByRole('radio', { name: 'Não sei.' }))

    expect(screen.getByTestId('valor')).toHaveTextContent('|true')
    expect(screen.getByLabelText(/Campo de teste MOEDA/)).toHaveValue('')
  })

  it.each(['TAXA', 'NUMERO', 'DATA'] as const)(
    '%s com opção "não sei" também mostra o "Não sei"',
    (tipo) => {
      render(
        <CampoPergunta
          pergunta={fabricar(tipo, {
            admite_nao_sei: false,
            opcoes: [{ rotulo: 'Não sei.', valor_interno: null, admite_nao_sei: true }],
          })}
          valor=""
          naoSei={false}
          onValor={vi.fn()}
          onNaoSei={vi.fn()}
        />,
      )

      expect(screen.getByRole('radio', { name: 'Não sei.' })).toBeInTheDocument()
    },
  )

  it('a opção alternativa aparece ao lado do campo e grava o código', async () => {
    const usuario = userEvent.setup()
    render(<ComEstado pergunta={renda} />)

    await usuario.click(screen.getByRole('radio', { name: 'Minha renda é variável.' }))

    expect(screen.getByTestId('valor')).toHaveTextContent('RENDA_VARIAVEL|false')
    expect(screen.getByRole('radio', { name: 'Minha renda é variável.' })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    // O código nunca aparece no campo de R$.
    expect(screen.getByLabelText(/Campo de teste MOEDA/)).toHaveValue('')
  })

  it('digitar um valor desfaz a alternativa', async () => {
    const usuario = userEvent.setup()
    render(<ComEstado pergunta={renda} inicial="RENDA_VARIAVEL" />)

    await usuario.type(screen.getByLabelText(/Campo de teste MOEDA/), '1')

    expect(screen.getByTestId('valor')).toHaveTextContent('0,01|false')
    expect(screen.getByRole('radio', { name: 'Minha renda é variável.' })).toHaveAttribute(
      'aria-checked',
      'false',
    )
  })
})

describe('T-294: opção que abre campo R$ em outra variável', () => {
  // Como `B5.B01`: "Sim."/"Aproximadamente." pedem o valor original.
  const valorOriginal = fabricar('SELECAO_UNICA', {
    admite_nao_sei: true,
    opcoes: [
      { rotulo: 'Sim.', valor_interno: 'CONFIRMADA', admite_nao_sei: false, abre_campo: 'MOEDA' },
      {
        rotulo: 'Aproximadamente.',
        valor_interno: 'ESTIMADA',
        admite_nao_sei: false,
        abre_campo: 'MOEDA',
      },
      { rotulo: 'Não.', valor_interno: 'DESCONHECIDA', admite_nao_sei: true },
    ],
  })

  function ComEstado({ inicial = '' }: { inicial?: string | string[] }) {
    const [valor, setValor] = useState<string | string[]>(inicial)
    return (
      <>
        <CampoPergunta
          pergunta={valorOriginal}
          valor={valor}
          naoSei={false}
          onValor={setValor}
          onNaoSei={vi.fn()}
        />
        <output data-testid="valor">{JSON.stringify(valor)}</output>
      </>
    )
  }

  it('"Sim." abre o campo R$ e envia o código e o valor', async () => {
    const usuario = userEvent.setup()
    render(<ComEstado />)

    await usuario.click(screen.getByRole('radio', { name: 'Sim.' }))
    await usuario.type(screen.getByLabelText('Valor em R$'), '1')

    expect(screen.getByTestId('valor')).toHaveTextContent('["CONFIRMADA","0,01"]')
    expect(screen.getByRole('radio', { name: 'Sim.' })).toHaveAttribute('aria-checked', 'true')
  })

  it('trocar para "Aproximadamente." mantém o valor digitado', async () => {
    const usuario = userEvent.setup()
    render(<ComEstado inicial={['CONFIRMADA', '1.500,00']} />)

    await usuario.click(screen.getByRole('radio', { name: 'Aproximadamente.' }))

    expect(screen.getByTestId('valor')).toHaveTextContent('["ESTIMADA","1.500,00"]')
  })

  it('"Não." não abre campo e grava só o código', async () => {
    const usuario = userEvent.setup()
    render(<ComEstado inicial={['CONFIRMADA', '1.500,00']} />)

    await usuario.click(screen.getByRole('radio', { name: 'Não.' }))

    expect(screen.getByTestId('valor')).toHaveTextContent('"DESCONHECIDA"')
    expect(screen.queryByLabelText('Valor em R$')).not.toBeInTheDocument()
  })

  it('AC-102: reabre com a opção e o valor', () => {
    render(<ComEstado inicial={['ESTIMADA', '1.500,00']} />)

    expect(screen.getByRole('radio', { name: 'Aproximadamente.' })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    expect(screen.getByLabelText('Valor em R$')).toHaveValue('1.500,00')
  })
})

describe('T-323: nos tipos de valor, "Não sei" e as alternativas no mesmo formato', () => {
  // Como `B4.V09`: alternativa com código e "Não sei." do registro.
  const custo = fabricar('MOEDA', {
    admite_nao_sei: true,
    opcoes: [
      { rotulo: 'R$ ______', valor_interno: null, admite_nao_sei: false },
      {
        rotulo: 'Não há custo relevante que eu conheça.',
        valor_interno: 'SEM_CUSTO_RELEVANTE',
        admite_nao_sei: false,
      },
      { rotulo: 'Não sei.', valor_interno: null, admite_nao_sei: true },
    ],
  })

  function ComEstado({ pergunta }: { pergunta: Pergunta }) {
    const [valor, setValor] = useState<string | string[]>('')
    const [naoSei, setNaoSei] = useState(false)
    return (
      <>
        <CampoPergunta
          pergunta={pergunta}
          valor={naoSei ? '' : valor}
          naoSei={naoSei}
          onValor={setValor}
          onNaoSei={setNaoSei}
        />
        <output data-testid="valor">{`${String(valor)}|${String(naoSei)}`}</output>
      </>
    )
  }

  it('B4.V09: a alternativa e o "Não sei." são opções do mesmo grupo, sem checkbox', async () => {
    const usuario = userEvent.setup()
    render(<ComEstado pergunta={custo} />)

    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    const grupo = screen.getByRole('radiogroup')
    const opcoes = within(grupo).getAllByRole('radio')
    expect(opcoes.map((o) => o.textContent)).toEqual([
      'Não há custo relevante que eu conheça.',
      'Não sei.',
    ])
    // Exceção deliberada à regra de não consultar classe: o critério É o
    // mesmo estilo `.opt` nas duas.
    for (const opcao of opcoes) expect(opcao).toHaveClass('opt')

    const campo = screen.getByLabelText(/Campo de teste MOEDA/)
    await usuario.type(campo, '5000')
    await usuario.click(screen.getByRole('radio', { name: 'Não sei.' }))
    // Grava `NAO_SEI` e limpa o campo — nada digitado vai junto (`AC-78`).
    expect(screen.getByTestId('valor')).toHaveTextContent('|true')
    expect(campo).toHaveValue('')
    expect(screen.getByRole('radio', { name: 'Não sei.' })).toHaveAttribute('aria-checked', 'true')

    await usuario.click(screen.getByRole('radio', { name: 'Não há custo relevante que eu conheça.' }))
    expect(screen.getByTestId('valor')).toHaveTextContent('SEM_CUSTO_RELEVANTE|false')
    expect(screen.getByRole('radio', { name: 'Não sei.' })).toHaveAttribute('aria-checked', 'false')
    expect(campo).toHaveValue('')

    // Digitar um valor desmarca a alternativa.
    await usuario.type(campo, '7')
    expect(screen.getByTestId('valor')).toHaveTextContent('0,07|false')
    for (const opcao of screen.getAllByRole('radio'))
      expect(opcao).toHaveAttribute('aria-checked', 'false')
  })

  it('digitar depois do "Não sei" desmarca o "Não sei"', async () => {
    const usuario = userEvent.setup()
    render(<ComEstado pergunta={custo} />)

    await usuario.click(screen.getByRole('radio', { name: 'Não sei.' }))
    await usuario.type(screen.getByLabelText(/Campo de teste MOEDA/), '1')

    expect(screen.getByTestId('valor')).toHaveTextContent('0,01|false')
    expect(screen.getByRole('radio', { name: 'Não sei.' })).toHaveAttribute('aria-checked', 'false')
  })

  it.each(['MOEDA', 'TAXA', 'NUMERO', 'DATA'] as const)(
    '%s só com "não sei" mostra o "Não sei" como opção',
    async (tipo) => {
      const usuario = userEvent.setup()
      render(<ComEstado pergunta={fabricar(tipo, { admite_nao_sei: true })} />)

      expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
      await usuario.click(screen.getByRole('radio', { name: 'Não sei' }))
      expect(screen.getByTestId('valor')).toHaveTextContent('|true')
    },
  )
})
