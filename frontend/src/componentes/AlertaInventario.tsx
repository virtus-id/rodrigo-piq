/**
 * O alerta permanente de inventário incompleto — `RF-86`, `RF-87`, `AC-133`,
 * `AC-154` (T-251).
 *
 * Vive na casca (`Tela.tsx`): toda tela do aluno o mostra enquanto a
 * diferença persistir. Consulta `/inventario` a cada navegação — o
 * `navegacao` do contexto muda a cada rota — e renderiza exatamente o que o
 * servidor devolveu: **nenhuma regra é avaliada aqui**. Sem pendência, nada
 * é renderizado; falha de rede também não renderiza (a guarda real é a do
 * servidor, no cálculo).
 *
 * Cada pendência traz as ações diretas: cadastrar fichas do escopo (quando o
 * servidor o indica) e corrigir a resposta declarada pela rota de correção
 * (`RF-69`). O bloco é `role="alert"` — anunciado a leitor de tela — e cada
 * botão aponta, por `aria-describedby`, para a mensagem que o originou (NFR
 * de acessibilidade da Rodada 9).
 *
 * `T-324`: dívidas faltando dizem QUAIS — os tipos marcados que ainda não
 * têm ficha e as fichas já cadastradas, como o servidor relacionou —, e
 * "Cadastrar a próxima dívida" abre a ficha vazia ou cria uma (`T-311`).
 */
import { createContext, useContext, useEffect, useId, useState } from 'react'

import { type Rota } from '../navegacao'
import {
  criarFicha,
  obterInventario,
  obterProximaPergunta,
  type PendenciaDeInventario,
} from '../services/api'
import Botao from './Botao'

export interface AlertaDoCaso {
  casoId: string
  irPara: (rota: Rota) => void
  /** A rota corrente — a consulta refaz a cada navegação. */
  navegacao: Rota
}

export const ContextoDoAlerta = createContext<AlertaDoCaso | null>(null)

export default function AlertaInventario() {
  const contexto = useContext(ContextoDoAlerta)
  const [pendencias, setPendencias] = useState<readonly PendenciaDeInventario[]>([])
  const [erro, setErro] = useState<string | null>(null)
  const base = useId()
  const casoId = contexto?.casoId ?? ''
  const navegacao = contexto?.navegacao

  useEffect(() => {
    if (!casoId) return
    let ativo = true
    obterInventario(casoId)
      .then((dados) => {
        if (ativo) setPendencias(dados.pendencias)
      })
      .catch(() => {
        if (ativo) setPendencias([])
      })
    return () => {
      ativo = false
    }
  }, [casoId, navegacao])

  if (!contexto || pendencias.length === 0) return null
  const { irPara } = contexto

  async function cadastrarProxima(fichaVazia: string | null) {
    setErro(null)
    try {
      const itemId = fichaVazia ?? (await criarFicha(casoId, 'DIVIDA_ID')).ficha.item_id
      const dados = await obterProximaPergunta(casoId, itemId)
      if (!dados.pergunta) throw new Error('ficha sem pergunta')
      irPara({ tela: 'pergunta', idPergunta: dados.pergunta.ID, itemId })
    } catch {
      setErro('Não foi possível abrir a ficha.')
    }
  }

  return (
    <div role="alert" className="aviso-atencao flex-col">
      <strong>Inventário incompleto</strong>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {pendencias.map((pendencia, indice) => {
          const idMensagem = `${base}-${indice}`
          const dividas = pendencia.dividas
          return (
            <li key={pendencia.codigo} className="flex flex-col gap-2">
              <span id={idMensagem}>{pendencia.mensagem}</span>
              {dividas && dividas.tipos_sem_ficha.length > 0 && (
                <span>
                  Tipos que você marcou e ainda não têm ficha:{' '}
                  {dividas.tipos_sem_ficha.join(', ')}.
                </span>
              )}
              {dividas && dividas.fichas.length > 0 && (
                <div>
                  Fichas já cadastradas:
                  <ul className="m-0 pl-5">
                    {dividas.fichas.map((ficha) => (
                      <li key={ficha.item_id}>
                        {[ficha.credor, ficha.tipo].filter(Boolean).join(' — ') ||
                          'Ficha sem credor e tipo informados'}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {dividas ? (
                  <Botao
                    variante="secundario"
                    aria-describedby={idMensagem}
                    onClick={() => void cadastrarProxima(dividas.ficha_vazia)}
                  >
                    Cadastrar a próxima dívida
                  </Botao>
                ) : pendencia.escopo && (
                  <Botao
                    variante="secundario"
                    aria-describedby={idMensagem}
                    onClick={() =>
                      irPara({ tela: 'fichas', escopo: pendencia.escopo ?? undefined })
                    }
                  >
                    Cadastrar as fichas
                  </Botao>
                )}
                <Botao
                  variante="discreto"
                  aria-describedby={idMensagem}
                  onClick={() =>
                    irPara({ tela: 'respostas', idPergunta: pendencia.ID_PARA_CORRIGIR })
                  }
                >
                  Corrigir a resposta
                </Botao>
              </div>
            </li>
          )
        })}
      </ul>
      {erro && <p className="aviso-erro">{erro}</p>}
    </div>
  )
}
