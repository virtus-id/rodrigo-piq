/**
 * As duas ações que mudam o plano do aluno — `RF-115`, `RF-118`, `RF-120`
 * (T-344).
 *
 * **Um lugar só.** O aluno chega pelo Início e também por "Minhas respostas":
 * as duas telas oferecem as mesmas ações, com a mesma confirmação. Cada tela
 * só diz o que fazer DEPOIS (`aoPedir`/`aoRetirar`); a regra — quando cada ação
 * existe — é do servidor (`pode_refazer_plano`, `pode_retomar_edicao`).
 *
 * **Confirmação em linha, nunca em um `window.confirm`.** O texto da
 * confirmação é parte do requisito (`AC-184`): o aluno precisa saber que o
 * plano será conferido de novo e que isso pode demorar na fila.
 */
import { useState } from 'react'

import { refazerPlano, retomarEdicao } from '../services/api'
import Botao from './Botao'

/** Roda a ação, com o estado de "confirmando", "enviando" e o erro do servidor. */
function useAcaoConfirmada(executar: () => Promise<unknown>, depois: () => void, erroPadrao: string) {
  const [confirmando, setConfirmando] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function confirmar() {
    setEnviando(true)
    setErro(null)
    try {
      await executar()
      setConfirmando(false)
      depois()
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : erroPadrao)
    } finally {
      setEnviando(false)
    }
  }

  return { confirmando, setConfirmando, enviando, erro, confirmar }
}

interface CartaoPlanoNovoProps {
  casoId: string
  /**
   * `true`: as respostas mudaram desde o plano (o servidor comparou) — o cartão
   * vira aviso. `false`/`null`/ausente: a ação neutra, sem afirmar mudança.
   */
  atualizado?: boolean | null
  /** O caso já voltou à coleta; a casca leva à tela que calcula. */
  aoPedir: () => void
}

/** "Gerar um novo plano com as minhas respostas" — `RF-118`, `RF-120`. */
export function CartaoPlanoNovo({ casoId, atualizado = null, aoPedir }: CartaoPlanoNovoProps) {
  const acao = useAcaoConfirmada(
    () => refazerPlano(casoId),
    aoPedir,
    'Não foi possível pedir o plano novo agora.',
  )

  return (
    <section
      className={atualizado === true ? 'aviso-atencao flex-col' : 'cartao'}
      aria-label="Plano novo"
    >
      {atualizado === true ? (
        <>
          <strong>Você atualizou suas respostas depois do seu plano.</strong>
          <p className="m-0">Quer enviá-las para gerar um novo plano?</p>
        </>
      ) : (
        <>
          <strong>Mudou algo? Você pode pedir um plano novo.</strong>
          <p className="nota">
            Seu plano atual continua disponível. Se você corrigiu ou atualizou respostas, um plano
            novo leva isso em conta.
          </p>
        </>
      )}

      {!acao.confirmando && (
        <Botao
          // Com mudança afirmada a ação é o ponto do aviso: botão de verdade.
          variante={atualizado === true ? 'secundario' : 'discreto'}
          className="self-start"
          onClick={() => acao.setConfirmando(true)}
        >
          Gerar um novo plano com as minhas respostas
        </Botao>
      )}

      {acao.confirmando && (
        <div className="flex flex-col gap-2" role="group" aria-label="Confirmar o plano novo">
          <p>
            <strong>
              Seu plano atual continua disponível. O plano novo será calculado com todas as suas
              respostas e conferido de novo pela equipe, o que pode levar o tempo da fila. Quando
              ficar pronto, ele substitui o atual.
            </strong>
          </p>
          <div className="flex flex-wrap gap-2">
            <Botao onClick={() => void acao.confirmar()} disabled={acao.enviando}>
              Pedir o plano novo
            </Botao>
            <Botao
              variante="discreto"
              onClick={() => acao.setConfirmando(false)}
              disabled={acao.enviando}
            >
              Cancelar
            </Botao>
          </div>
        </div>
      )}

      {acao.erro && (
        <p role="alert" className="aviso-erro">
          {acao.erro}
        </p>
      )}
    </section>
  )
}

interface CartaoRetirarProps {
  casoId: string
  /** O que o cartão diz sobre a conferência — varia por tela. */
  explicacao: string
  /** O caso voltou à coleta: a tela relê ou leva a "Minhas respostas". */
  aoRetirar: () => void
}

/** "Quero editar minhas respostas" — retira o plano da conferência (`RF-115`). */
export function CartaoRetirarDaConferencia({ casoId, explicacao, aoRetirar }: CartaoRetirarProps) {
  const acao = useAcaoConfirmada(
    () => retomarEdicao(casoId),
    aoRetirar,
    'Não foi possível retirar o plano agora.',
  )

  return (
    <section className="cartao" aria-label="Plano em conferência">
      <strong>Seu plano está em conferência.</strong>
      <p className="nota">{explicacao}</p>

      {!acao.confirmando && (
        <Botao variante="discreto" className="self-start" onClick={() => acao.setConfirmando(true)}>
          Quero editar minhas respostas
        </Botao>
      )}

      {acao.confirmando && (
        <div className="flex flex-col gap-2" role="group" aria-label="Confirmar a retirada">
          <p>
            <strong>
              Seu plano sai da conferência. Quando você enviar de novo, ele volta para a fila.
            </strong>
          </p>
          <div className="flex flex-wrap gap-2">
            <Botao onClick={() => void acao.confirmar()} disabled={acao.enviando}>
              Retirar o plano e editar
            </Botao>
            <Botao
              variante="discreto"
              onClick={() => acao.setConfirmando(false)}
              disabled={acao.enviando}
            >
              Cancelar
            </Botao>
          </div>
        </div>
      )}

      {acao.erro && (
        <p role="alert" className="aviso-erro">
          {acao.erro}
        </p>
      )}
    </section>
  )
}
