/**
 * O Bloco 6 rodando — `RF-16`, `AC-12`, `EC-06`, `EC-25` (T-150).
 *
 * É a tela `#calculando` do protótipo (linha ~490). O aluno não faz nada
 * aqui; a tela existe para que a espera seja legível em vez de parecer
 * travamento.
 *
 * **O polling para quando o estado muda, e a tela avisa quem a hospeda.** Não
 * é a tela que decide para onde ir — ela reporta que terminou, e a casca
 * navega. Quem sabe o próximo passo é `/inicio` (`RF-58`).
 *
 * **`EC-25`: erro de cálculo não vira tela de erro.** Se o cálculo falhar, o
 * servidor põe o caso em `ERRO_DE_CALCULO`, cuja mensagem é *"Seu plano está
 * em nova análise."* — a mesma fase `revisao`. O aluno não pode agir sobre a
 * falha, e mostrá-la só acrescentaria medo a quem já está endividado. Quem
 * precisa saber do erro é o operador, no painel dele.
 *
 * **A tela dispara o cálculo antes de acompanhá-lo (T-196).** Um `POST`,
 * uma vez, e só então o polling. `409` é o caso já em `CALCULANDO` (duplo
 * clique, F5): segue para o polling como sucesso. Recusa ANTES da transição
 * (`400` pendência, `422` montagem, `503`) não é `EC-25` — o caso segue em
 * `COLETA_INICIAL` e o aluno pode agir, então a tela mostra o motivo e as
 * pendências em vez de voltar ao Início em silêncio (T-197). Cada pendência
 * aparece pelo enunciado, com um "Responder" que abre a pergunta (T-210);
 * a navegação é da casca, como em `TelaFichas`.
 */
import { useEffect, useState } from 'react'

import Tela from '../componentes/Tela'
import {
  dispararCalculo,
  ErroHttp,
  obterProgressoDoCalculo,
  type PendenciaDoCalculo,
} from '../services/api'

interface TelaCalculandoProps {
  casoId: string
  voltar: () => void
  /** Chamado quando o cálculo sai de `CALCULANDO` — em qualquer direção. */
  onTerminou: () => void
  /** Abre a pergunta pendente — no item dela, quando é de ficha. */
  onAbrirPergunta: (idPergunta: string, itemId: string | null) => void
}

/** Intervalo do polling. O NFR fixa p95 < 10 s para o Bloco 6 completo. */
const INTERVALO_MS = 2000

/** Status cuja mensagem o servidor escreveu para o aluno ler. */
const RECUSAS_LEGIVEIS = [400, 422, 503]

interface Recusa {
  mensagem: string
  pendencias: readonly PendenciaDoCalculo[]
}

export default function TelaCalculando({
  casoId,
  voltar,
  onTerminou,
  onAbrirPergunta,
}: TelaCalculandoProps) {
  const [erro, setErro] = useState<string | null>(null)
  const [recusa, setRecusa] = useState<Recusa | null>(null)

  useEffect(() => {
    let ativo = true
    let timer: ReturnType<typeof setInterval> | undefined

    async function consultar() {
      try {
        const progresso = await obterProgressoDoCalculo(casoId)
        if (!ativo) return
        // `calculando: false` cobre os dois desfechos — snapshot gravado ou
        // erro. A tela não os distingue de propósito (`EC-25`); quem decide
        // o que o aluno vê a seguir é `/inicio`.
        if (!progresso.calculando) onTerminou()
      } catch {
        if (ativo) setErro('Não foi possível acompanhar o cálculo agora.')
      }
    }

    async function iniciar() {
      try {
        await dispararCalculo(casoId)
      } catch (e) {
        const jaCalculando = e instanceof ErroHttp && e.status === 409
        if (!jaCalculando) {
          if (!ativo) return
          setRecusa(
            e instanceof ErroHttp && RECUSAS_LEGIVEIS.includes(e.status)
              ? { mensagem: e.detalhe, pendencias: e.pendencias }
              : { mensagem: 'Não foi possível iniciar o cálculo agora.', pendencias: [] },
          )
          return
        }
      }
      if (!ativo) return
      void consultar()
      timer = setInterval(() => void consultar(), INTERVALO_MS)
    }

    void iniciar()
    return () => {
      ativo = false
      clearInterval(timer)
    }
  }, [casoId, onTerminou])

  return (
    <Tela titulo="Estamos montando o seu plano" voltar={voltar}>
      {/* `aria-hidden`: o indicador é decorativo. Quem usa leitor de tela
          recebe a informação pelo `role="status"` abaixo, que diz o que está
          acontecendo — um spinner anunciado não diria nada. */}
      {recusa ? (
        <div role="alert" className="aviso-atencao">
          <p>{recusa.mensagem}</p>
          {recusa.pendencias.length > 0 && (
            <ul>
              {recusa.pendencias.map((p) => (
                <li key={`${p.ID}:${p.item_id ?? ''}`}>
                  {p.enunciado}{' '}
                  <button
                    type="button"
                    className="font-bold text-accent"
                    aria-label={`Responder: ${p.enunciado}`}
                    onClick={() => onAbrirPergunta(p.ID, p.item_id)}
                  >
                    Responder
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <>
          <div className="pulse" aria-hidden="true" />
          <p className="lead" role="status" aria-live="polite">
            Isso leva menos de um minuto. Você não precisa fazer nada.
          </p>
        </>
      )}
      {erro && (
        <p role="alert" className="aviso-atencao">
          {/* A falha é do POLLING, não do cálculo: o servidor segue
              calculando. Dizer "seu plano falhou" aqui seria mentira. */}
          {erro} Seu plano continua sendo calculado.
        </p>
      )}
    </Tela>
  )
}
