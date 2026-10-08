/**
 * "Seu plano em números" — `RF-77`/`RF-78`, `T-375`. Uma LINHA por caminho,
 * todas na mesma escala de meses: vermelho (se nada mudar), azul (seguindo o
 * plano) e verde (plano acelerado, só com o valor extra informado). Na barra,
 * um círculo numerado por dívida quitada (anel dourado na primeira); abaixo,
 * o mês a mês de cada caminho e "Quando cada dívida termina". Texto e números
 * chegam prontos do servidor (Lei nº 3); `mes_fim`/`escala`/`marcos` são só
 * geometria. A cor nunca é o único sinal: título, veredito e tabela em texto.
 */
import type {
  AnoDosCaminhos,
  CaminhoDoPrognostico,
  PrognosticoDoPlano as PrognosticoTipo,
  QuandoTermina,
} from "../tipos";

const COR = {
  vermelho: {
    borda: "border-l-bad",
    texto: "text-bad",
    barra: "bg-bad",
    anel: "border-bad",
    claro: "bg-bad-soft",
  },
  azul: {
    borda: "border-l-azul",
    texto: "text-azul",
    barra: "bg-azul",
    anel: "border-azul",
    claro: "bg-azul-soft",
  },
  verde: {
    borda: "border-l-accent",
    texto: "text-accent",
    barra: "bg-accent",
    anel: "border-accent",
    claro: "bg-accent-soft",
  },
} as const;

function porcentagem(mes: number, escala: number): string {
  return `${escala > 0 ? (mes / escala) * 100 : 0}%`;
}

function Linha({
  caminho,
  eixoInicio,
}: {
  caminho: CaminhoDoPrognostico;
  eixoInicio: string;
}) {
  const cor = COR[caminho.cor];
  return (
    <article
      data-caminho={caminho.cor}
      className={`rounded-piq border border-l-8 border-line bg-surface p-4 ${cor.borda}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <h3 className={`m-0 text-lg ${cor.texto}`}>{caminho.titulo}</h3>
        <p className="m-0 text-lg font-bold text-ink sm:text-right">
          {caminho.veredito}
        </p>
      </div>
      <p className="text-muted mb-2 mt-0.5 text-sm">{caminho.nota}</p>
      {caminho.marcador && (
        <p
          className="text-ink m-0 mb-1 text-right text-sm font-bold"
          style={{
            width: porcentagem(caminho.mes_fim, caminho.escala),
            minWidth: "9rem",
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
            className={`absolute top-1/2 flex h-6 w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-surface text-xs font-bold text-ink ${
              marco.mes === caminho.mes_primeira_quitacao
                ? "border-[3px] border-[#D9A400]"
                : `border-2 ${cor.anel}`
            }`}
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
    </article>
  );
}

function MesAMes({
  anos,
  textos,
}: {
  anos: AnoDosCaminhos[];
  textos: Record<string, string>;
}) {
  return (
    <div className="flex flex-col gap-3 overflow-x-auto">
      {anos.map((ano) => (
        <div key={ano.numero} className="flex min-w-max flex-col gap-1">
          <div className="flex items-center gap-1">
            <span className="w-28 flex-none text-sm font-bold">
              {textos.rotulo_ano || "Ano"} {ano.numero}
            </span>
            {ano.faixas[0]?.meses.map((m) => (
              <span
                key={m.mes}
                className="text-muted w-9 flex-none text-center text-xs"
              >
                {m.mes}
              </span>
            ))}
          </div>
          {ano.faixas.map((faixa) => (
            <div
              key={faixa.cor}
              data-faixa={faixa.cor}
              className="flex items-center gap-1"
            >
              <span
                className={`w-28 flex-none text-xs font-bold ${COR[faixa.cor].texto}`}
              >
                {faixa.rotulo}
              </span>
              {faixa.meses.map((m) => (
                <span
                  key={m.mes}
                  data-tipo={m.tipo}
                  title={`Mês ${m.mes}`}
                  className={`h-6 w-9 flex-none rounded text-center text-xs font-bold leading-6 text-white ${
                    m.tipo === "depois"
                      ? "border border-dashed border-line bg-surface"
                      : m.tipo === "comum"
                        ? COR[faixa.cor].claro
                        : `${COR[faixa.cor].barra} ${m.tipo === "primeira" ? "ring-2 ring-[#D9A400]" : ""}`
                  }`}
                >
                  {m.numeros.join(",")}
                </span>
              ))}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

/** "Quando cada dívida termina" — uma linha por dívida, uma coluna por caminho. */
export function QuandoCadaDividaTermina({
  tabela,
  textos,
}: {
  tabela: QuandoTermina;
  textos: Record<string, string>;
}) {
  return (
    <section className="cartao" aria-labelledby="titulo-quando-termina">
      <h3 id="titulo-quando-termina" className="m-0">
        {textos.quando_termina_titulo || "Quando cada dívida termina"}
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-muted text-left text-xs">
              <th scope="col" className="py-1 pr-3">
                {textos.coluna_divida || "Dívida"}
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
                  <span className="mr-1 font-bold text-accent">
                    {linha.numero}
                  </span>
                  {linha.nome}
                </th>
                {linha.meses.map((mes, i) => (
                  <td
                    key={tabela.colunas[i]}
                    className="py-1.5 pr-3 tabular-nums"
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
  );
}

export default function PrognosticoDoPlano({
  prognostico,
  textos = {},
}: {
  prognostico: PrognosticoTipo;
  textos?: Record<string, string>;
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
            eixoInicio={textos.eixo_inicio || "Mês 1 (início)"}
          />
        ))}
      </div>
      {(prognostico.legenda ?? []).length > 0 && (
        <div
          className="text-muted m-0 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs"
          data-legenda
        >
          <strong>{textos.legenda_titulo || "Números nas barras:"}</strong>
          {(prognostico.legenda ?? []).map((item) => (
            <span key={item.numero} className="inline-flex items-center gap-1">
              <span className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-muted bg-surface font-bold text-ink">
                {item.numero}
              </span>
              {item.nome}
            </span>
          ))}
          <span className="inline-flex items-center gap-1">
            <span className="flex h-5 w-5 items-center justify-center rounded-full border-[3px] border-[#D9A400] bg-surface font-bold text-ink">
              1
            </span>
            {textos.legenda_primeira ||
              "anel dourado: sua primeira dívida quitada"}
          </span>
        </div>
      )}
      {(prognostico.mes_a_mes ?? []).length > 0 && (
        <>
          <h3 className="m-0">
            {textos.mes_a_mes_titulo || "Mês a mês, em cada caminho"}
          </h3>
          {textos.mes_a_mes_intro && (
            <p className="text-muted m-0 text-sm">{textos.mes_a_mes_intro}</p>
          )}
          <MesAMes anos={prognostico.mes_a_mes} textos={textos} />
        </>
      )}
    </section>
  );
}
