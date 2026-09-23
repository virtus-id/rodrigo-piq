// @vitest-environment happy-dom
/**
 * `TelaLogin` — a primeira tela que quem comprou vê (`RF-50`).
 *
 * `happy-dom`, não `jsdom`: a cadeia de dependências do jsdom quebra neste
 * Node 22.9 (`ERR_REQUIRE_ESM` em `@csstools/css-calc`) — mesma nota de
 * `TelaDefinirSenha.test.tsx`.
 *
 * Queries acessíveis (`getByLabelText`, `getByRole`), nunca seletor por
 * classe. Isso testa a acessibilidade de graça: se o rótulo não estiver
 * associado ao campo, a query falha — e esta tela ganhou layout próprio
 * (`AC-82` isenta a entrada), então é justamente aqui que uma regressão de
 * marcação passaria despercebida.
 *
 * **Os testes de texto apontam para `textosDaEntrada.ts`, não para
 * literais.** A redação é revisada pelo especialista e vai mudar; um teste
 * que repetisse a frase quebraria a cada revisão de copy e ensinaria a
 * equipe a atualizar o teste sem ler o que mudou.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaLogin from '../../../src/telas/TelaLogin'
import {
  ERROS,
  FORMULARIO,
  PROVAS,
  RODAPE_SEGURANCA,
  SUBTITULO,
  TITULO,
} from '../../../src/telas/textosDaEntrada'
import * as api from '../../../src/services/api'

function resposta(ok: boolean, corpo: object = {}): Response {
  return { ok, json: async () => corpo } as Response
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('TelaLogin', () => {
  // -------------------------------------------------------------------
  // O que a tela afirma antes de pedir e-mail e senha.
  // -------------------------------------------------------------------

  it('mostra a promessa do produto, não o tamanho do questionário', () => {
    // O motivo da tela existir assim: quem acabou de pagar precisa ver o
    // que ganha. Anunciar quantas perguntas existem é anunciar o preço.
    render(<TelaLogin onEntrou={() => undefined} />)

    const titulo = screen.getByRole('heading', { level: 1 })
    expect(titulo).toHaveTextContent(TITULO.antes.trim())
    expect(titulo).toHaveTextContent(TITULO.destaque)
    expect(screen.getByText(SUBTITULO)).toBeInTheDocument()
  })

  it('não anuncia número de perguntas nem de métodos', () => {
    // Guarda de regressão da decisão de copy: se alguém reintroduzir "177
    // perguntas" ou "3 métodos", este teste cai.
    render(<TelaLogin onEntrou={() => undefined} />)

    const texto = document.body.textContent ?? ''
    expect(texto).not.toMatch(/\d+\s*perguntas/i)
    expect(texto).not.toMatch(/\d+\s*métodos/i)
  })

  it('lista as três respostas do plano', () => {
    render(<TelaLogin onEntrou={() => undefined} />)

    for (const prova of PROVAS) {
      expect(screen.getByText(prova.titulo)).toBeInTheDocument()
      expect(screen.getByText(prova.detalhe)).toBeInTheDocument()
    }
  })

  it('diz a verdade sobre quem vê os dados', () => {
    // A redação anterior dizia "ninguém mais vê o que você respondeu", o
    // que é falso: o plano é conferido por uma pessoa da equipe (`RF-23`).
    // Promessa de sigilo que o produto quebra é pior que nenhuma.
    render(<TelaLogin onEntrou={() => undefined} />)

    expect(screen.getByText(RODAPE_SEGURANCA)).toBeInTheDocument()
    expect(document.body.textContent ?? '').not.toMatch(/ninguém mais vê/i)
  })

  it('tem exatamente um h1 — a tela não usa a casca, e sem ele não há o que anunciar', () => {
    render(<TelaLogin onEntrou={() => undefined} />)

    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('o gráfico de fundo não é anunciado a leitor de tela', () => {
    // Decoração que repete o que o texto ao lado já diz só atrapalha.
    const { container } = render(<TelaLogin onEntrou={() => undefined} />)

    for (const svg of container.querySelectorAll('svg')) {
      expect(svg).toHaveAttribute('aria-hidden', 'true')
    }
  })

  // -------------------------------------------------------------------
  // O login em si.
  // -------------------------------------------------------------------

  it('envia e-mail e senha para a API', async () => {
    const login = vi.spyOn(api, 'entrar').mockResolvedValue(resposta(true, { e_revisor: false }))
    render(<TelaLogin onEntrou={() => undefined} />)

    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloEmail), 'aluno@exemplo.br')
    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloSenha), 'senha-secreta')
    await userEvent.click(screen.getByRole('button', { name: FORMULARIO.entrar }))

    await waitFor(() => expect(login).toHaveBeenCalledWith('aluno@exemplo.br', 'senha-secreta'))
  })

  it('o Enter no campo de senha submete', async () => {
    // Esta tela não usa a casca `Tela`, onde o botão fica FORA do form e
    // precisa de `form={ID}`. Aqui o botão é filho do form — se alguém o
    // mover para fora, o teclado para de funcionar em silêncio, e o
    // teclado é o único caminho de quem não usa mouse.
    const login = vi.spyOn(api, 'entrar').mockResolvedValue(resposta(true))
    render(<TelaLogin onEntrou={() => undefined} />)

    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloEmail), 'aluno@exemplo.br')
    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloSenha), 'senha-secreta{Enter}')

    await waitFor(() => expect(login).toHaveBeenCalledOnce())
  })

  it('sobe a sessão com o papel para o App', async () => {
    // `e_revisor` é dica de interface (`RF-59`, `AC-80`): decide o que
    // oferecer, nunca o que autorizar.
    vi.spyOn(api, 'entrar').mockResolvedValue(resposta(true, { e_revisor: true }))
    const onEntrou = vi.fn()
    render(<TelaLogin onEntrou={onEntrou} />)

    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloEmail), 'revisor@exemplo.br')
    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloSenha), 'senha')
    await userEvent.click(screen.getByRole('button', { name: FORMULARIO.entrar }))

    await waitFor(() => expect(onEntrou).toHaveBeenCalledWith({ e_revisor: true }))
  })

  it('entra mesmo quando o corpo da resposta é ilegível', async () => {
    // Corpo quebrado não pode barrar quem tem credencial válida: `null`
    // significa "não sabemos o papel", e o App trata como não-revisor.
    vi.spyOn(api, 'entrar').mockResolvedValue({
      ok: true,
      json: async () => {
        throw new Error('sem JSON')
      },
    } as unknown as Response)
    const onEntrou = vi.fn()
    render(<TelaLogin onEntrou={onEntrou} />)

    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloEmail), 'aluno@exemplo.br')
    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloSenha), 'senha')
    await userEvent.click(screen.getByRole('button', { name: FORMULARIO.entrar }))

    await waitFor(() => expect(onEntrou).toHaveBeenCalledWith(null))
  })

  it('credencial recusada não revela se o e-mail existe', async () => {
    // O servidor devolve 401 sem distinguir os dois casos — deliberado. A
    // mensagem da tela precisa respeitar isso, senão a interface desfaz a
    // proteção do servidor.
    vi.spyOn(api, 'entrar').mockResolvedValue(resposta(false))
    render(<TelaLogin onEntrou={() => undefined} />)

    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloEmail), 'naoexiste@exemplo.br')
    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloSenha), 'senha')
    await userEvent.click(screen.getByRole('button', { name: FORMULARIO.entrar }))

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(ERROS.credenciais)
    expect(alerta.textContent ?? '').not.toMatch(/não (existe|cadastrad)/i)
  })

  it('rede fora do ar mostra mensagem diferente de credencial errada', async () => {
    // Quem errou a senha tenta outra; quem está sem rede tenta de novo
    // depois. Mensagens iguais mandariam a pessoa para o caminho errado.
    vi.spyOn(api, 'entrar').mockRejectedValue(new Error('offline'))
    render(<TelaLogin onEntrou={() => undefined} />)

    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloEmail), 'aluno@exemplo.br')
    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloSenha), 'senha')
    await userEvent.click(screen.getByRole('button', { name: FORMULARIO.entrar }))

    expect(await screen.findByRole('alert')).toHaveTextContent(ERROS.indisponivel)
    expect(ERROS.indisponivel).not.toBe(ERROS.credenciais)
  })

  it('o botão desabilita durante o envio', async () => {
    // Sem isso, dois cliques viram duas requisições de login.
    let liberar: (r: Response) => void = () => undefined
    vi.spyOn(api, 'entrar').mockReturnValue(
      new Promise<Response>((resolve) => {
        liberar = resolve
      }),
    )
    render(<TelaLogin onEntrou={() => undefined} />)

    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloEmail), 'aluno@exemplo.br')
    await userEvent.type(screen.getByLabelText(FORMULARIO.rotuloSenha), 'senha')
    await userEvent.click(screen.getByRole('button', { name: FORMULARIO.entrar }))

    const botao = await screen.findByRole('button', { name: FORMULARIO.entrando })
    expect(botao).toBeDisabled()

    liberar(resposta(true))
    await waitFor(() => expect(screen.getByRole('button')).toBeEnabled())
  })

  it('os campos pedem ao gerenciador de senhas o preenchimento certo', () => {
    render(<TelaLogin onEntrou={() => undefined} />)

    expect(screen.getByLabelText(FORMULARIO.rotuloEmail)).toHaveAttribute(
      'autocomplete',
      'username',
    )
    const senha = screen.getByLabelText(FORMULARIO.rotuloSenha)
    expect(senha).toHaveAttribute('type', 'password')
    expect(senha).toHaveAttribute('autocomplete', 'current-password')
  })
})
