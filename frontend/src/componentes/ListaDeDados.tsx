import type { CampoDeEntrada } from '../services/api'

/**
 * Dados de entrada com rótulo e valor legíveis, ambos do servidor (`RF-111`,
 * `T-326`) — a tela não traduz código nenhum.
 *
 * Cada dado é uma LINHA (rótulo à esquerda, valor à direita, filete embaixo):
 * se lê varrendo o olho por uma coluna só, em vez de saltar entre rótulo e valor
 * de pares soltos (`T-349`). `larga` abre três colunas em monitor grande — para
 * o cartão que ocupa a largura toda do painel.
 */
export default function ListaDeDados({
  campos,
  larga = false,
}: {
  campos: CampoDeEntrada[]
  larga?: boolean
}) {
  return (
    // `T-329`: uma coluna no celular, duas a partir de `sm`; nada estoura o
    // cartão — o código técnico quebra em qualquer ponto.
    <dl
      className={`m-0 grid grid-cols-1 gap-x-8 sm:grid-cols-2 ${
        larga ? 'min-[1800px]:grid-cols-3' : ''
      }`}
    >
      {campos.map((campo) => (
        <div
          key={campo.codigo}
          className="flex min-w-0 items-baseline justify-between gap-4 border-b border-line py-1.5"
        >
          {/* Só o rótulo: o nome técnico da variável (`campo.codigo`) não
              ajuda o revisor a interpretar (relato do produto, 2026-10-02). */}
          <dt className="min-w-0 text-sm text-muted">{campo.nome}</dt>
          <dd className="m-0 min-w-0 text-right font-medium tabular-nums [overflow-wrap:anywhere]">
            {campo.valor}
          </dd>
        </div>
      ))}
    </dl>
  )
}
