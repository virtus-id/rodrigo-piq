// @vitest-environment happy-dom
/**
 * `TelaDefinirSenha` — o primeiro acesso de quem comprou (`T-179`).
 *
 * `happy-dom`, não `jsdom`: a cadeia de dependências do jsdom quebra neste
 * Node 22.9 (`ERR_REQUIRE_ESM` em `@csstools/css-calc`).
 *
 * Queries acessíveis (`getByLabelText`, `getByRole`), nunca seletor por
 * classe — mesma disciplina de `CampoPergunta.test.tsx`. Isso testa a
 * acessibilidade de graça: se o rótulo não estiver associado ao campo, a
 * query falha.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TelaDefinirSenha from '../../../src/telas/TelaDefinirSenha'
import * as api from '../../../src/services/api'

const TOKEN = 'token-de-teste'

function resposta(ok: boolean, corpo: object = {}): Response {
  return {
    ok,
    json: async () => corpo,
  } as Response
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('TelaDefinirSenha', () => {
  it('envia a senha quando as duas batem e têm tamanho', async () => {
    const definir = vi.spyOn(api, 'definirSenha').mockResolvedValue(resposta(true))
    render(<TelaDefinirSenha token={TOKEN} aoDefinir={() => undefined} />)

    await userEvent.type(screen.getByLabelText('Sua senha'), 'senha-bem-comprida')
    await userEvent.type(screen.getByLabelText('Repita a senha'), 'senha-bem-comprida')
    await userEvent.click(screen.getByRole('button', { name: /Criar senha/i }))

    await waitFor(() => expect(definir).toHaveBeenCalledWith(TOKEN, 'senha-bem-comprida'))
  })

  it('recusa senha curta SEM chamar o servidor', async () => {
    // A checagem local existe para o aluno saber antes de enviar — e para
    // não queimar o token num erro que dá para ver na hora.
    const definir = vi.spyOn(api, 'definirSenha').mockResolvedValue(resposta(true))
    render(<TelaDefinirSenha token={TOKEN} aoDefinir={() => undefined} />)

    await userEvent.type(screen.getByLabelText('Sua senha'), 'curta')
    await userEvent.type(screen.getByLabelText('Repita a senha'), 'curta')
    await userEvent.click(screen.getByRole('button', { name: /Criar senha/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/8 caracteres/i)
    expect(definir).not.toHaveBeenCalled()
  })

  it('recusa quando as duas senhas diferem', async () => {
    // A confirmação NÃO existe no servidor: lá chega uma senha só. É esta
    // comparação que protege contra o erro de digitação — sem ela, o aluno
    // definiria uma senha que não sabe qual é.
    const definir = vi.spyOn(api, 'definirSenha').mockResolvedValue(resposta(true))
    render(<TelaDefinirSenha token={TOKEN} aoDefinir={() => undefined} />)

    await userEvent.type(screen.getByLabelText('Sua senha'), 'senha-bem-comprida')
    await userEvent.type(screen.getByLabelText('Repita a senha'), 'senha-diferente-aqui')
    await userEvent.click(screen.getByRole('button', { name: /Criar senha/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/não são iguais/i)
    expect(definir).not.toHaveBeenCalled()
  })

  it('mostra a mensagem DO SERVIDOR quando o token é inválido', async () => {
    // Token expirado e senha curta são coisas diferentes, e o aluno precisa
    // saber qual aconteceu para saber o que fazer — pedir outro link, ou
    // escolher outra senha.
    vi.spyOn(api, 'definirSenha').mockResolvedValue(
      resposta(false, { erro: 'Link inválido ou expirado.' }),
    )
    render(<TelaDefinirSenha token={TOKEN} aoDefinir={() => undefined} />)

    await userEvent.type(screen.getByLabelText('Sua senha'), 'senha-bem-comprida')
    await userEvent.type(screen.getByLabelText('Repita a senha'), 'senha-bem-comprida')
    await userEvent.click(screen.getByRole('button', { name: /Criar senha/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/Link inválido ou expirado/i)
  })

  it('depois de definir, leva ao login — não entra sozinho', async () => {
    // A senha recém-escolhida é exercitada na hora. Entrar direto adiaria
    // a descoberta de um erro de digitação para dias depois.
    vi.spyOn(api, 'definirSenha').mockResolvedValue(resposta(true))
    const aoDefinir = vi.fn()
    render(<TelaDefinirSenha token={TOKEN} aoDefinir={aoDefinir} />)

    await userEvent.type(screen.getByLabelText('Sua senha'), 'senha-bem-comprida')
    await userEvent.type(screen.getByLabelText('Repita a senha'), 'senha-bem-comprida')
    await userEvent.click(screen.getByRole('button', { name: /Criar senha/i }))

    const entrar = await screen.findByRole('button', { name: 'Entrar' })
    await userEvent.click(entrar)

    expect(aoDefinir).toHaveBeenCalledOnce()
  })

  it('os campos são de senha e pedem senha NOVA ao gerenciador', async () => {
    render(<TelaDefinirSenha token={TOKEN} aoDefinir={() => undefined} />)

    for (const rotulo of ['Sua senha', 'Repita a senha']) {
      const campo = screen.getByLabelText(rotulo)
      expect(campo).toHaveAttribute('type', 'password')
      // `new-password` faz o navegador OFERECER uma senha forte, em vez de
      // tentar preencher uma que ainda não existe.
      expect(campo).toHaveAttribute('autocomplete', 'new-password')
    }
  })
})
