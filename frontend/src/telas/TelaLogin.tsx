/**
 * Entrada — tela `entrada` do protótipo validado (`RF-50`).
 *
 * O login é `POST /api/conta/login` com corpo `form-urlencoded`, exatamente
 * como a rota do servidor espera. O que autoriza tudo depois é o cookie de
 * sessão (`piq_sessao`, `Secure`+`HttpOnly`) que essa resposta instala — o
 * cliente nunca guarda credencial nem decide a quem um caso pertence.
 *
 * **O `e_revisor` da resposta sobe para o App** (`RF-59`, `AC-80`). É dica de
 * interface, não autorização: serve para não oferecer ao aluno o caminho da
 * fila e do painel. Quem autoriza é o servidor, a cada requisição.
 */
import { type FormEvent, useState } from 'react'

import Botao from '../componentes/Botao'
import Tela from '../componentes/Tela'
import { entrar, type SessaoDaConta } from '../services/api'

/**
 * O par que mantém o Enter funcionando — `RF-57`, detalhe nº 4 de `R5.5`.
 *
 * O submit vive na prop `acoes` da casca, logo FORA do `<form>`. Sem
 * `form="form-entrada"` no botão o Enter no campo de senha deixa de submeter,
 * e o teclado é o único caminho de quem não usa mouse.
 */
const ID_DO_FORM = 'form-entrada'

interface TelaLoginProps {
  onEntrou: (sessao: SessaoDaConta | null) => void
}

export default function TelaLogin({ onEntrou }: TelaLoginProps) {
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      const resposta = await entrar(email, senha)
      if (resposta.ok) {
        // `entrar` devolve a `Response` crua — o corpo é lido aqui porque é
        // esta tela que conhece o contrato do login. Corpo ilegível não
        // impede a entrada: `null` significa "não sabemos o papel", e o App
        // trata isso como não-revisor, que é o lado seguro.
        let sessao: SessaoDaConta | null = null
        try {
          sessao = (await resposta.json()) as SessaoDaConta
        } catch {
          /* sem corpo JSON: entra sem o papel */
        }
        onEntrou(sessao)
      } else {
        // O servidor devolve 401 sem dizer se o e-mail existe — não vazar
        // essa diferença é deliberado, e a mensagem aqui respeita isso.
        setErro('E-mail ou senha não conferem.')
      }
    } catch {
      setErro('Não foi possível entrar agora.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Tela
      titulo="Bem-vinda de volta"
      acoes={
        <Botao type="submit" form={ID_DO_FORM} disabled={enviando}>
          {enviando ? 'Entrando…' : 'Entrar'}
        </Botao>
      }
    >
      <p className="lead">
        Entre com seu e-mail e sua senha. Tudo o que você já respondeu está guardado.
      </p>

      <form id={ID_DO_FORM} onSubmit={aoEnviar} className="flex flex-col gap-5">
        <div className="field">
          <label htmlFor="email">Seu e-mail</label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            className="campo-texto"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="senha">Sua senha</label>
          <input
            id="senha"
            type="password"
            autoComplete="current-password"
            className="campo-texto"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
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
