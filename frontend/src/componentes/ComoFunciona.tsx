/**
 * "Como o seu plano funciona" — revisão de design (2026-10-03): três
 * quadros, cada um com ícone, título curto e explicação, no lugar de uma
 * lista numerada com uma ilustração abstrata. Passos e títulos vêm do
 * servidor (`como_funciona`, `como_funciona_rotulos`).
 */
import Icone from './Icone'
import type { NomeDoIcone } from './Icone'

interface ComoFuncionaProps {
  passos: string[]
  rotulos: string[]
  titulo: string
}

const ICONES: NomeDoIcone[] = ['passo', 'concluido', 'taxa']

export default function ComoFunciona({ passos, rotulos, titulo }: ComoFuncionaProps) {
  if (passos.length === 0) return null

  return (
    <section className="cartao" aria-labelledby="titulo-como-funciona">
      <h2 id="titulo-como-funciona">{titulo || 'Como o seu plano funciona'}</h2>
      <ol className="m-0 grid list-none gap-3 p-0">
        {passos.map((passo, indice) => (
          <li key={passo} className="flex gap-3 rounded-piq border border-line p-3">
            <span className="grid h-10 w-10 flex-none place-items-center rounded-full bg-accent-soft text-accent">
              <Icone nome={ICONES[indice] ?? 'avancar'} />
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <h3 className="m-0 text-base">
                {indice + 1}. {rotulos[indice] ?? ''}
              </h3>
              <p className="m-0 text-sm">{passo}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
