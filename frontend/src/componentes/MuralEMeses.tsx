/**
 * "Seu plano detalhado" (mural) e "Mês a mês, em detalhe" — `T-377`.
 * O mural tem um bloco por mês de cada plano; cada bloco é um link (âncora) para
 * o cartão do mês logo abaixo. O rótulo é a referência "Mês 01", nunca uma data.
 * Todo número e texto chega pronto do servidor (Lei nº 3).
 */
import type { MesDetalhado, PlanoDetalhado } from '../tipos'

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
      className={`block rounded-piq p-2 text-xs no-underline ${
        quitacao ? `${c.forte} text-white` : `${c.suave} text-ink`
      }`}
    >
      <strong className="block text-sm">{mes.rotulo}</strong>
      <span className="block">
        {textos.rotulo_deve || 'Deve'} {mes.saldo}
      </span>
      <span className="block">
        {mes.ultimo
          ? textos.texto_fim || 'Fim das dívidas'
          : `${textos.rotulo_extra_mes || 'Extra'} ${mes.valor_extra}`}
      </span>
      {mes.quitadas.map((q) => (
        <span key={q.numero} className="block font-bold">
          ✓ {q.numero}
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
          <div className="grid gap-2 md:grid-cols-2">
            {plano.meses.map((mes) => (
              <CartaoDoMes key={mes.ancora} mes={mes} cor={plano.cor} textos={textos} />
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}
