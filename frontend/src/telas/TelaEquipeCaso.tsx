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
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import {
  type CampoDeEntrada,
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
function textoDoItem(valor: unknown): string {
  if (Array.isArray(valor)) return valor.join(' → ')
  if (valor && typeof valor === 'object') {
    return Object.entries(valor)
      .map(([divida, mes]) => `${divida}: mês ${String(mes)}`)
      .join(' · ')
  }
  return String(valor)
}

/**
 * Dados de entrada com rótulo e valor legíveis, ambos do servidor (`RF-111`,
 * `T-326`) — a tela não traduz código nenhum. O nome técnico fica ao lado,
 * discreto, para quem precisa casar o dado com a spec.
 */
function ListaDeDados({ campos }: { campos: CampoDeEntrada[] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
      {campos.map((campo) => (
        <div key={campo.codigo} className="contents">
          <dt className="text-muted">
            {campo.nome} <small className="text-muted">{campo.codigo}</small>
          </dt>
          <dd className="tabular-nums">{campo.valor}</dd>
        </div>
      ))}
    </dl>
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
      <Tela titulo="Conferir plano" voltar={voltar} largura="equipe">
        <Esqueleto forma="resumo" anuncio="Carregando o caso" />
      </Tela>
    )
  }

  if (!dados) {
    return (
      <Tela titulo="Conferir plano" voltar={voltar} largura="equipe">
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
      largura="equipe"
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

      {/* `T-266` — redação aprovada pelo produto (`T-289`, 2026-09-30). */}
      {pendencias.length > 0 && (
        <div role="alert" className="aviso-erro">
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
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            {ITENS_DE_HOMOLOGACAO.map(([chave, rotulo]) => {
              const item = homologacao.itens[chave]
              return (
                <div key={chave} className="contents">
                  <dt className="text-muted">{rotulo}</dt>
                  <dd className="m-0 tabular-nums">
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

      <div className="grid gap-4 md:grid-cols-2">
        <div className="cartao">
          <span className="eyebrow">Como o aluno vai ver</span>
          {/* Redação canônica do servidor — `AC-14`. Nunca reescrita aqui. */}
          <h2>{plano.titulo}</h2>
          <p className="nota">{plano.corpo}</p>
          <div className="lista">
            {plano.ordem.map((posicao) => (
              <div className="item" key={posicao.DIVIDA_ID}>
                <span className="num">{posicao.posicao}</span>
                {/* `T-326` (`RF-111`): "tipo — credor" e a explicação que o
                    aluno lê; o código e a justificativa do motor ficam como
                    detalhe — recolhido, para quem precisa refazer a decisão. */}
                <div className="flex-1">
                  {posicao.nome} <small className="text-muted">{posicao.DIVIDA_ID}</small>
                  <p className="text-muted">{posicao.explicacao}</p>
                  {posicao.JUSTIFICATIVA_POSICAO && (
                    <details>
                      <summary>Detalhe técnico</summary>
                      <small className="block text-muted">
                        {posicao.JUSTIFICATIVA_POSICAO}
                      </small>
                    </details>
                  )}
                </div>
              </div>
            ))}
          </div>
          <p className="carimbo">
            Método: {fila.metodo} · {fila.status_metodo} · versão do cálculo{' '}
            {plano.ENGINE_VERSION} · parâmetros {plano.PARAMETROS_VERSION}
          </p>
        </div>

        <div className="cartao">
          <span className="eyebrow">Dados que produziram o plano</span>
          {/* Nenhum campo é omitido: o revisor compara o plano contra o
              estado COMPLETO, e campo fora da tela é campo que ninguém
              confere. Os valores já vêm formatados pelo servidor — inclusive
              `DESCONHECIDO`, que nunca pode aparecer como `0` (`AC-08`). */}
          <ListaDeDados campos={entradas.campos} />
          {entradas.dividas.map((divida) => (
            <section key={divida.DIVIDA_ID} aria-label={divida.nome}>
              <h3>
                {divida.nome} <small className="text-muted">{divida.DIVIDA_ID}</small>
              </h3>
              <ListaDeDados campos={divida.campos} />
            </section>
          ))}
          <h3>Como lida com os gastos</h3>
          <ListaDeDados campos={entradas.perfil_comportamental} />
          <h3>Sinais de comportamento</h3>
          <ListaDeDados campos={entradas.sinais_comportamentais} />
        </div>
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
