/**
 * "Seu plano em números" — `RF-77`/`RF-78`, `T-375`. Uma LINHA por caminho,
 * todas na mesma escala de meses: vermelho (se nada mudar), azul (seguindo o
 * plano) e verde (plano acelerado, só com o valor extra informado). Na barra,
 * um ponto por dívida quitada, com "M<mês>" acima, e a lista "M7 · Quita …"
 * dentro do próprio bloco; depois do capítulo, "Quando cada dívida termina". Texto e números
 * chegam prontos do servidor (Lei nº 3); `mes_fim`/`escala`/`marcos` são só
 * geometria. A cor nunca é o único sinal: título, veredito e tabela em texto.
 */
import type {
  CaminhoDoPrognostico,
  PrognosticoDoPlano as PrognosticoTipo,
  QuandoTermina,
} from '../tipos'

const COR = {
  vermelho: {
    borda: 'border-l-bad',
    texto: 'text-bad',
    barra: 'bg-bad',
    anel: 'border-bad',
    claro: 'bg-bad-soft',
  },
  azul: {
    borda: 'border-l-azul',
    texto: 'text-azul',
    barra: 'bg-azul',
    anel: 'border-azul',
    claro: 'bg-azul-soft',
  },
  verde: {
    borda: 'border-l-accent',
    texto: 'text-accent',
    barra: 'bg-accent',
    anel: 'border-accent',
    claro: 'bg-accent-soft',
  },
} as const

function porcentagem(mes: number, escala: number): string {
  return `${escala > 0 ? (mes / escala) * 100 : 0}%`
}

/** Linha do rótulo "M7": dois marcos próximos alternam a linha para não se sobrepor. */
function linhasDosRotulos(marcos: { mes: number }[], escala: number): number[] {
  const ultimo = [-100, -100]
  return marcos.map((marco) => {
    const x = escala > 0 ? (marco.mes / escala) * 100 : 0
    const linha = x - ultimo[0] >= 6 ? 0 : 1
    ultimo[linha] = x
    return linha
  })
}

function Linha({ caminho, eixoInicio }: { caminho: CaminhoDoPrognostico; eixoInicio: string }) {
  const cor = COR[caminho.cor]
  const marcos = caminho.marcos ?? []
  const linhas = linhasDosRotulos(marcos, caminho.escala)
  return (
    <article data-caminho={caminho.cor} className="rounded-piq border border-line bg-surface p-4">
      <h3 className={`m-0 text-xl ${cor.texto}`}>{caminho.titulo}</h3>
      <p className="text-muted m-0 mt-1 text-sm">{caminho.nota}</p>
      <p className="m-0 mt-2 text-ink">{caminho.veredito}</p>
      <div
        role="img"
        aria-label={`${caminho.titulo}. ${caminho.veredito}`}
        className={`relative mb-1 h-2 w-full rounded-full bg-line ${marcos.length > 0 ? 'mt-9' : 'mt-4'}`}
      >
        <div
          className={`h-full rounded-full ${cor.barra}`}
          style={{ width: porcentagem(caminho.mes_fim, caminho.escala) }}
        />
        {marcos.map((marco, i) => (
          <span
            key={`${marco.mes}-${marco.numero}`}
            data-marco={marco.mes}
            className={`absolute h-3.5 w-3.5 -translate-x-1/2 rounded-full ${cor.barra}`}
            style={{ left: porcentagem(marco.mes, caminho.escala), top: '-3px' }}
          >
            <span
              className={`absolute left-1/2 -translate-x-1/2 text-xs font-bold ${cor.texto}`}
              style={{ bottom: linhas[i] === 0 ? '1.1rem' : '2.1rem' }}
            >
              M{marco.mes}
            </span>
          </span>
        ))}
      </div>
      <div className="text-muted flex justify-between text-xs">
        <span>{eixoInicio}</span>
        <span>Mês {caminho.escala}</span>
      </div>
      {(caminho.itens ?? []).length > 0 && (
        <ul
          className={`m-0 mt-2 grid list-none gap-x-4 gap-y-0.5 p-0 text-sm font-bold sm:grid-cols-2 lg:grid-cols-3 ${cor.texto}`}
        >
          {caminho.itens.map((item) => (
            <li key={item} data-item>
              {item}
            </li>
          ))}
        </ul>
      )}
      <dl className="m-0 mt-3 grid gap-x-8 gap-y-2 text-ink sm:grid-cols-2">
        {caminho.destaques.map((item) => (
          <div key={item.rotulo}>
            <dt className="text-muted text-sm">{item.rotulo}</dt>
            <dd className="m-0 text-xl font-bold tabular-nums">{item.valor}</dd>
          </div>
        ))}
      </dl>
      {caminho.economia && <p className={`m-0 mt-3 font-bold ${cor.texto}`}>{caminho.economia}</p>}
    </article>
  )
}

/** "Quando cada dívida termina" — uma linha por dívida, uma coluna por caminho. */
export function QuandoCadaDividaTermina({
  tabela,
  textos,
}: {
  tabela: QuandoTermina
  textos: Record<string, string>
}) {
  return (
    <section className="cartao" aria-labelledby="titulo-quando-termina">
      <h3 id="titulo-quando-termina" className="m-0">
        {textos.quando_termina_titulo || 'Quando cada dívida termina'}
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-muted text-left text-xs">
              <th scope="col" className="py-1 pr-3">
                {textos.coluna_divida || 'Dívida'}
              </th>
              {tabela.colunas.map((coluna, i) => (
                <th
                  key={coluna}
                  scope="col"
                  className={`whitespace-nowrap px-3 py-1 font-bold ${COR[tabela.cores?.[i] ?? 'azul'].texto}`}
                >
                  {coluna}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tabela.linhas.map((linha) => (
              <tr key={linha.numero} className="border-t border-line">
                <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                  <span className="mr-1 font-bold text-accent">{linha.numero}</span>
                  {linha.nome}
                </th>
                {linha.meses.map((mes, i) => (
                  <td
                    key={tabela.colunas[i]}
                    data-coluna={tabela.cores?.[i] ?? 'azul'}
                    className={`whitespace-nowrap px-3 py-1.5 tabular-nums ${COR[tabela.cores?.[i] ?? 'azul'].claro}`}
                  >
                    {mes}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function PrognosticoDoPlano({
  prognostico,
  textos = {},
}: {
  prognostico: PrognosticoTipo
  textos?: Record<string, string>
}) {
  return (
    <section className="cartao" aria-labelledby="titulo-prognostico">
      <h2 id="titulo-prognostico">{prognostico.titulo}</h2>
      <p className="text-muted m-0">{prognostico.introducao}</p>
      <div className="flex flex-col gap-3">
        {prognostico.caminhos.map((caminho) => (
          <Linha
            key={caminho.cor}
            caminho={caminho}
            eixoInicio={textos.eixo_inicio || 'Mês 1 (início)'}
          />
        ))}
      </div>
    </section>
  )
}
