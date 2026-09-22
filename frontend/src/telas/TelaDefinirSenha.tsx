/**
 * Definir a própria senha — primeiro acesso e recuperação (`T-179`).
 *
 * **Quem chega aqui.** Quem comprou o PIQ e recebeu o link por e-mail. A
 * conta já existe (nasceu do webhook da compra) e está **sem senha**: até
 * ele definir uma, `autenticar` recusa qualquer tentativa de login.
 *
 * A mesma tela serve à recuperação de senha — os dois fluxos terminam no
 * mesmo lugar, porque o fato é o mesmo: *"provei que sou dono deste e-mail,
 * quero definir a senha"*. Uma segunda tela seria a mesma coisa com outro
 * título.
 *
 * **Não entra sozinho depois.** Definida a senha, o aluno vai para o login
 * e a usa. Poderia instalar a sessão direto — mas aí a senha que ele acabou
 * de escolher só seria exercitada dias depois, e um erro de digitação
 * (nos dois campos, igual) só apareceria quando ele já não lembrasse o que
 * digitou.
 */
import { useState, type FormEvent } from 'react'

import Botao from '../componentes/Botao'
import Tela from '../componentes/Tela'
import { definirSenha } from '../services/api'

const ID_DO_FORM = 'form-definir-senha'

/**
 * O mesmo piso do servidor (`rotas_provisionamento.py::
 * TAMANHO_MINIMO_SENHA`).
 *
 * **Duplicado de propósito, e o servidor continua soberano.** Esta
 * verificação existe para o aluno saber ANTES de enviar; a do servidor é a
 * que vale. Se as duas divergirem, quem recusa é o servidor — e a tela
 * mostra a mensagem dele, nunca uma inventada aqui.
 */
const TAMANHO_MINIMO = 8

interface TelaDefinirSenhaProps {
  token: string
  /** Chamado depois de a senha ser definida — leva ao login. */
  aoDefinir: () => void
}

export default function TelaDefinirSenha({ token, aoDefinir }: TelaDefinirSenhaProps) {
  const [senha, setSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [pronto, setPronto] = useState(false)

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setErro(null)

    // As duas checagens locais são de CONVENIÊNCIA — evitam uma ida ao
    // servidor para um erro que o aluno vê na hora. A confirmação não
    // existe no servidor: lá chega uma senha só, e é a comparação aqui que
    // protege contra o erro de digitação.
    if (senha.length < TAMANHO_MINIMO) {
      setErro(`A senha precisa ter ao menos ${TAMANHO_MINIMO} caracteres.`)
      return
    }
    if (senha !== confirmacao) {
      setErro('As duas senhas não são iguais.')
      return
    }

    setEnviando(true)
    try {
      const resposta = await definirSenha(token, senha)
      if (resposta.ok) {
        setPronto(true)
        return
      }
      // `AC-104` em espírito: a recusa do servidor chega NOMEADA. Token
      // expirado e senha curta são coisas diferentes, e o aluno precisa
      // saber qual delas aconteceu para saber o que fazer.
      let detalhe = 'Não foi possível definir a senha.'
      try {
        const corpo = (await resposta.json()) as { erro?: string }
        if (corpo?.erro) detalhe = corpo.erro
      } catch {
        /* corpo não-JSON: fica a mensagem acima */
      }
      setErro(detalhe)
    } catch {
      setErro('Não foi possível definir a senha agora.')
    } finally {
      setEnviando(false)
    }
  }

  if (pronto) {
    return (
      <Tela
        titulo="Sua senha está pronta"
        acoes={<Botao onClick={aoDefinir}>Entrar</Botao>}
      >
        <p className="lead">
          Agora entre com o seu e-mail e a senha que você acabou de criar.
        </p>
      </Tela>
    )
  }

  return (
    <Tela
      titulo="Crie a sua senha"
      acoes={
        <Botao type="submit" form={ID_DO_FORM} disabled={enviando}>
          {enviando ? 'Salvando…' : 'Criar senha e continuar'}
        </Botao>
      }
    >
      <p className="lead">
        É com ela que você vai entrar no PIQ, de qualquer aparelho, sempre que
        quiser continuar o seu plano.
      </p>

      <form id={ID_DO_FORM} onSubmit={aoEnviar} className="flex flex-col gap-5">
        <div className="field">
          <label htmlFor="senha">Sua senha</label>
          <input
            id="senha"
            type="password"
            // `new-password` (e não `current-password`): diz ao gerenciador
            // de senhas do navegador para OFERECER uma senha forte, em vez
            // de tentar preencher uma que não existe.
            autoComplete="new-password"
            className="campo-texto"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
          />
          <small className="nota">Ao menos {TAMANHO_MINIMO} caracteres.</small>
        </div>

        <div className="field">
          <label htmlFor="confirmacao">Repita a senha</label>
          <input
            id="confirmacao"
            type="password"
            autoComplete="new-password"
            className="campo-texto"
            value={confirmacao}
            onChange={(e) => setConfirmacao(e.target.value)}
            required
          />
        </div>

        {erro && (
          <p role="alert" className="aviso-erro">
            {erro}
          </p>
        )}
      </form>
    </Tela>
  )
}
