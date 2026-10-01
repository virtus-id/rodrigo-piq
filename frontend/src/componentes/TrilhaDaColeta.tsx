/**
 * A trilha da coleta em cinco partes — `RF-100`, `AC-162` (T-310).
 *
 * As partes são as de `/respostas`; o estado de cada uma (concluída, atual,
 * próxima) vem do servidor (`RF-45`, `RF-67`): o cliente não sabe quais
 * perguntas abrem, então não conta nada. A barra mede **partes concluídas**,
 * nunca perguntas — o total de perguntas cresce a cada ficha criada, e uma
 * barra sobre ele pareceria regredir (`T-293`).
 *
 * Reaproveita o desenho da trilha da jornada (`.trilha`, `.degrau`, `.marca`,
 * T-166), sem o componente: aquela trilha lê o payload de `/inicio`.
 * Também **não é navegável** (`AC-115`).
 *
 * Duas geometrias no mesmo DOM, como a casca (`Tela.tsx`): no celular a
 * barra e um resumo de uma linha; a partir de `lg:` a lista inteira na
 * coluna lateral.
 */
import type { ParteDaTrilha } from '../tipos'
import Icone from './Icone'

export default function TrilhaDaColeta({ trilha }: { trilha: readonly ParteDaTrilha[] }) {
  const total = trilha.length
  const concluidas = trilha.filter((parte) => parte.estado === 'concluida').length
  const atual = trilha.find((parte) => parte.estado === 'atual')
  const pct = total > 0 ? Math.round((concluidas / total) * 100) : 0

  return (
    <section aria-label="Partes da coleta" className="flex flex-col gap-3">
      <div
        className="bar h-1"
        role="progressbar"
        aria-label="Progresso da coleta"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={concluidas}
        aria-valuetext={`${concluidas} de ${total} partes concluídas`}
      >
        <i style={{ width: `${pct}%` }} />
      </div>

      {atual && (
        <p className="text-sm text-muted lg:hidden">
          Parte {atual.numero} de {total} · <span className="font-bold text-ink">{atual.rotulo}</span>
        </p>
      )}

      <ol className="trilha hidden list-none p-0 lg:flex">
        {trilha.map((parte) => {
          const concluida = parte.estado === 'concluida'
          const eAtual = parte.estado === 'atual'
          return (
            <li
              key={parte.numero}
              className={`degrau ${concluida ? 'feito' : ''} ${eAtual ? 'agora' : ''}`}
              aria-current={eAtual ? 'step' : undefined}
            >
              <span aria-hidden="true" className="marca">
                {concluida ? <Icone nome="concluido" /> : parte.numero}
              </span>
              <span className={eAtual ? 'font-bold' : concluida ? '' : 'text-muted'}>
                {parte.rotulo}
                {concluida && <span className="sr-only"> (concluída)</span>}
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
