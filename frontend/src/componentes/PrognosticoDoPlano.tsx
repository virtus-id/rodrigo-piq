/**
 * "Seu plano em números" — `RF-77`/`RF-78`, `T-375`. Uma LINHA por caminho,
 * todas na mesma escala de meses: vermelho (se nada mudar), azul (seguindo o
 * plano) e verde (plano acelerado, só com o valor extra informado). Na barra,
 * um círculo numerado por dívida quitada, e o quadro dessas dívidas (número,
 * nome e mês) dentro do próprio bloco; abaixo,
 * o mês a mês de cada caminho e "Quando cada dívida termina". Texto e números
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

function Linha({
  caminho,
  eixoInicio,
  textos,
}: {
  caminho: CaminhoDoPrognostico
  eixoInicio: string
  textos: Record<string, string>
}) {
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
          style={{
            width: porcentagem(caminho.mes_fim, caminho.escala),
            minWidth: '9rem',
          }}
        >
          {caminho.marcador}
        </p>
      )}
      <div
        role="img"
        aria-label={`${caminho.titulo}. ${caminho.veredito}`}
        className="relative my-2 h-3.5 w-full rounded-full bg-line"
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
        {(caminho.marcos ?? []).map((marco) => (
          <span
            key={`${marco.mes}-${marco.numero}`}
            data-marco={marco.numero}
            className={`absolute top-1/2 flex h-6 w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 bg-surface text-xs font-bold text-ink ${cor.anel}`}
            style={{ left: porcentagem(marco.mes, caminho.escala) }}
          >
            {marco.numero}
          </span>
        ))}
      </div>
      <div className="text-muted flex justify-between text-xs">
        <span>{eixoInicio}</span>
        <span>Mês {caminho.escala}</span>
      </div>
      <dl className="m-0 mt-2 flex flex-wrap gap-x-8 gap-y-1 text-ink">
        {caminho.destaques.map((item) => (
          <div key={item.rotulo}>
            <dt className="text-muted text-xs">{item.rotulo}</dt>
            <dd className="m-0 font-bold tabular-nums">{item.valor}</dd>
          </div>
        ))}
      </dl>
      {(caminho.itens ?? []).length > 0 && (
        <div
          role="group"
          aria-label={textos.itens_titulo || 'Dívidas quitadas neste caminho'}
          className="mt-3 border-t border-line pt-2"
        >
          <p className="text-muted m-0 text-xs">
            {textos.itens_titulo || 'Dívidas quitadas neste caminho'}
          </p>
          <ul className="m-0 mt-1 flex list-none flex-wrap gap-x-4 gap-y-2 p-0">
            {caminho.itens.map((item) => (
              <li key={`${item.numero}-${item.quando}`} data-item={item.numero} className="w-40">
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full border-2 bg-surface text-xs font-bold text-ink ${cor.anel}`}
                >
                  {item.numero}
                </span>
                <span className="block text-sm font-bold text-ink">{item.nome}</span>
                <span className="text-muted block text-xs">{item.quando}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
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
              {tabela.colunas.map((coluna) => (
                <th key={coluna} scope="col" className="py-1 pr-3">
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
                  <td key={tabela.colunas[i]} className="py-1.5 pr-3 tabular-nums">
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
            textos={textos}
          />
        ))}
      </div>
    </section>
  )
}
