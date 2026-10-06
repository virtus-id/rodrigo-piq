/**
 * Conferência de um caso — plano e dados lado a lado — `RF-26`, `AC-29`,
 * `AC-27` (T-150).
 *
 * **Esta era a maior lacuna funcional do produto.** `GET /api/revisao/caso/
 * {id}` e `POST /revisao/caso/{id}/decisao` existem e são testadas desde
 * T-70/T-72, mas nenhuma tela as consumia: o revisor não tinha como liberar
 * um plano pela interface. E `RF-23` diz que **todo** plano passa pela
 * conferência antes de chegar ao aluno — ou seja, sem esta tela nenhum aluno
 * recebia plano nenhum, exceto por intervenção manual no banco.
 *
 * **Plano e `estado_inputs` vêm na MESMA resposta**, e isso é o requisito, não
 * conveniência: se viessem de duas requisições poderiam ser de snapshots
 * diferentes, e a comparação não provaria nada (`AC-29`).
 *
 * **As seis classificações vêm do servidor** (`GET .../decisao`), nunca
 * escritas aqui. `OQ-12` fixou os seis nomes sem definição de categoria; um
 * sétimo rótulo só pode nascer em `CLASSIFICACAO_ERRO`, num lugar só.
 */
import { type ReactNode, useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Icone from '../componentes/Icone'
import ListaDeDados from '../componentes/ListaDeDados'
import PlanoDoAluno from '../componentes/PlanoDoAluno'
import Tela from '../componentes/Tela'
import {
  type CasoParaRevisao,
  type OpcoesDeDecisao,
  decidirRevisao,
  obterCasoParaRevisao,
  obterOpcoesDeDecisao,
} from '../services/api'

/** `T-304`: os cinco itens de `DE-08`, na ordem da decisão do especialista. */
const ITENS_DE_HOMOLOGACAO: [string, string][] = [
  ['ordem_final_de_ataque', 'Ordem final de ataque'],
  ['mes_de_quitacao_por_divida', 'Mês de quitação de cada dívida'],
  ['valor_mensal_destinado', 'Valor mensal destinado'],
  ['custo_total_de_juros', 'Custo total de juros'],
  ['uso_da_reserva', 'Uso da reserva'],
]

/** Valor do registro como texto — sem conta nenhuma (Lei nº 3). Ordem e
 *  meses chegam com o nome da dívida (`T-328`). */
function textoDoItem(valor: unknown): ReactNode {
  // `T-329`: ordem e meses em lista, uma dívida por linha — em parágrafo
  // corrido, onze nomes longos viravam um bloco ilegível.
  const linhas = Array.isArray(valor)
    ? valor.map(String)
    : valor && typeof valor === 'object'
      ? Object.entries(valor).map(([divida, mes]) => `${divida}: mês ${String(mes)}`)
      : null
  if (!linhas) return String(valor)
  return (
    <ul className="m-0 list-none p-0">
      {linhas.map((linha) => (
        <li key={linha}>{linha}</li>
      ))}
    </ul>
  )
}

interface TelaEquipeCasoProps {
  casoId: string
  voltar: () => void
}

export default function TelaEquipeCaso({ casoId, voltar }: TelaEquipeCasoProps) {
  const [dados, setDados] = useState<CasoParaRevisao | null>(null)
  const [classificacoes, setClassificacoes] = useState<string[]>([])
  const [conferencia, setConferencia] = useState<OpcoesDeDecisao | null>(null)
  const [classificacao, setClassificacao] = useState('')
  const [observacao, setObservacao] = useState('')
  // `T-333` (`RF-113`): o que o ALUNO lê — separado da observação interna.
  const [mensagemAluno, setMensagemAluno] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [enviando, setEnviando] = useState(false)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const [caso, opcoes] = await Promise.all([
        obterCasoParaRevisao(casoId),
        obterOpcoesDeDecisao(casoId),
      ])
      setDados(caso)
      setClassificacoes(opcoes.classificacoes_erro)
      setConferencia(opcoes)
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar o caso.')
    } finally {
      setCarregando(false)
    }
  }, [casoId])

  useEffect(() => {
    void carregar()
  }, [carregar])

  async function decidir(decisao: 'LIBERAR' | 'REPROVAR') {
    // `RF-113`: sem a mensagem o aluno recebe o plano de volta sem saber o
    // que corrigir. Conveniência — quem recusa é o servidor (`422`).
    if (decisao === 'REPROVAR' && !mensagemAluno.trim()) {
      setErro('Escreva a mensagem para o aluno.')
      return
    }
    setEnviando(true)
    setErro(null)
    try {
      await decidirRevisao(casoId, {
        decisao,
        // A classificação só acompanha a reprovação: classificar um erro num
        // plano que se está liberando não faz sentido, e o servidor a ignora
        // no ramo `LIBERAR`.
        classificacaoErro: decisao === 'REPROVAR' ? classificacao || undefined : undefined,
        observacao: observacao || undefined,
        mensagemAluno: decisao === 'REPROVAR' ? mensagemAluno.trim() : undefined,
      })
      setAviso(
        decisao === 'LIBERAR'
          ? 'Plano liberado. A decisão ficou registrada com o seu nome e a data.'
          : 'Correção pedida. A decisão ficou registrada com o seu nome e a data.',
      )
      voltar()
    } catch (falha) {
      // `409` quando o caso já saiu de `AGUARDANDO_REVISAO` — outra pessoa
      // decidiu antes. A mensagem é a do servidor: ele sabe o que aconteceu.
      setErro(falha instanceof Error ? falha.message : 'Não foi possível registrar.')
    } finally {
      setEnviando(false)
    }
  }

  if (carregando) {
    return (
      <Tela titulo="Conferir plano" voltar={voltar} largura="total">
        <Esqueleto forma="resumo" anuncio="Carregando o caso" />
      </Tela>
    )
  }

  if (!dados) {
    return (
      <Tela titulo="Conferir plano" voltar={voltar} largura="total">
        <p role="alert" className="aviso-erro">
          {erro ?? 'Nada para conferir.'}
        </p>
      </Tela>
    )
  }

  const { plano, estado_inputs: entradas, fila } = dados
  const pendencias = conferencia?.pendencias_homologacao ?? []
  const fontes = conferencia?.fontes ?? []
  const segurosNaoInformados = conferencia?.seguros_nao_informados ?? []
  const divergencias = conferencia?.divergencias ?? []
  const rateios = conferencia?.rateios ?? []
  const homologacao = conferencia?.homologacao

  return (
    <Tela
      // `T-327` (`RF-111` e): o aluno pelo e-mail; o `CASO_ID` vai para o `onde`.
      titulo={`Conferir o plano de ${fila.email_do_aluno || dados.CASO_ID}`}
      voltar={voltar}
      onde={`${dados.CASO_ID} · plano v${fila.versao}`}
      largura="total"
      acoes={
        <div className="flex flex-wrap gap-3">
          {/* `RF-93`: com pendência de homologação o botão fica desabilitado.
              É conveniência — quem recusa é o servidor (`409`). */}
          <Botao
            className="flex-1"
            disabled={enviando || pendencias.length > 0}
            onClick={() => void decidir('LIBERAR')}
          >
            Liberar para o aluno
          </Botao>
          <Botao
            variante="secundario"
            className="flex-1"
            disabled={enviando}
            onClick={() => void decidir('REPROVAR')}
          >
            Pedir correção
          </Botao>
        </div>
      }
    >
      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}
      {aviso && (
        <p role="status" className="aviso-ok">
          {aviso}
        </p>
      )}

      {/* `RF-121` (T-347): a conferência mostra o plano COMO O ALUNO O RECEBE — o
          mesmo componente da tela dele — e, ao lado, o painel do revisor. No
          monitor largo são duas colunas (plano do aluno na largura dele ·
          painel); abaixo disso empilha, plano do aluno primeiro. */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,760px)_minmax(0,1fr)] xl:items-start">
        <section aria-label="Como o aluno vai ver" className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="eyebrow">Como o aluno vai ver</span>
            {/* `RF-124`: a prévia do PDF que o aluno receberá. Link de verdade:
                o download usa a navegação nativa e o cookie de sessão. */}
            <a
              className="btn-discreto !w-auto no-underline"
              href={`/revisao/caso/${casoId}/plano/pdf`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Icone nome="baixar" />
              Abrir prévia do PDF
            </a>
          </div>
          <div className="flex flex-col gap-4 rounded-piq border border-dashed border-line bg-surface p-4">
            {/* Redação canônica do servidor — `AC-14`. Nunca reescrita aqui. */}
            <h2 className="m-0">{plano.titulo}</h2>
            <PlanoDoAluno plano={plano} revisor={{ entradas }} />
          </div>
        </section>

        <aside aria-label="Painel do revisor" className="flex min-w-0 flex-col gap-4">
      {/* `T-330`: o método é do caso, não da dívida — um destaque só, com o
          critério em uma frase (do servidor). Substitui o "Detalhe técnico"
          que repetia o mesmo texto do motor em cada posição. */}
      <section className="cartao" aria-labelledby="titulo-metodo">
        <span className="eyebrow">Método selecionado para este aluno</span>
        <h2 id="titulo-metodo">
          {fila.metodo} <small className="text-muted">· {fila.status_metodo}</small>
        </h2>
        {fila.criterio_metodo && <p>{fila.criterio_metodo}</p>}
      </section>

      {/* `T-266` — redação aprovada pelo produto (`T-289`, 2026-09-30). */}
      {pendencias.length > 0 && (
        <div role="alert" className="aviso-erro flex-col">
          <p className="font-bold">
            Não pode ser homologado ainda: confirme ou corrija estes dados antes de liberar.
          </p>
          <ul>
            {pendencias.map((p) => (
              <li key={`${p.item_id ?? 'caso'}-${p.ID_PERGUNTA}`}>
                {p.nome ? `${p.nome} · ` : ''}
                {p.enunciado} —{' '}
                {p.motivo === 'AUSENTE' ? 'não informado' : 'pendente de confirmação'}
              </li>
            ))}
          </ul>
        </div>
      )}

      {(fontes.length > 0 ||
        segurosNaoInformados.length > 0 ||
        divergencias.length > 0 ||
        rateios.length > 0) && (
        <div className="cartao">
          <span className="eyebrow">Fonte de comprovação e avisos</span>
          <ul>
            {fontes.map((f) => (
              <li key={`${f.item_id}-${f.origem}`}>
                {f.nome} · {f.dado}: {f.rotulo}
              </li>
            ))}
            {segurosNaoInformados.map((divida) => (
              <li key={`seguro-${divida.item_id}`}>
                {divida.nome} · seguro: {conferencia?.rotulo_nao_informado ?? 'não informado'}
              </li>
            ))}
            {divergencias.map((d, i) => (
              <li key={`divergencia-${i}`}>
                {d.tipo === 'DESCONTO'
                  ? `${d.nome} · desconto: valor em R$ e percentual não conferem`
                  : `Renda dos vínculos (${d.soma_liquidas}) difere da renda total (${d.renda_bloco_3})`}
              </li>
            ))}
            {rateios.map((r) => (
              <li key={`rateio-${r.item_id}-${r.variavel}`}>
                {r.nome} · rateio mensal (só análise): {r.valor_mensal}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* `T-304` (`RF-96`, `DE-08`): o registro de homologação, lido do
          snapshot em decisão. Item não derivável vem "não disponível" com o
          motivo — nunca estimado. */}
      {homologacao && (
        <section className="cartao" aria-labelledby="titulo-homologacao">
          <h2 id="titulo-homologacao" className="eyebrow">
            Registro de homologação
          </h2>
          <dl className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-[auto_minmax(0,1fr)]">
            {ITENS_DE_HOMOLOGACAO.map(([chave, rotulo]) => {
              const item = homologacao.itens[chave]
              return (
                <div key={chave} className="contents">
                  <dt className="text-muted">{rotulo}</dt>
                  <dd className="m-0 mb-2 min-w-0 tabular-nums [overflow-wrap:anywhere] sm:mb-0">
                    {item ? textoDoItem(item.valor) : 'não disponível'}
                    {item?.motivo && (
                      <small className="block text-muted">{item.motivo}</small>
                    )}
                  </dd>
                </div>
              )
            })}
            <dt className="text-muted">Pode ser homologado</dt>
            <dd className="m-0">{homologacao.homologavel ? 'sim' : 'não'}</dd>
          </dl>
        </section>
      )}

      {/* Os dois sinais seguem SEPARADOS — `AC-28`. A política do piloto
          (100% dos planos) e o campo `REVISAO_HUMANA_OBRIGATORIA` do motor
          (caso `S-04`) são motivos diferentes para o caso estar aqui, e
          combiná-los num selo só esconderia qual dos dois se aplica. */}
      <div className="flex flex-wrap gap-2">
        {fila.entra_por_politica && <span className="chip chip-mudo">Política 100%</span>}
        {fila.e_metodologico && (
          <span className="chip chip-atencao">S-04 · revisão obrigatória</span>
        )}
      </div>

        {/* `RF-123` (T-348): o que mudou nos dados de entrada desde a versão
            anterior — só em plano refeito. O servidor já manda tudo formatado. */}
        {dados.mudancas && (
          <section className="cartao" aria-labelledby="titulo-mudancas">
            <h2 id="titulo-mudancas" className="eyebrow">
              O que mudou desde a versão anterior
            </h2>
            {dados.mudancas.length === 0 ? (
              <p className="m-0">Nada mudou nos dados de entrada desde a versão anterior.</p>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-2 p-0">
                {dados.mudancas.map((mudanca, i) => (
                  <li key={`${mudanca.secao}-${mudanca.nome}-${i}`}>
                    <span className="text-muted block text-xs">{mudanca.secao}</span>
                    <strong>{mudanca.nome}</strong>:{' '}
                    {mudanca.situacao === 'novo' && <span className="chip chip-atencao">novo</span>}
                    {mudanca.situacao === 'removido' && <span className="chip chip-mudo">removido</span>}{' '}
                    {mudanca.de !== null && <span className="text-muted tabular-nums">{mudanca.de}</span>}
                    {mudanca.de !== null && mudanca.para !== null && ' → '}
                    {mudanca.para !== null && <span className="tabular-nums font-bold">{mudanca.para}</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        <details className="cartao min-w-0" open>
          <summary className="eyebrow cursor-pointer">Dados que produziram o plano</summary>
          {/* Nenhum campo é omitido: o revisor compara o plano contra o
              estado COMPLETO, e campo fora da tela é campo que ninguém
              confere. Os valores já vêm formatados pelo servidor — inclusive
              `DESCONHECIDO`, que nunca pode aparecer como `0` (`AC-08`). */}
          <ListaDeDados campos={entradas.campos} />
          {entradas.dividas.map((divida) => (
            <section key={divida.DIVIDA_ID} aria-label={divida.nome}>
              <h3>
                {divida.nome}
              </h3>
              <ListaDeDados campos={divida.campos} />
            </section>
          ))}
          <h3>Como lida com os gastos</h3>
          <ListaDeDados campos={entradas.perfil_comportamental} />
          <h3>Sinais de comportamento</h3>
          <ListaDeDados campos={entradas.sinais_comportamentais} />
        </details>
        </aside>
      </div>

      <div className="cartao">
        <span className="eyebrow">Decisão</span>
        <div className="field">
          <label htmlFor="classificacao">Se encontrou um erro, classifique</label>
          <select
            id="classificacao"
            className="campo-texto"
            value={classificacao}
            onChange={(e) => setClassificacao(e.target.value)}
          >
            <option value="">—</option>
            {classificacoes.map((nome) => (
              <option key={nome} value={nome}>
                {nome}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="observacao">Observação</label>
          <input
            id="observacao"
            type="text"
            className="campo-texto"
            placeholder="Opcional"
            value={observacao}
            onChange={(e) => setObservacao(e.target.value)}
          />
        </div>
        {/* `T-333` (`RF-113`): o texto que o aluno lê no Início. A
            observação acima é interna e nunca chega a ele. */}
        <div className="field">
          <label htmlFor="mensagem-aluno">Mensagem para o aluno</label>
          <textarea
            id="mensagem-aluno"
            className="campo-texto"
            rows={3}
            aria-describedby="mensagem-aluno-nota"
            value={mensagemAluno}
            onChange={(e) => setMensagemAluno(e.target.value)}
          />
          <p id="mensagem-aluno-nota" className="nota">
            Obrigatória para pedir correção. O aluno lê este texto; a observação, não.
          </p>
        </div>
        {/* `AC-27`: o autor vem da sessão do revisor no servidor, nunca de um
            campo daqui. Dizer isso na tela é honesto — a decisão é dele e não
            pode ser desfeita. */}
        <p className="nota">
          A decisão fica registrada com o seu nome e a data, e não pode ser alterada.
        </p>
      </div>
    </Tela>
  )
}
