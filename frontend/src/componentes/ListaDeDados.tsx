import type { CampoDeEntrada } from '../services/api'

/**
 * Dados de entrada com rótulo e valor legíveis, ambos do servidor (`RF-111`,
 * `T-326`) — a tela não traduz código nenhum.
 *
 * **Uma coluna, empilhada.** Cada dado é uma linha: o rótulo à esquerda, numa
 * coluna de largura proporcional, e o valor logo ao lado, alinhado à esquerda —
 * rótulo e valor ficam perto, em qualquer largura de tela, e se lê descendo o
 * olho. Dividir a lista em várias colunas "para aproveitar o monitor" a
 * deixava quebrada, uma coisa ao lado da outra (relato do produto,
 * 2026-10-05, `T-350`).
 */
export default function ListaDeDados({ campos }: { campos: CampoDeEntrada[] }) {
  return (
    // O código técnico quebra em qualquer ponto: nada estoura o cartão.
    <dl className="m-0 flex flex-col">
      {campos.map((campo) => (
        <div
          key={campo.codigo}
          className="grid min-w-0 grid-cols-1 gap-x-4 border-b border-line py-1.5 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]"
        >
          {/* Só o rótulo: o nome técnico da variável (`campo.codigo`) não
              ajuda o revisor a interpretar (relato do produto, 2026-10-02). */}
          <dt className="min-w-0 text-sm text-muted">{campo.nome}</dt>
          <dd className="m-0 min-w-0 font-medium tabular-nums [overflow-wrap:anywhere]">
            {campo.valor}
          </dd>
        </div>
      ))}
    </dl>
  )
}
