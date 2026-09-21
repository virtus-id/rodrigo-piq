/**
 * Meu progresso — as cinco partes da coleta — `RF-31`, `AC-40` (T-150).
 *
 * É a tela `#progresso` do protótipo validado (linha ~272): as cinco partes
 * em linguagem do aluno, para que ele saiba o tamanho do caminho antes de
 * começar e possa parar sem se perder.
 *
 * **Os rótulos são do protótipo, verbatim.** "Seu compromisso", "Como você
 * controla os gastos" — não são tradução dos nomes técnicos dos blocos
 * ("Pacto da Virada", "Autopercepção e controle"), e a diferença importa: o
 * aluno não sabe o que é um Bloco 2, e não deveria precisar saber.
 *
 * ## Por que esta tela NÃO marca partes como concluídas
 *
 * A primeira versão comparava `respondidas` (do servidor) com os totais
 * estáticos dos blocos (16/15/57/49/58 = 195) para pintar "Feito" em cada
 * parte. Isso somava duas contagens incompatíveis e produzia duas
 * afirmações falsas:
 *
 * 1. **Números incoerentes na mesma tela.** `contar_coleta` é dinâmico e conta
 *    ocorrências POR ITEM de todos os blocos: com três dívidas cadastradas o
 *    total real é 172, não 195 — e o Bloco 5 sozinho responde por 108 delas
 *    (36 perguntas × 3 fichas). O topo diria "0 de 172" com a lista somando
 *    195 logo abaixo.
 * 2. **"Feito" na parte errada.** Só há 8 perguntas ABERTAS no Bloco 1 sem
 *    respostas; responder o bloco inteiro nunca alcançaria 16, então a parte
 *    1 jamais seria marcada. Pior: responder 16 campos de dívida marcaria "Seu
 *    compromisso" como feita sem o aluno ter tocado nela.
 *
 * O servidor não expõe progresso por bloco, e derivá-lo aqui seria o cliente
 * contando um conjunto que ele não conhece — `RF-45`/`RF-05`. Então a tela
 * mostra o que é verdade: **o total geral, que vem do servidor, e as cinco
 * partes como mapa do caminho**. Progresso por parte é `OQ-31`, registrada.
 */
import Botao from '../componentes/Botao'
import Tela from '../componentes/Tela'
import type { Inicio } from '../tipos'

interface TelaProgressoProps {
  /** O mesmo payload da tela Início — uma requisição serve as duas. */
  inicio: Inicio | null
  voltar: () => void
  continuar: () => void
  /**
   * Abre a lista de dívidas — `RF-53`, `AC-04`.
   *
   * O CRUD de fichas repetíveis não tem outro caminho na interface desde que
   * a barra de abas ("Dívidas") morreu. Sem esta porta o aluno não cadastra
   * nem remove dívida, e o inventário do Bloco 5 fica travado no que ele
   * declarou de primeira.
   */
  verFichas?: () => void
}

/**
 * As cinco partes, na ordem em que o aluno as percorre.
 *
 * Sem contagem de perguntas: o número de uma ficha repetível não é uma
 * propriedade da parte (depende de quantas dívidas o aluno tem), e o
 * protótipo sabia disso — na parte 5 ele escreve "3 dívidas cadastradas ·
 * falta 1 valor", não "58 perguntas".
 */
const PARTES: readonly string[] = [
  'Seu compromisso',
  'Como você controla os gastos',
  'O que entra e o que sai por mês',
  'Salário, margem e o que você tem',
  'Suas dívidas, uma por uma',
]

export default function TelaProgresso({
  inicio,
  voltar,
  continuar,
  verFichas,
}: TelaProgressoProps) {
  const progresso = inicio?.progresso ?? null
  const pct =
    progresso && progresso.total > 0
      ? Math.round((progresso.respondidas / progresso.total) * 100)
      : 0

  return (
    <Tela
      titulo="Onde você está"
      voltar={voltar}
      acoes={
        <>
          <Botao onClick={continuar}>Continuar de onde parei</Botao>
          {verFichas && (
            <Botao variante="discreto" onClick={verFichas}>
              Ver e editar minhas dívidas
            </Botao>
          )}
        </>
      }
    >
      <p className="lead">Cinco partes. Você pode parar quando quiser e voltar depois.</p>

      {/* O total é o do servidor, e é o único número desta tela. O
          denominador varia conforme o aluno responde (perguntas abrem e
          fecham por condicional) e isso é correto — ver `RF-62`. */}
      {progresso && progresso.total > 0 && (
        <div className="cartao">
          <div className="linha">
            <span>Você já respondeu</span>
            <strong>
              {progresso.respondidas} de {progresso.total}
            </strong>
          </div>
          <div className="bar">
            <i style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      <div className="lista">
        {PARTES.map((rotulo, indice) => (
          <div className="item" key={rotulo}>
            <span className="num">{indice + 1}</span>
            <div className="flex-1">{rotulo}</div>
          </div>
        ))}
      </div>

      <p className="nota">
        Depois disso, o PIQ calcula o seu plano e uma pessoa da equipe confere antes de
        você receber.
      </p>
    </Tela>
  )
}
