/**
 * "Seu prognóstico: três caminhos" — `RF-77`/`RF-78`. Vermelho (se nada
 * mudar), azul (seguindo o plano) e verde (plano + esforço extra, só quando o
 * aluno informou o valor). Todo texto e número chega pronto do servidor
 * (Lei nº 3); a cor nunca é o único sinal — cada cartão tem o próprio título.
 */
import type { PrognosticoDoPlano as PrognosticoTipo } from '../tipos'

const COR = {
  vermelho: 'border-t-bad text-bad',
  azul: 'border-t-azul text-azul',
  verde: 'border-t-accent text-accent',
} as const

export default function PrognosticoDoPlano({ prognostico }: { prognostico: PrognosticoTipo }) {
  return (
    <section className="cartao" aria-labelledby="titulo-prognostico">
      <h2 id="titulo-prognostico">{prognostico.titulo}</h2>
      <p className="text-muted m-0">{prognostico.introducao}</p>
      <div className="grid gap-3 md:grid-cols-3">
        {prognostico.caminhos.map((caminho) => (
          <article
            key={caminho.cor}
            data-caminho={caminho.cor}
            className={`rounded-piq border border-line border-t-8 bg-surface p-4 ${COR[caminho.cor]}`}
          >
            <h3 className="m-0 text-lg">{caminho.titulo}</h3>
            <p className="text-ink mt-1 text-sm">{caminho.descricao}</p>
            <dl className="m-0 text-ink">
              {caminho.linhas.map((linha) => (
                <div key={linha.rotulo} className="mt-2">
                  <dt className="text-muted text-sm">{linha.rotulo}</dt>
                  <dd className="m-0 font-bold tabular-nums">{linha.valor}</dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </div>
    </section>
  )
}
