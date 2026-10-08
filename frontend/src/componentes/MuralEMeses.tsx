/**
 * "Seu plano detalhado" (mural) e "Mês a mês, em detalhe" — `T-377`.
 * O mural tem um bloco por mês de cada plano; cada bloco é um link (âncora) para
 * o cartão do mês logo abaixo. O rótulo é a referência "Mês 01", nunca uma data.
 * Todo número e texto chega pronto do servidor (Lei nº 3).
 */
import { useEffect, useState } from 'react'

import type { MesDetalhado, PlanoDetalhado } from '../tipos'
import Icone from './Icone'

const COR = {
  azul: {
    texto: 'text-azul',
    suave: 'bg-azul-soft',
    forte: 'bg-azul',
    borda: 'border-l-azul',
  },
  verde: {
    texto: 'text-accent',
    suave: 'bg-accent-soft',
    forte: 'bg-accent',
    borda: 'border-l-accent',
  },
} as const

function BlocoDoMural({
  mes,
  cor,
  textos,
}: {
  mes: MesDetalhado
  cor: PlanoDetalhado['cor']
  textos: Record<string, string>
}) {
  const c = COR[cor]
  const quitacao = mes.quitadas.length > 0
  return (
    <a
      href={`#${mes.ancora}`}
      data-mes={mes.ancora}
      className={`relative block rounded-piq p-2 text-xs no-underline ${
        quitacao ? `${c.forte} text-white` : `${c.suave} text-ink`
      }`}
    >
      {quitacao && (
        <span data-trofeu className="absolute right-1.5 top-1.5">
          <Icone nome="trofeu" className="h-4 w-4" />
        </span>
      )}
      <strong className="block text-sm">{mes.rotulo}</strong>
      <span className="mt-1 block text-[11px] opacity-90">
        {textos.rotulo_deve || 'Ainda deve'}
      </span>
      <span className="block font-bold">{mes.saldo}</span>
      {mes.ultimo ? (
        <span className="mt-1 block text-[11px] opacity-90">
          {textos.texto_fim || 'Fim das dívidas'}
        </span>
      ) : (
        <>
          <span className="mt-1 block text-[11px] opacity-90">
            {textos.rotulo_extra_mes || 'Pagar a mais'}
          </span>
          <span className="block font-bold">{mes.valor_extra}</span>
        </>
      )}
      {(mes.quitas ?? []).map((texto) => (
        <span key={texto} className="mt-1 block text-[11px] font-bold">
          {texto}
        </span>
      ))}
    </a>
  )
}

