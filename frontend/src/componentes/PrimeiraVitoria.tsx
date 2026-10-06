/**
 * "Sua primeira dívida quitada" — o ponto alto do plano (capítulo 4): destaque da primeira quitação prevista,
 * com um selo animado (`.selo-vitoria`, suprimido para quem pede menos
 * movimento). `mes`/`divida` são leitura do cronograma gravado
 * (`PrimeiraVitoria`); nenhum cálculo aqui.
 */
import type { PrimeiraVitoria as PrimeiraVitoriaTipo } from '../tipos'
import Icone from './Icone'

interface PrimeiraVitoriaProps {
  primeiraVitoria: PrimeiraVitoriaTipo
  titulo: string
  complemento: string
}

export default function PrimeiraVitoria({
  primeiraVitoria,
  titulo,
  complemento,
}: PrimeiraVitoriaProps) {
  return (
    <section
      className="cartao border-2 border-warn bg-accent-soft"
      aria-labelledby="titulo-primeira-vitoria"
    >
      <h2 id="titulo-primeira-vitoria">{titulo || 'Sua primeira dívida quitada'}</h2>
      <div className="flex flex-wrap items-center gap-4">
        <div className="selo-vitoria flex flex-none flex-col items-center rounded-piq border-2 border-warn bg-surface px-6 py-3 text-warn">
          <Icone nome="trofeu" />
          <span className="text-xs uppercase tracking-wide">Mês</span>
          <span className="text-4xl font-bold">{primeiraVitoria.mes}</span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="m-0 font-bold">
            No Mês {primeiraVitoria.mes}, a dívida {primeiraVitoria.divida} estará quitada.
          </p>
          {complemento && <p className="text-muted mb-0 mt-1">{complemento}</p>}
        </div>
      </div>
    </section>
  )
}
