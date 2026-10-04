/**
 * Linha do tempo das dívidas (estilo Gantt) — plano amigável (2026-10-03).
 *
 * Uma barra por posição de `ordem`, do Mês 1 até `mes_de_quitacao` (ou até
 * `prazoTotalMeses` quando a dívida não quita dentro do horizonte
 * simulado). É o visual principal: mostra de uma vez a ordem, a dívida que
 * acaba primeiro e a data de chegada.
 *
 * **Redesenho (2026-10-03, feedback do usuário: "tem a informação mas eu
 * não sei do que se trata").** Três acréscimos para ficar autoexplicativo
 * só de bater o olho, sem precisar ler texto corrido:
 * 1. legenda fixa acima do gráfico (o que cada cor/marca significa);
 * 2. régua de meses abaixo de todas as barras;
 * 3. rótulos "Começa aqui"/"Termina aqui" nas pontas.
 *
 * Em plano de mais de dois anos, a régua marca anos ("Ano 1", "Ano 2"…)
 * em vez de três números de mês.
 *
 * **Regra de geometria (Lei nº 3).** As posições/larguras aqui são
 * GEOMETRIA DE DESENHO — razão entre dois inteiros já formatados pelo
 * servidor (mês ÷ prazo total), nunca um valor financeiro recalculado.
 * Nenhum número produzido por essa conta é exibido como dado: o texto ao
 * lado de cada barra é sempre `nome`/`mes_de_quitacao`, já prontos do
 * servidor. Equivalente estático em
 * `report/templates/plano/visuais.html::linha_do_tempo` (mesma geometria,
 * mesma paleta).
 */
import type { PosicaoDaOrdem } from '../../tipos'

interface LinhaDoTempoDividasProps {
  ordem: PosicaoDaOrdem[]
  prazoTotalMeses: number
  /** Legenda/rótulos de `textos-canonicos.yaml::linha_do_tempo`. */
  textos: Record<string, string>
}

export default function LinhaDoTempoDividas({
  ordem,
  prazoTotalMeses,
  textos,
}: LinhaDoTempoDividasProps) {
  if (ordem.length === 0 || prazoTotalMeses <= 0) return null

  const alturaLinha = 36
  const alturaRegua = 36
  const altura = alturaLinha * ordem.length + alturaRegua + 16
  const yRegua = alturaLinha * ordem.length + 14
  const descricao = `Linha do tempo das suas ${ordem.length} dívidas, da primeira à última quitação em ${prazoTotalMeses} meses.`

  // Régua: mês 1, o(s) mês(es) intermediário(s) redondo(s) e o último mês —
  // nunca todos os meses de um plano longo, que lotaria o eixo. `Set` evita
  // "1" duplicado quando o prazo é muito curto.
  const marcosDaRegua = Array.from(
    new Set([1, Math.round(prazoTotalMeses / 2), prazoTotalMeses].filter((m) => m >= 1)),
  ).sort((a, b) => a - b)

  // Plano de mais de dois anos: a régua marca o fim de cada ano e escreve
  // "Ano N" no meio da faixa, só quando a faixa tem ao menos 6 meses de
  // largura. Geometria de desenho, igual a `visuais.html::linha_do_tempo`.
  const porAno = prazoTotalMeses > 24
  const faixasDosAnos = Array.from({ length: Math.ceil(prazoTotalMeses / 12) }, (_, indice) => ({
    numero: indice + 1,
    inicio: indice * 12,
    fim: Math.min((indice + 1) * 12, prazoTotalMeses),
  }))

  return (
    <figure className="visual" role="img" aria-label={descricao}>
      <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 rounded-full bg-accent" />
          {textos.legenda_atacando || 'Sendo atacada agora'}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-4 rounded-full border border-accent bg-accent-soft" />
          {textos.legenda_aguardando || 'Aguardando a vez'}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 rounded-full bg-accent" />
          {textos.legenda_quitada || 'Mês da quitação'}
        </span>
      </div>
      <svg
        viewBox={`0 0 600 ${altura}`}
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        focusable="false"
      >
        {ordem.map((posicao, indice) => {
          const fimMes = posicao.mes_de_quitacao ?? prazoTotalMeses
          const xFim = 560 * (fimMes / prazoTotalMeses)
          const y = alturaLinha * indice + 10
          const ehAlvoAtual = indice === 0
          return (
            <g key={posicao.DIVIDA_ID}>
              <text x={0} y={y + 14} fontSize={16} fill="#1B2A2F">
                {indice + 1}. {posicao.nome}
              </text>
              <rect x={0} y={y + 18} width={560} height={8} rx={4} fill="#D9E0DC" />
              <rect
                x={0}
                y={y + 18}
                width={xFim}
                height={8}
                rx={4}
                fill={ehAlvoAtual ? '#0F6E56' : '#E3F1EB'}
                stroke={ehAlvoAtual ? undefined : '#0F6E56'}
                strokeWidth={ehAlvoAtual ? undefined : 1}
              />
              {posicao.mes_de_quitacao != null && (
                <circle cx={xFim} cy={y + 22} r={6} fill="#0F6E56" />
              )}
            </g>
          )
        })}
        {/* Régua de meses — referência de tempo ao longo de todas as barras. */}
        <line x1={0} y1={yRegua} x2={560} y2={yRegua} stroke="#D9E0DC" strokeWidth={1} />
        {porAno
          ? faixasDosAnos.map(({ numero, inicio, fim }) => {
              const x = 560 * (fim / prazoTotalMeses)
              return (
                <g key={numero}>
                  <line x1={x} y1={yRegua} x2={x} y2={yRegua + 5} stroke="#5E6E72" strokeWidth={1} />
                  {fim - inicio >= 6 && (
                    <text
                      x={560 * ((inicio + fim) / 2 / prazoTotalMeses)}
                      y={yRegua + 17}
                      fontSize={13}
                      fill="#5E6E72"
                      textAnchor="middle"
                    >
                      {textos.rotulo_ano || 'Ano'} {numero}
                    </text>
                  )}
                </g>
              )
            })
          : marcosDaRegua.map((mes) => {
              const x = 560 * (mes / prazoTotalMeses)
              return (
                <g key={mes}>
                  <line x1={x} y1={yRegua} x2={x} y2={yRegua + 5} stroke="#5E6E72" strokeWidth={1} />
                  <text x={x} y={yRegua + 17} fontSize={13} fill="#5E6E72" textAnchor="middle">
                    {mes}
                  </text>
                </g>
              )
            })}
        {/* Rótulos de início/fim, ancorando a leitura da linha inteira. */}
        <text x={0} y={altura - 2} fontSize={13} fill="#5E6E72" textAnchor="start">
          {textos.comeca_aqui || 'Começa aqui'}
        </text>
        <text x={560} y={altura - 2} fontSize={13} fill="#5E6E72" textAnchor="end">
          {textos.termina_aqui || 'Termina aqui'}
        </text>
      </svg>
    </figure>
  )
}
