/**
 * "Seu ponto de partida" — revisão de design (2026-10-03): os números do
 * mês do aluno (renda, gastos, parcelas que já paga e o valor extra do
 * plano), para que o plano pareça feito para ele. Tudo lido do cálculo e
 * já formatado pelo servidor; nenhum número é somado ou subtraído aqui. A
 * relação entre eles é explicada em texto, nunca com sinais de conta.
 */
import type { PontoDePartida as PontoDePartidaTipo } from '../tipos'

interface PontoDePartidaProps {
  ponto: PontoDePartidaTipo
  textos: Record<string, string>
  titulo: string
  /** Em estabilização ou ordem vazia não há valor extra a mostrar. */
  mostrarValorExtra: boolean
}

export default function PontoDePartida({
  ponto,
  textos,
  titulo,
  mostrarValorExtra,
}: PontoDePartidaProps) {
  const linhas: [string, string | number][] = [
    [textos.renda || 'Sua renda no mês', ponto.renda],
    [textos.gastos || 'Seus gastos do dia a dia', ponto.gastos],
    [textos.gastos_ocasionais || 'Gastos que não acontecem todo mês', ponto.gastos_ocasionais],
    [textos.parcelas || 'Parcelas de dívidas que você já paga', ponto.parcelas],
    [textos.quantidade_dividas || 'Dívidas incluídas neste plano', ponto.quantidade_de_dividas],
  ]

  return (
    <section className="cartao" aria-labelledby="titulo-ponto-de-partida">
      <h2 id="titulo-ponto-de-partida">{titulo || 'Seu ponto de partida'}</h2>
      {textos.introducao && <p className="text-muted">{textos.introducao}</p>}
      <dl className="m-0 flex flex-col">
        {linhas.map(([rotulo, valor]) => (
          <div
            key={rotulo}
            className="flex items-baseline justify-between gap-4 border-b border-line py-2"
          >
            <dt>{rotulo}</dt>
            <dd className="m-0 whitespace-nowrap font-bold tabular-nums">{valor}</dd>
          </div>
        ))}
        {mostrarValorExtra && (
          <div className="mt-2 flex items-baseline justify-between gap-4 rounded-piq bg-accent-soft px-3 py-2">
            <dt className="font-bold">{textos.valor_extra || 'Valor extra para quitar as dívidas'}</dt>
            <dd className="m-0 whitespace-nowrap text-lg font-bold tabular-nums text-accent">{ponto.valor_extra}</dd>
          </div>
        )}
      </dl>
      {mostrarValorExtra && textos.nota_seguranca && (
        <p className="text-muted text-sm">{textos.nota_seguranca}</p>
      )}
    </section>
  )
}
