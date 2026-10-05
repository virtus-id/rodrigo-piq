import type { CampoDeEntrada } from '../services/api'

/**
 * Dados de entrada com rótulo e valor legíveis, ambos do servidor (`RF-111`,
 * `T-326`) — a tela não traduz código nenhum.
 */
export default function ListaDeDados({ campos }: { campos: CampoDeEntrada[] }) {
  return (
    // `T-329`: uma coluna no celular, duas a partir de `sm`; nada estoura o
    // cartão — o código técnico quebra em qualquer ponto.
    <dl className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      {campos.map((campo) => (
        <div key={campo.codigo} className="contents">
          {/* Só o rótulo: o nome técnico da variável (`campo.codigo`) não
              ajuda o revisor a interpretar (relato do produto, 2026-10-02). */}
          <dt className="min-w-0 text-muted">{campo.nome}</dt>
          <dd className="m-0 mb-2 min-w-0 tabular-nums [overflow-wrap:anywhere] sm:mb-0">
            {campo.valor}
          </dd>
        </div>
      ))}
    </dl>
  )
}
