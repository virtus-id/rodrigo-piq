/**
 * A fotografia do mês na `B3.C00` — `RF-79`, `RF-80`, `EC-28` (T-228).
 *
 * Três números, todos do SERVIDOR (`app/montagem/entrada.py`): nenhuma soma
 * aqui — nem das decomposições, que são só consulta. `null` é "não
 * informado", nunca `R$ 0,00` (`EC-28`); a marca "parcial (há itens sem
 * valor)" é a decisão do produto `R9-2`. A sobra é a do orçamento **antes
 * das dívidas** — o rótulo diz isso (`AC-117`).
 *
 * As decomposições ficam num `<details>`, fora da vista inicial e
 * alcançáveis por teclado (o `<summary>` é focável por natureza); cada linha
 * leva ao "corrigir" pela rota de correção de `RF-69`.
 */
import { formatarDecimalDoServidor } from '../mascaras'
import type { LinhaDaFotografia, PainelFotografia as Painel } from '../tipos'

const NAO_INFORMADO = 'não informado'
const PARCIAL = 'parcial (há itens sem valor)'

/** Formatação de exibição de uma string decimal do servidor — sinal incluso. */
function moeda(valor: string | null): string {
  if (valor === null) return NAO_INFORMADO
  const negativo = valor.startsWith('-')
  const texto = formatarDecimalDoServidor(negativo ? valor.slice(1) : valor) || '0,00'
  return `${negativo ? '−' : ''}R$ ${texto}`
}

function Numero({ rotulo, valor, parcial }: { rotulo: string; valor: string | null; parcial: boolean }) {
  return (
    <>
      <dt className="text-muted">{rotulo}</dt>
      <dd className="m-0 font-bold tabular-nums">
        {moeda(valor)}
        {parcial && valor !== null && <span className="nota"> — {PARCIAL}</span>}
      </dd>
    </>
  )
}

function Linhas({
  titulo,
  linhas,
  aoCorrigir,
}: {
  titulo: string
  linhas: LinhaDaFotografia[]
  aoCorrigir?: (idPergunta: string, itemId: string) => void
}) {
  if (linhas.length === 0) return null
  return (
    <>
      <h3 className="eyebrow">{titulo}</h3>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {linhas.map((linha) => (
          <li key={linha.item_id} className="linha flex-wrap">
            <span>{linha.rotulo ?? linha.item_id}</span>
            <span className="tabular-nums">{moeda(linha.valor_mensal)}</span>
            {aoCorrigir && linha.corrigir.ID_PERGUNTA && (
              <button
                type="button"
                className="btn-discreto"
                onClick={() =>
                  aoCorrigir(linha.corrigir.ID_PERGUNTA ?? '', linha.corrigir.item_id)
                }
              >
                Corrigir<span className="sr-only"> {linha.rotulo ?? linha.item_id}</span>
              </button>
            )}
          </li>
        ))}
      </ul>
    </>
  )
}

export default function PainelFotografia({
  painel,
  aoCorrigir,
}: {
  painel: Painel
  /** Sem ela, as linhas são só consulta (nenhum botão que não leva a nada). */
  aoCorrigir?: (idPergunta: string, itemId: string) => void
}) {
  return (
    <section className="cartao" aria-label="Fotografia do seu mês">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <Numero rotulo="Renda total" valor={painel.renda_total} parcial={painel.parcial.renda} />
        <Numero
          rotulo="Despesas totais"
          valor={painel.despesas_totais}
          parcial={painel.parcial.despesas}
        />
        <Numero
          rotulo="Sobra do mês, antes das dívidas"
          valor={painel.sobra_antes_das_dividas}
          parcial={painel.parcial.sobra}
        />
      </dl>
      <details>
        <summary>Ver de onde vêm as despesas</summary>
        <div className="flex flex-col gap-3 pt-3">
          <Linhas titulo="Despesas por item" linhas={painel.despesas_por_item} aoCorrigir={aoCorrigir} />
          <Linhas
            titulo="Despesas não mensais, convertidas para o mês"
            linhas={painel.nao_mensais_por_item}
            aoCorrigir={aoCorrigir}
          />
        </div>
      </details>
    </section>
  )
}
