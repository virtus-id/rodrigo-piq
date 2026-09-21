/**
 * Boas-vindas — o que é isto, antes de perguntar sobre dinheiro — `RF-66`,
 * `AC-97`, `AC-98` (T-158).
 *
 * **Por que existe.** No primeiro uso real, o relato foi *"me senti perdido,
 * sem saber o que é, qual o objetivo"*. O aluno chegava ao Início e encontrava
 * "Continuar de onde você parou" — uma ordem, sem explicação do que ele estava
 * continuando.
 *
 * Pedir a alguém endividado que responda cem perguntas sobre o próprio
 * dinheiro sem dizer para quê é pedir um ato de confiança que não foi
 * merecido. Esta tela é onde o produto se apresenta.
 *
 * **Aparece uma vez, e nunca bloqueia** (`AC-98`). O gatilho é ter zero
 * respostas gravadas — não uma marca em `localStorage` (`RF-67`, `AC-99`):
 * quem começa no computador e continua no celular não pode ver a apresentação
 * de novo, nem perdê-la por ter trocado de aparelho. O estado do caso é a
 * única fonte.
 *
 * **O que esta tela promete, o sistema cumpre.** "Uma pessoa confere" é
 * `RF-23` (revisão humana obrigatória, 100% dos planos no piloto); "pode parar
 * e voltar" é `RF-10` (multissessão, retomada na pergunta exata). Nenhuma
 * frase aqui é marketing: cada uma corresponde a um requisito implementado.
 */
import Botao from '../componentes/Botao'
import Tela from '../componentes/Tela'

interface TelaBoasVindasProps {
  /** Segue para o fluxo. A tela nunca é obstáculo (`AC-98`). */
  comecar: () => void
}

interface Passo {
  rotulo: string
  detalhe: string
}

/**
 * O que vai acontecer, na ordem — o "step by step" do produto.
 *
 * Três passos, não cinco: aqui o objetivo é dar o arco (você responde → o PIQ
 * calcula → uma pessoa confere → você recebe), não o detalhe. O mapa completo
 * das cinco etapas é a trilha do Início, que ele vê logo em seguida e a cada
 * visita.
 */
const PASSOS: readonly Passo[] = [
  {
    rotulo: 'Você conta a sua situação',
    detalhe:
      'Perguntas sobre o que entra, o que sai e o que você deve. Pode responder aos poucos.',
  },
  {
    rotulo: 'O PIQ monta a ordem de quitação',
    detalhe: 'Qual dívida atacar primeiro, quanto cabe por mês, e em quanto tempo.',
  },
  {
    rotulo: 'Uma pessoa da equipe confere',
    detalhe: 'Nenhum plano chega a você sem alguém ter revisado antes.',
  },
]

export default function TelaBoasVindas({ comecar }: TelaBoasVindasProps) {
  return (
    <Tela
      titulo="Vamos montar o seu plano de quitação"
      acoes={<Botao onClick={comecar}>Começar</Botao>}
    >
      <p className="lead">
        O PIQ organiza as suas dívidas numa ordem de quitação feita para a sua
        situação — e diz quanto cabe pagar por mês, sem apertar o seu orçamento
        além do que dá.
      </p>

      <ol className="lista list-none p-0">
        {PASSOS.map((passo, indice) => (
          <li key={passo.rotulo} className="item">
            <span className="num" aria-hidden="true">
              {indice + 1}
            </span>
            <div className="flex-1">
              {passo.rotulo}
              <small className="block text-muted">{passo.detalhe}</small>
            </div>
          </li>
        ))}
      </ol>

      {/* As duas promessas que mais importam para quem hesita em começar:
          não precisa ser de uma vez, e ninguém julga sozinho. */}
      <div className="cartao">
        <p className="nota">
          <strong>Não precisa terminar hoje.</strong> Tudo o que você responder fica
          guardado. Você pode parar quando quiser e voltar depois, de qualquer
          aparelho.
        </p>
      </div>
    </Tela>
  )
}