export function MuralDoPlano({
  detalhes,
  textos,
}: {
  detalhes: PlanoDetalhado[]
  textos: Record<string, string>
}) {
  return (
    <section className="cartao" aria-labelledby="titulo-mural" id="mural-do-plano">
      <h2 id="titulo-mural">{textos.mural_titulo || 'Seu plano detalhado'}</h2>
      {textos.mural_intro && <p className="text-muted m-0">{textos.mural_intro}</p>}
      {detalhes.map((plano) => (
        <div key={plano.cor} data-mural={plano.cor} className="flex flex-col gap-2">
          <h3 className={`m-0 ${COR[plano.cor].texto}`}>{plano.titulo}</h3>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-6">
            {plano.meses.map((mes) => (
              <BlocoDoMural key={mes.ancora} mes={mes} cor={plano.cor} textos={textos} />
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}

function CartaoDoMes({
  mes,
  cor,
  textos,
}: {
  mes: MesDetalhado
  cor: PlanoDetalhado['cor']
  textos: Record<string, string>
}) {
  const c = COR[cor]
  return (
    <article
      id={mes.ancora}
      className={`scroll-mt-4 rounded-piq border border-l-8 border-line bg-surface p-3 text-sm ${c.borda}`}
    >
      <h4 className={`m-0 text-base ${c.texto}`}>{mes.rotulo}</h4>
      {mes.divida_da_vez && (
        <p className="m-0 mt-1">
          <strong>{textos.rotulo_da_vez || 'Dívida da vez'}:</strong> {mes.divida_da_vez.numero}.{' '}
          {mes.divida_da_vez.nome}
          <br />
          {(textos.texto_coloque || '').replace('{valor}', mes.valor_extra)}
        </p>
      )}
      <p className="m-0 mt-1 font-bold">
        {textos.rotulo_saldo_fim || 'Ainda deve, ao fim do mês'}: {mes.saldo}
      </p>
      {mes.quitadas.map((q) => (
        <p key={q.numero} className="m-0 mt-1">
          ✓ {mes.primeira_quitacao ? textos.rotulo_primeira : textos.rotulo_quitada}: {q.numero}.{' '}
          {q.nome}
        </p>
      ))}
      {mes.ultimo ? (
        <p className="m-0 mt-1 font-bold">{textos.texto_fim}</p>
      ) : (
        <p className="text-muted m-0 mt-1">
          {textos.instrucao_parcelas} {textos.instrucao_comprovante}
        </p>
      )}
      <p className="m-0 mt-1 text-xs">
        <a href="#mural-do-plano" className="text-muted">
          {textos.voltar || 'Voltar ao mural'}
        </a>
      </p>
    </article>
  )
}

/** Texto com `{marcador}` trocado pelos valores (os textos vêm do servidor). */
function preencher(modelo: string | undefined, valores: Record<string, string>): string {
  return Object.entries(valores).reduce((t, [k, v]) => t.replace(`{${k}}`, v), modelo ?? '')
}

/**
 * `T-384` — a página do mês, no modelo do produto (para acompanhar e imprimir):
 * resumo, tabela por dívida, "Como fecha o mês" e o que executar. Recolhida por
 * padrão (um plano tem dezenas de meses); abre sozinha quando o link do mural
 * aponta para ela.
 */
function PaginaDoMes({
  mes,
  cor,
  titulo,
  textos,
}: {
  mes: MesDetalhado
  cor: PlanoDetalhado['cor']
  titulo: string
  textos: Record<string, string>
}) {
  const p = mes.pagina
  const c = COR[cor]
  const [aberto, setAberto] = useState(false)
  useEffect(() => {
    const abrir = () => {
      if (window.location.hash === `#${mes.ancora}`) setAberto(true)
    }
    abrir()
    window.addEventListener('hashchange', abrir)
    return () => window.removeEventListener('hashchange', abrir)
  }, [mes.ancora])
  if (!p) return null
  return (
    <details
      id={mes.ancora}
      open={aberto}
      onToggle={(e) => setAberto(e.currentTarget.open)}
      className={`scroll-mt-4 rounded-piq border border-l-8 border-line bg-surface p-3 ${c.borda}`}
    >
      <summary className="cursor-pointer list-none">
        <span className={`text-base font-bold ${c.texto}`}>
          {mes.rotulo} · {titulo}
        </span>
        <span className="text-muted ml-2 text-sm">
          {textos.rotulo_deve}: {p.divida_apos}
        </span>
        {p.quitacao && (
          <span data-trofeu className="ml-2 inline-block align-middle text-[#8A5A00]">
            <Icone nome="trofeu" className="h-5 w-5" />
            <span className="ml-1 text-sm font-bold">{textos.pagina_quitacao}</span>
          </span>
        )}
      </summary>
      <p className="text-muted mb-2 mt-2 text-sm">
        {preencher(textos.pagina_subtitulo, { de_total: p.de_total })}
      </p>
      <dl className="m-0 grid gap-2 rounded-piq bg-bg p-3 sm:grid-cols-3">
        <div>
          <dt className="text-muted text-sm">{textos.pagina_total_pagar}</dt>
          <dd className="m-0 text-lg font-bold">{p.total_pagar}</dd>
        </div>
        <div>
          <dt className="text-muted text-sm">{textos.pagina_extra}</dt>
          <dd className="m-0 text-lg font-bold">{p.extra_aplicado}</dd>
        </div>
        <div>
          <dt className="text-muted text-sm">{textos.pagina_divida_apos}</dt>
          <dd className="m-0 text-lg font-bold">{p.divida_apos}</dd>
        </div>
      </dl>
      <h4 className="mb-1 mt-3">{textos.pagina_tabela_titulo}</h4>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-muted text-right text-xs">
              <th scope="col" className="py-1 pr-2 text-left">
                {textos.coluna_divida}
              </th>
              <th scope="col">{textos.coluna_saldo_antes}</th>
              <th scope="col">{textos.coluna_juros}</th>
              <th scope="col">{textos.coluna_habitual}</th>
              <th scope="col">{textos.coluna_extra}</th>
              <th scope="col">{textos.coluna_total}</th>
              <th scope="col">{textos.coluna_saldo_depois}</th>
            </tr>
          </thead>
          <tbody>
            {p.linhas.map((l) => (
              <tr
                key={l.nome}
                data-quita={l.quita ? 'sim' : undefined}
                className={`border-t border-line text-right tabular-nums ${
                  l.quita ? `${c.suave} font-bold ${c.texto}` : ''
                }`}
              >
                <th scope="row" className="py-1.5 pr-2 text-left">
                  {l.nome}
                  <small className="block font-normal opacity-80">
                    {l.quita ? textos.linha_quita : textos.linha_apoio}
                  </small>
                </th>
                <td>{l.saldo_antes}</td>
                <td>{l.juros}</td>
                <td>{l.habitual}</td>
                <td>{l.extra}</td>
                <td>{l.total}</td>
                <td>{l.saldo_depois}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h4 className="mb-1 mt-3">{textos.fecha_titulo}</h4>
      <p className="text-muted m-0 text-sm">{textos.fecha_regra}</p>
      <p className="m-0 font-bold">
        {preencher(textos.fecha_conta, {
          inicio: p.inicio,
          juros: p.juros,
          pagamentos: p.pagamentos,
          restante: p.restante,
        })}
      </p>
      <p className="m-0">
        {preencher(textos.fecha_total, { habitual: p.habitual_total, extra: p.extra_total })}
      </p>
      {p.quitacao && !mes.ultimo && <p className="text-muted m-0 text-sm">{textos.fecha_sobras}</p>}
      <h4 className="mb-1 mt-3">{textos.executar_titulo}</h4>
      <ul className="m-0 list-none p-0 text-sm">
        {['executar_1', 'executar_2', 'executar_3'].map((k) => (
          <li key={k} className="mb-1 flex gap-2">
            <span
              aria-hidden="true"
              className="mt-0.5 inline-block h-4 w-4 flex-none rounded border-2 border-ink"
            />
            {textos[k]}
          </li>
        ))}
      </ul>
      <p className="text-muted mb-0 mt-2 text-xs">{textos.pagina_nota}</p>
      <p className="m-0 mt-1 text-xs">
        <a href="#mural-do-plano" className="text-muted">
          {textos.voltar || 'Voltar ao mural'}
        </a>
      </p>
    </details>
  )
}

export function MesesDetalhados({
  detalhes,
  textos,
}: {
  detalhes: PlanoDetalhado[]
  textos: Record<string, string>
}) {
  return (
    <section className="cartao" aria-labelledby="titulo-meses">
      <h2 id="titulo-meses">{textos.meses_titulo || 'Mês a mês, em detalhe'}</h2>
      {textos.meses_intro && <p className="text-muted m-0">{textos.meses_intro}</p>}
      {detalhes.map((plano) => (
        <div key={plano.cor} className="flex flex-col gap-2">
          <h3 className={`m-0 ${COR[plano.cor].texto}`}>{plano.titulo}</h3>
          <div className={`grid gap-2 ${plano.meses[0]?.pagina ? '' : 'md:grid-cols-2'}`}>
            {plano.meses.map((mes) =>
              mes.pagina ? (
                <PaginaDoMes
                  key={mes.ancora}
                  mes={mes}
                  cor={plano.cor}
                  titulo={plano.titulo}
                  textos={textos}
                />
              ) : (
                <CartaoDoMes key={mes.ancora} mes={mes} cor={plano.cor} textos={textos} />
              ),
            )}
          </div>
        </div>
      ))}
    </section>
  )
}
