/**
 * "Seu plano, mês a mês" — redesenho (2026-10-03, feedback do usuário:
 * "tudo por escrito… precisa ser um design que, quando ele bate o olho,
 * ele já sabe do que se trata"). Grade de cartões, um por MÊS INDIVIDUAL:
 * número do mês, ícone do que acontece e o dado principal em poucas
 * palavras, nunca uma frase corrida. Abaixo, a legenda dos ícones. Cada
 * cartão já chega do servidor como `MesDaGrade` (`tipo` decide o ícone e a
 * cor); nenhum cálculo aqui.
 *
 * Plano com mais de 12 meses (2026-10-03, pergunta do usuário: "e quando a
 * pessoa tiver anos para pagar?"): a mesma grade vira calendário por ano,
 * uma linha por ano com os 12 meses lado a lado. Os anos chegam prontos do
 * servidor (`grade_anos`); aqui só se desenha.
 */
import type { ReactNode } from 'react'

import type { AnoDaGrade, MesDaGrade } from '../tipos'
import Icone from './Icone'
import type { NomeDoIcone } from './Icone'

interface JornadaDoPlanoProps {
  grade: MesDaGrade[]
  /** Calendário por ano; vazio em plano de até 12 meses. */
  anos: AnoDaGrade[]
  textos: Record<string, string>
  titulo: string
}

const ICONE_POR_TIPO: Record<MesDaGrade['tipo'], NomeDoIcone> = {
  ATAQUE: 'dinheiro',
  QUITACAO: 'concluido',
  APORTE: 'reserva',
  CHEGADA: 'bandeira',
}

const CLASSE_POR_TIPO: Record<MesDaGrade['tipo'], string> = {
  ATAQUE: 'bg-surface border-line',
  QUITACAO: 'bg-accent-soft border-accent',
  APORTE: 'bg-warn-soft border-warn text-warn',
  CHEGADA: 'bg-ink text-white border-ink',
}

const LEGENDA_POR_TIPO: Record<MesDaGrade['tipo'], string> = {
  ATAQUE: 'legenda_ataque',
  QUITACAO: 'legenda_quitacao',
  APORTE: 'legenda_aporte',
  CHEGADA: 'legenda_chegada',
}

function preencher(modelo: string, valores: Record<string, string | number>): string {
  return modelo.replace(/\{(\w+)\}/g, (_, chave: string) => String(valores[chave] ?? ''))
}

function rotuloCurto(mesDaGrade: MesDaGrade, textos: Record<string, string>): string {
  switch (mesDaGrade.tipo) {
    case 'QUITACAO':
      return textos.quitada || 'dívida quitada'
    case 'APORTE':
      return textos.aporte || 'dinheiro extra'
    case 'CHEGADA':
      return textos.chegada || 'fim das dívidas'
    default:
      return mesDaGrade.valor_extra || textos.ataque || 'a mais'
  }
}

interface ItemDaLegenda {
  chave: string
  classe: string
  conteudo: ReactNode
}

function Legenda({ itens, textos }: { itens: ItemDaLegenda[]; textos: Record<string, string> }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-1 p-0 text-sm text-muted">
      {itens.map(({ chave, classe, conteudo }) => {
        const texto = textos[chave]
        if (!texto) return null
        return (
          <li key={chave} className="flex items-center gap-2">
            <span className={`grid h-6 w-6 flex-none place-items-center rounded ${classe}`}>
              {conteudo}
            </span>
            {texto}
          </li>
        )
      })}
    </ul>
  )
}

function itemDoTipo(tipo: MesDaGrade['tipo']): ItemDaLegenda {
  return {
    chave: LEGENDA_POR_TIPO[tipo],
    classe: `border ${CLASSE_POR_TIPO[tipo]}`,
    conteudo: <Icone nome={ICONE_POR_TIPO[tipo]} />,
  }
}

function GradeDeCartoes({ grade, textos }: { grade: MesDaGrade[]; textos: Record<string, string> }) {
  return (
    <>
      <ol
        className="grid list-none grid-cols-3 gap-2 p-0 sm:grid-cols-4"
        aria-label="Um cartão por mês, do início ao fim do plano"
      >
        {grade.map((mesDaGrade, indice) => (
          <li
            key={`${mesDaGrade.mes}-${mesDaGrade.tipo}-${indice}`}
            className={`flex flex-col items-center gap-1 rounded-piq border p-2 text-center ${CLASSE_POR_TIPO[mesDaGrade.tipo]}`}
          >
            <span className="text-[0.65rem] uppercase tracking-wide opacity-70">
              {textos.rotulo_mes || 'Mês'}
            </span>
            <span className="font-serif text-xl font-bold">{mesDaGrade.mes}</span>
            <Icone nome={ICONE_POR_TIPO[mesDaGrade.tipo]} />
            <span className="text-xs leading-tight">{rotuloCurto(mesDaGrade, textos)}</span>
            {mesDaGrade.eh_primeira_vitoria && (
              <span className="text-[0.65rem] font-bold text-warn">
                {textos.primeira_vitoria || '1ª quitação'}
              </span>
            )}
          </li>
        ))}
      </ol>
      {/* Legenda dos símbolos — o cartão mostra só o ícone e uma palavra;
          aqui fica o que cada um quer dizer. */}
      <Legenda
        itens={(['ATAQUE', 'QUITACAO', 'APORTE', 'CHEGADA'] as const).map(itemDoTipo)}
        textos={textos}
      />
    </>
  )
}

