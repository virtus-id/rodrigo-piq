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
 */
import { createContext, useContext, useEffect, useId, useState } from 'react'

import { type Rota } from '../navegacao'
import { obterInventario, type PendenciaDeInventario } from '../services/api'
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

  return (
    <div role="alert" className="aviso-atencao flex-col">
      <strong>Inventário incompleto</strong>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {pendencias.map((pendencia, indice) => {
          const idMensagem = `${base}-${indice}`
          return (
            <li key={pendencia.codigo} className="flex flex-col gap-2">
              <span id={idMensagem}>{pendencia.mensagem}</span>
              <div className="flex flex-wrap gap-2">
                {pendencia.escopo && (
                  <Botao
                    variante="secundario"
                    aria-describedby={idMensagem}
                    onClick={() =>
                      contexto.irPara({ tela: 'fichas', escopo: pendencia.escopo ?? undefined })
                    }
                  >
                    Cadastrar as fichas
                  </Botao>
                )}
                <Botao
                  variante="discreto"
                  aria-describedby={idMensagem}
                  onClick={() =>
                    contexto.irPara({ tela: 'respostas', idPergunta: pendencia.ID_PARA_CORRIGIR })
                  }
                >
                  Corrigir a resposta
                </Botao>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
