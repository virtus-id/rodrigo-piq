/**
 * Bloco 11 — o que fazer agora (`RF-27`, `RF-33`, `AC-45`, `AC-46`,
 * `AC-50`).
 *
 * **Cada ação é uma tarefa, não um portão.** A linguagem é de coisa a
 * fazer — "pedir ao banco", "renegociar" —, nunca de estado de sistema.
 * O aluno não precisa resolver tudo hoje: faz a próxima e conta como foi.
 *
 * `AC-50`: **ação de economia não tem dívida associada**, e aparece como
 * qualquer outra. A chave é o `ACAO_ID`, nunca o `DIVIDA_ID` — por isso
 * nada nesta tela exige que exista dívida.
 *
 * **Esta tela só LISTA** (`T-156`). Reportar como foi é `TelaAcao`, uma tela
 * por ação: antes os campos abriam aqui mesmo, num acordeão, e a ação
 * principal ficava no meio do conteúdo — numa lista de cinco ações o aluno
 * perdia de vista qual delas estava respondendo.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import { obterAcoes, type Acao } from '../services/api'

interface TelaAcoesProps {
  casoId: string
  voltar?: () => void
  /**
   * Abre a tela de UMA ação — `T-156`.
   *
   * A lista deixou de resolver o reporte inline: responder uma ação é um
   * passo próprio, com a pergunta no corpo e a ação no rodapé fixo
   * (`RF-57`). Numa lista de cinco ações, o acordeão fazia o aluno perder
   * de vista qual delas estava respondendo.
   */
  abrirAcao?: (acaoId: string) => void
}

export default function TelaAcoes({ casoId, voltar, abrirAcao }: TelaAcoesProps) {
  const [acoes, setAcoes] = useState<Acao[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const dados = await obterAcoes(casoId)
      setAcoes(dados.acoes)
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar.')
    } finally {
      setCarregando(false)
    }
  }, [casoId])

  useEffect(() => {
    void carregar()
  }, [carregar])

  if (carregando) {
    return (
      <Tela titulo="O que fazer agora" voltar={voltar}>
        <Esqueleto forma="lista" anuncio="Carregando suas ações" itens={3} />
      </Tela>
    )
  }

  return (
    <Tela
      titulo="O que fazer agora"
      voltar={voltar}
      onde={
        acoes.length > 0
          ? acoes.length === 1
            ? '1 ação pendente'
            : `${acoes.length} ações pendentes`
          : undefined
      }
      acoes={
        // Cada ação grava pelo próprio "Salvar", então o rodapé encerra a
        // visita em vez de submeter — a ação principal desta tela acontece
        // fora do aplicativo, no banco ou no credor.
        voltar && (
          <Botao variante="secundario" onClick={voltar}>
            Terminei por agora
          </Botao>
        )
      }
    >
      <p className="lead">
        Você não precisa resolver tudo hoje. Faça a próxima ação e conte para a gente
        como foi.
      </p>

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}

      {acoes.length === 0 && (
        <p role="status" className="nota">
          Nenhuma ação pendente no momento.
        </p>
      )}

      <ul className="lista list-none p-0">
        {acoes.map((acao) => (
          <li key={acao.ACAO_ID} className="cartao">
            <div className="linha flex-wrap">
              <span className="eyebrow">{acao.TIPO_ACAO}</span>
              {acao.prioridade_excepcional && (
                <span className="chip bg-warn-soft text-warn">Prioridade</span>
              )}
            </div>

            <p className="font-serif text-[1.2rem] font-semibold">{acao.descricao}</p>

            {acao.DIVIDA_ID && <small className="text-muted">{acao.DIVIDA_ID}</small>}

            {acao.VALOR_ACAO_FINANCEIRA_IMEDIATA && (
              <p className="tabular-nums text-muted">
                Valor envolvido: {acao.VALOR_ACAO_FINANCEIRA_IMEDIATA}
              </p>
            )}

            {abrirAcao && (
              <Botao variante="secundario" onClick={() => abrirAcao(acao.ACAO_ID)}>
                Contar como foi
              </Botao>
            )}

          </li>
        ))}
      </ul>
    </Tela>
  )
}
