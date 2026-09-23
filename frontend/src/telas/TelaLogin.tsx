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
 *
 * ## Por que esta tela NÃO usa a casca `Tela`
 *
 * **`AC-82` isenta a entrada explicitamente** ("ela é anterior ao fluxo, e o
 * 'voltar' dali é sair do app"). A isenção existia só para o `‹ Voltar`;
 * aqui ela é usada por inteiro, e a razão é de produto, não de estética.
 *
 * Esta é a **primeira coisa que alguém que acabou de pagar vê**. Com a casca
 * genérica, ela era visualmente idêntica a qualquer formulário interno — a
 * mesma moldura da tela de pergunta, de progresso, de espera. Quem comprou
 * um plano personalizado encontrava um formulário que não afirmava nada, e a
 * tela não usava nenhum dos argumentos do produto.
 *
 * **A isenção para aqui.** Nenhuma outra tela do aluno ganha layout próprio:
 * `AC-82` existe contra o segundo modelo de navegação, e foi assim que a
 * barra de sete abas nasceu. Esta tela é a exceção nomeada no próprio
 * critério, não uma brecha.
 *
 * **Os componentes continuam sendo os do projeto** — `.campo-texto`, `.btn`,
 * `.btn-primario`, os alvos de toque de 56px. O que muda é a composição, não
 * o vocabulário visual: nada aqui é uma cor, um raio ou uma fonte nova.
 *
 * ## A redação vive em `textosDaEntrada.ts`
 *
 * Quem revisa a copy é o especialista, não quem escreve React. Ver a nota do
 * módulo.
 */
import { type FormEvent, useState } from 'react'

import { entrar, type SessaoDaConta } from '../services/api'
import {
  ERROS,
  FORMULARIO,
  PROVAS,
  RODAPE_SEGURANCA,
  SELO,
  SUBTITULO,
  TITULO,
} from './textosDaEntrada'

interface TelaLoginProps {
  onEntrou: (sessao: SessaoDaConta | null) => void
}

/**
 * As curvas do painel — a dívida caindo mês a mês.
 *
 * É o gráfico do próprio plano, não ornamento genérico: a única imagem que
 * este produto poderia ter. `aria-hidden` porque não carrega informação que
 * o texto ao lado já não diga; anunciá-la só atrapalharia quem usa leitor de
 * tela.
 */
function CurvasDeQuitacao() {
  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full opacity-[0.26]"
      viewBox="0 0 400 560"
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M-20 200 C 90 205, 150 300, 230 370 S 350 470, 420 500"
        fill="none"
        stroke="#5FD3AE"
        strokeWidth="1.6"
        opacity="0.75"
      />
      <path
        d="M-20 250 C 90 258, 160 350, 240 415 S 350 505, 420 535"
        fill="none"
        stroke="#5FD3AE"
        strokeWidth="1.2"
        opacity="0.5"
      />
      <path
        d="M-20 150 C 90 152, 140 250, 220 325 S 350 435, 420 465"
        fill="none"
        stroke="#5FD3AE"
        strokeWidth="1"
        opacity="0.33"
      />
      <circle cx="230" cy="370" r="3.2" fill="#7FE0BC" />
      <circle cx="330" cy="452" r="2.6" fill="#7FE0BC" opacity="0.7" />
    </svg>
  )
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
        setErro(ERROS.credenciais)
      }
    } catch {
      setErro(ERROS.indisponivel)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-0 sm:p-6">
      {/*
        `items-stretch` é o que mantém as duas metades da mesma altura. Sem
        ele, a coluna do formulário encolhe ao conteúdo e o painel verde
        fica com uma faixa clara embaixo.
      */}
      <div className="grid w-full max-w-[1080px] items-stretch overflow-hidden border-line bg-surface shadow-[var(--e3)] sm:rounded-piq sm:border lg:grid-cols-[1.05fr_0.95fr]">
        {/*
          O painel de marca. `lg:` e não `md:`: abaixo de 1024px as duas
          colunas espremem o título a ponto de quebrar em quatro linhas — no
          celular ele vira uma faixa acima do formulário, na ordem em que se
          lê.
        */}
        <div className="painel-marca relative flex flex-col justify-between gap-8 px-6 py-9 text-marca-texto sm:px-10 sm:py-11">
          <CurvasDeQuitacao />

          <p className="relative m-0 flex items-center gap-2.5 text-[0.76rem] font-bold uppercase tracking-[0.12em] text-marca-suave">
            <span
              className="inline-block h-[7px] w-[7px] rounded-full bg-[#5FD3AE]"
              aria-hidden="true"
            />
            {SELO}
          </p>

          <div className="relative">
            {/*
              O `<h1>` da página. Ele existe aqui e não numa casca porque
              esta tela não tem casca — e toda tela precisa de um heading
              para leitor de tela anunciar.
            */}
            <h1 className="m-0 mb-3.5 text-balance font-serif text-[clamp(2rem,3.6vw,2.9rem)] font-semibold leading-[1.12] tracking-[-0.015em]">
              {TITULO.antes}
              <em className="not-italic text-[#7FE0BC] [font-style:italic]">{TITULO.destaque}</em>
              {TITULO.depois}
            </h1>
            <p className="m-0 max-w-[34ch] text-[1.02rem] leading-relaxed text-[#C6DDD4]">
              {SUBTITULO}
            </p>
          </div>

          <ul className="relative m-0 flex list-none flex-wrap gap-6 p-0 sm:gap-7">
            {PROVAS.map((prova) => (
              <li key={prova.titulo}>
                <p className="m-0 font-serif text-[1.35rem] font-semibold leading-none text-white sm:text-[1.5rem]">
                  {prova.titulo}
                </p>
                <p className="m-0 mt-1.5 max-w-[17ch] text-[0.79rem] leading-snug text-marca-suave">
                  {prova.detalhe}
                </p>
              </li>
            ))}
          </ul>
        </div>

        {/* O formulário. */}
        <div className="flex flex-col justify-center gap-5 px-6 py-9 sm:px-10 sm:py-11">
          <div>
            <h2 className="m-0 mb-1 font-serif text-[1.62rem] font-semibold">
              {FORMULARIO.titulo}
            </h2>
            <p className="lead m-0">{FORMULARIO.lead}</p>
          </div>

          <form onSubmit={aoEnviar} className="flex flex-col gap-4">
            <div className="field">
              <label htmlFor="email">{FORMULARIO.rotuloEmail}</label>
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
              <label htmlFor="senha">{FORMULARIO.rotuloSenha}</label>
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

            {/*
              O botão fica DENTRO do `<form>`, diferente das outras telas.
              Nelas o submit vive na prop `acoes` da casca — fora do form — e
              por isso precisa de `form={ID}` para o Enter continuar
              funcionando. Aqui não há casca: o botão é filho do form, e o
              Enter no campo de senha submete pelo comportamento nativo.
            */}
            <button type="submit" className="btn btn-primario w-full" disabled={enviando}>
              {enviando ? FORMULARIO.entrando : FORMULARIO.entrar}
            </button>
          </form>

          <p className="m-0 flex items-center gap-2 border-t border-line pt-4 text-[0.8rem] text-muted">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              aria-hidden="true"
              focusable="false"
              className="flex-none"
            >
              <rect x="4" y="11" width="16" height="10" rx="2" />
              <path d="M8 11V7a4 4 0 0 1 8 0v4" />
            </svg>
            {RODAPE_SEGURANCA}
          </p>
        </div>
      </div>
    </div>
  )
}
