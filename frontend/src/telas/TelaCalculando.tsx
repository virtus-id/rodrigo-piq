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
 */
import { useEffect, useState } from 'react'

import Tela from '../componentes/Tela'
import { obterProgressoDoCalculo } from '../services/api'

interface TelaCalculandoProps {
  casoId: string
  voltar: () => void
  /** Chamado quando o cálculo sai de `CALCULANDO` — em qualquer direção. */
  onTerminou: () => void
}

/** Intervalo do polling. O NFR fixa p95 < 10 s para o Bloco 6 completo. */
const INTERVALO_MS = 2000

export default function TelaCalculando({
  casoId,
  voltar,
  onTerminou,
}: TelaCalculandoProps) {
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    let ativo = true

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

    void consultar()
    const timer = setInterval(() => void consultar(), INTERVALO_MS)
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
      <div className="pulse" aria-hidden="true" />
      <p className="lead" role="status" aria-live="polite">
        Isso leva menos de um minuto. Você não precisa fazer nada.
      </p>
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