/** Descrição de um mês do calendário para leitor de tela: o quadro só
 * mostra o número e, nos meses com acontecimento, um ícone. */
function descricaoDoMes(mesDaGrade: MesDaGrade, textos: Record<string, string>): string {
  const mes = `${textos.rotulo_mes || 'Mês'} ${mesDaGrade.mes}`
  if (mesDaGrade.eh_primeira_vitoria) return `${mes}: ${textos.primeira_vitoria || '1ª quitação'}`
  return `${mes}: ${rotuloCurto(mesDaGrade, textos)}`
}

/** "Valor extra de cada mês: R$ 300,00, depois R$ 500,00", com cada valor
 * inteiro na mesma linha ("R$" nunca separado do número). */
function ValoresDoAno({
  modelo,
  valores,
  separador,
}: {
  modelo: string
  valores: string[]
  separador: string
}) {
  const [antes, depois = ''] = modelo.split('{valores}')
  return (
    <>
      {antes}
      {valores.map((valor, indice) => (
        <span key={valor}>
          {indice > 0 && separador}
          <span className="whitespace-nowrap tabular-nums">{valor}</span>
        </span>
      ))}
      {depois}
    </>
  )
}

function CalendarioPorAno({ anos, textos }: { anos: AnoDaGrade[]; textos: Record<string, string> }) {
  const separador = textos.separador_de_valores || ', depois '
  return (
    <>
      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        {anos.map((ano) => (
          <li key={ano.numero} className="rounded-piq border border-line p-3">
            <h3 className="m-0 flex flex-wrap items-baseline gap-x-3 text-base">
              {textos.rotulo_ano || 'Ano'} {ano.numero}
              <span className="font-sans text-sm font-normal text-muted">
                {preencher(
                  ano.mes_inicio === ano.mes_fim
                    ? textos.mes_unico_do_ano || 'Mês {inicio}'
                    : textos.meses_do_ano || 'Mês {inicio} a {fim}',
                  { inicio: ano.mes_inicio, fim: ano.mes_fim },
                )}
              </span>
            </h3>
            <ol className="mt-2 grid list-none grid-cols-6 gap-1 p-0 sm:grid-cols-12">
              {ano.meses.map((mesDaGrade) => (
                <li
                  key={mesDaGrade.mes}
                  aria-label={descricaoDoMes(mesDaGrade, textos)}
                  className={`flex h-12 flex-col items-center gap-0.5 rounded pt-1 text-center ${CLASSE_POR_TIPO[mesDaGrade.tipo]} ${mesDaGrade.eh_primeira_vitoria ? 'border-2' : 'border'}`}
                >
                  <span
                    className={`text-xs tabular-nums ${mesDaGrade.tipo === 'ATAQUE' ? 'text-muted' : 'font-bold'}`}
                  >
                    {mesDaGrade.mes}
                  </span>
                  {mesDaGrade.tipo !== 'ATAQUE' && (
                    <span className={mesDaGrade.eh_primeira_vitoria ? 'text-warn' : ''}>
                      <Icone
                        nome={
                          mesDaGrade.eh_primeira_vitoria
                            ? 'trofeu'
                            : ICONE_POR_TIPO[mesDaGrade.tipo]
                        }
                      />
                    </span>
                  )}
                </li>
              ))}
            </ol>
            <div className="mt-2 flex flex-col gap-0.5 text-sm text-muted">
              {ano.valores_extras.length > 0 && (
                <p className="m-0">
                  <ValoresDoAno
                    modelo={textos.valor_do_ano || '{valores}'}
                    valores={ano.valores_extras}
                    separador={separador}
                  />
                </p>
              )}
              {ano.quitacoes.map((quitacao) => (
                <p
                  key={`${quitacao.mes}-${quitacao.nome}`}
                  className="m-0 flex items-start gap-1 font-bold text-accent"
                >
                  <span className="mt-0.5 flex-none">
                    <Icone nome="concluido" />
                  </span>
                  {preencher(textos.quitacao_do_ano || 'Mês {mes}: {divida}', {
                    mes: quitacao.mes,
                    divida: quitacao.nome,
                  })}
                </p>
              ))}
            </div>
          </li>
        ))}
      </ol>
      <Legenda
        itens={[
          {
            chave: 'legenda_comum',
            classe: `border text-xs ${CLASSE_POR_TIPO.ATAQUE}`,
            conteudo: '1',
          },
          itemDoTipo('QUITACAO'),
          {
            chave: 'legenda_primeira_vitoria',
            classe: `border-2 text-warn ${CLASSE_POR_TIPO.QUITACAO}`,
            conteudo: <Icone nome="trofeu" />,
          },
          itemDoTipo('APORTE'),
          itemDoTipo('CHEGADA'),
        ]}
        textos={textos}
      />
    </>
  )
}

export default function JornadaDoPlano({ grade, anos, textos, titulo }: JornadaDoPlanoProps) {
  if (grade.length === 0) return null
  const porAno = anos.length > 0
  const introducao = porAno ? textos.introducao_anos : textos.introducao

  return (
    <section className="cartao" aria-labelledby="titulo-jornada">
      <h2 id="titulo-jornada">{titulo || textos.titulo || 'Seu plano, mês a mês'}</h2>
      {introducao && <p className="text-muted m-0">{introducao}</p>}
      {porAno ? (
        <CalendarioPorAno anos={anos} textos={textos} />
      ) : (
        <GradeDeCartoes grade={grade} textos={textos} />
      )}
    </section>
  )
}
