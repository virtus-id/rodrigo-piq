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
  type CasoParaRevisao,
  decidirRevisao,
  obterCasoParaRevisao,
  obterOpcoesDeDecisao,
} from '../services/api'

interface TelaEquipeCasoProps {
  casoId: string
  voltar: () => void
}

export default function TelaEquipeCaso({ casoId, voltar }: TelaEquipeCasoProps) {
  const [dados, setDados] = useState<CasoParaRevisao | null>(null)
  const [classificacoes, setClassificacoes] = useState<string[]>([])
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

  return (
    <Tela
      titulo={`Conferir o plano de ${dados.CASO_ID}`}
      voltar={voltar}
      onde={`${dados.CASO_ID} · plano v${fila.versao}`}
      largura="equipe"
      acoes={
        <div className="flex flex-wrap gap-3">
          <Botao
            className="flex-1"
            disabled={enviando}
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
                <div className="flex-1">
                  {posicao.DIVIDA_ID}
                  <small className="block text-muted">
                    {posicao.JUSTIFICATIVA_POSICAO}
                  </small>
                </div>
              </div>
            ))}
          </div>
          <p className="carimbo">
            Método: {fila.METODO_RECOMENDADO_PIQ} · {fila.STATUS_METODO} · versão do
            cálculo {plano.ENGINE_VERSION} · parâmetros {plano.PARAMETROS_VERSION}
          </p>
        </div>

        <div className="cartao">
          <span className="eyebrow">Dados que produziram o plano</span>
          {/* Nenhum campo é omitido: o revisor compara o plano contra o
              estado COMPLETO, e campo fora da tela é campo que ninguém
              confere. Os valores já vêm formatados pelo servidor — inclusive
              `DESCONHECIDO`, que nunca pode aparecer como `0` (`AC-08`). */}
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            {entradas.campos.map((campo) => (
              <div key={campo.nome} className="contents">
                <dt className="text-muted">{campo.nome}</dt>
                <dd className="tabular-nums">{campo.valor}</dd>
              </div>
            ))}
            {entradas.dividas.flatMap((divida) =>
              divida.campos.map((campo) => (
                <div key={`${divida.DIVIDA_ID}.${campo.nome}`} className="contents">
                  <dt className="text-muted">
                    {divida.DIVIDA_ID} · {campo.nome}
                  </dt>
                  <dd className="tabular-nums">{campo.valor}</dd>
                </div>
              )),
            )}
          </dl>
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
