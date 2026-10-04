/**
 * "O que fazer no Mês 1" — revisão de design (2026-10-03, pedido do
 * usuário: "está da mesma forma que a jornada estava antes, só descrição
 * por escrito"). Três passos numerados, cada um em seu bloco: (1) pagar as
 * parcelas de sempre, com a lista de cada dívida e o valor; (2) o valor
 * extra em destaque, com uma seta para a dívida da vez; (3) guardar o
 * comprovante. Depois, como pedir o pagamento extra ao credor.
 *
 * Todo valor é leitura do que o servidor já formatou (`PassoAtual`) e todo
 * texto vem de `textos-canonicos.yaml::primeiro_passo`; os textos abaixo
 * são só o recurso para um payload antigo.
 */
import type { ReactNode } from 'react'

import type { PassoAtual } from '../tipos'
import Icone from './Icone'

interface PrimeiroPassoProps {
  passo: PassoAtual
  titulo: string
  textos: Record<string, string>
}

function preencher(modelo: string, valores: Record<string, string>): string {
  return modelo.replace(/\{(\w+)\}/g, (_, chave: string) => valores[chave] ?? '')
}

interface BlocoProps {
  numero: number
  titulo: string
  destaque?: boolean
  children: ReactNode
}

function Bloco({ numero, titulo, destaque = false, children }: BlocoProps) {
  return (
    <li
      className={`flex gap-3 rounded-piq border p-4 ${destaque ? 'border-accent bg-accent-soft' : 'border-line bg-surface'}`}
    >
      <span
        aria-hidden="true"
        className="grid h-9 w-9 flex-none place-items-center rounded-full border-2 border-accent font-bold text-accent"
      >
        {numero}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <h3 className="m-0 text-base">
          <span className="sr-only">Passo {numero}: </span>
          {titulo}
        </h3>
        {children}
      </div>
    </li>
  )
}

export default function PrimeiroPasso({ passo, titulo, textos }: PrimeiroPassoProps) {
  return (
    <section className="cartao-proximo" aria-labelledby="titulo-primeiro-passo">
      <h2 id="titulo-primeiro-passo" className="flex items-center gap-2">
        <Icone nome="passo" />
        {titulo || 'O que fazer no Mês 1'}
      </h2>
      {textos.introducao && <p className="text-muted m-0">{textos.introducao}</p>}

      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        <Bloco numero={1} titulo={textos.passo_1_titulo || 'Pague as parcelas de sempre'}>
          {textos.passo_1_texto && <p className="text-muted m-0">{textos.passo_1_texto}</p>}
          {passo.parcelas.length > 0 && (
            <dl className="m-0 flex flex-col">
              {passo.parcelas.map((parcela) => (
                <div
                  key={parcela.nome}
                  className="flex items-baseline justify-between gap-4 border-t border-line py-2"
                >
                  <dt>{parcela.nome}</dt>
                  <dd className="m-0 whitespace-nowrap font-bold tabular-nums">{parcela.valor}</dd>
                </div>
              ))}
            </dl>
          )}
        </Bloco>

        {passo.alvo && (
          <>
            <Bloco
              numero={2}
              titulo={textos.passo_2_titulo || 'Coloque o valor extra em uma dívida só'}
              destaque
            >
              {textos.passo_2_texto && (
                <p className="text-muted m-0">
                  {preencher(textos.passo_2_texto, { valor: passo.valor_extra, alvo: passo.alvo })}
                </p>
              )}
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-2xl font-bold tabular-nums text-accent">
                  {passo.valor_extra}
                </span>
                <span className="text-accent">
                  <Icone nome="avancar" />
                </span>
                <span className="rounded-piq border-2 border-accent bg-surface px-3 py-2 font-bold">
                  {passo.alvo}
                </span>
              </div>
            </Bloco>

            <Bloco numero={3} titulo={textos.passo_3_titulo || 'Guarde o comprovante'}>
              {textos.passo_3_texto && <p className="text-muted m-0">{textos.passo_3_texto}</p>}
            </Bloco>
          </>
        )}
      </ol>

      {passo.alvo && textos.como_pagar_a_mais && (
        <div className="aviso-atencao" role="note">
          <div>
            <strong className="block">
              {textos.como_pagar_titulo || 'Como fazer o pagamento extra'}
            </strong>
            {textos.como_pagar_a_mais}
          </div>
        </div>
      )}
    </section>
  )
}
