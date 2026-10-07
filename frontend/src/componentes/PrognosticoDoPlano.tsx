/**
 * "Seu prognóstico" — `RF-77`/`RF-78`. Uma LINHA por caminho, todas na mesma
 * escala de meses: vermelho (se nada mudar), azul (seguindo o plano) e verde
 * (plano acelerado, só com o valor extra informado). Frase, barra e até três
 * números chegam prontos do servidor (Lei nº 3); `mes_fim`/`escala` são só a
 * geometria da barra. A cor nunca é o único sinal: título e veredito em texto.
 */
import type { CaminhoDoPrognostico, PrognosticoDoPlano as PrognosticoTipo } from '../tipos'

const COR = {
  vermelho: { borda: 'border-l-bad', texto: 'text-bad', barra: 'bg-bad' },
  azul: { borda: 'border-l-azul', texto: 'text-azul', barra: 'bg-azul' },
  verde: { borda: 'border-l-accent', texto: 'text-accent', barra: 'bg-accent' },
} as const

function porcentagem(mes: number, escala: number): string {
  return `${escala > 0 ? (mes / escala) * 100 : 0}%`
}

function Linha({ caminho }: { caminho: CaminhoDoPrognostico }) {
  const cor = COR[caminho.cor]
  return (
    <article
      data-caminho={caminho.cor}
      className={`rounded-piq border border-l-8 border-line bg-surface p-4 ${cor.borda}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <h3 className={`m-0 text-lg ${cor.texto}`}>{caminho.titulo}</h3>
        <p className="m-0 text-lg font-bold text-ink sm:text-right">{caminho.veredito}</p>
      </div>
      <p className="text-muted mb-2 mt-0.5 text-sm">{caminho.nota}</p>
      {caminho.marcador && (
        <p
          className="text-ink m-0 mb-1 text-right text-sm font-bold"
          style={{ width: porcentagem(caminho.mes_fim, caminho.escala), minWidth: '9rem' }}
        >
          {caminho.marcador}
        </p>
      )}
      <div
        role="img"
        aria-label={`${caminho.titulo}. ${caminho.veredito}`}
        className="relative h-3.5 w-full rounded-full bg-line"
      >
        <div
          className={`h-full rounded-full ${cor.barra}`}
          style={{ width: porcentagem(caminho.mes_fim, caminho.escala) }}
        />
        {caminho.mes_sombra !== null && (
          <div
            className="absolute inset-y-0 left-0 rounded-full border border-dashed border-azul"
            style={{ width: porcentagem(caminho.mes_sombra, caminho.escala) }}
          />
        )}
      </div>
      <dl className="m-0 mt-2 flex flex-wrap gap-x-8 gap-y-1 text-ink">
        {caminho.destaques.map((item) => (
          <div key={item.rotulo}>
            <dt className="text-muted text-xs">{item.rotulo}</dt>
            <dd className="m-0 font-bold tabular-nums">{item.valor}</dd>
          </div>
        ))}
      </dl>
    </article>
  )
}

export default function PrognosticoDoPlano({ prognostico }: { prognostico: PrognosticoTipo }) {
  return (
    <section className="cartao" aria-labelledby="titulo-prognostico">
      <h2 id="titulo-prognostico">{prognostico.titulo}</h2>
      <p className="text-muted m-0">{prognostico.introducao}</p>
      <div className="flex flex-col gap-3">
        {prognostico.caminhos.map((caminho) => (
          <Linha key={caminho.cor} caminho={caminho} />
        ))}
      </div>
    </section>
  )
}
