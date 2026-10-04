/**
 * "Perguntas frequentes" — perguntas e respostas fixas, de
 * `textos-canonicos.yaml` (não dependem do caso). Na tela ficam
 * recolhíveis (precedente de `<details>` de `PainelFotografia.tsx`); no PDF
 * aparecem abertas, porque no papel nada se clica.
 */
import Icone from './Icone'

interface DuvidasDoPlanoProps {
  duvidas: { pergunta: string; resposta: string }[]
  titulo: string
}

export default function DuvidasDoPlano({ duvidas, titulo }: DuvidasDoPlanoProps) {
  if (duvidas.length === 0) return null

  return (
    <section className="cartao" aria-labelledby="titulo-duvidas">
      <h2 id="titulo-duvidas" className="flex items-center gap-2">
        <Icone nome="duvida" />
        {titulo || 'Perguntas frequentes'}
      </h2>
      {duvidas.map((item) => (
        <details key={item.pergunta}>
          <summary className="font-bold">{item.pergunta}</summary>
          <p className="text-muted mt-1">{item.resposta}</p>
        </details>
      ))}
    </section>
  )
}
