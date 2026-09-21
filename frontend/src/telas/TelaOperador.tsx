/**
 * Painel do operador — tela `equipe-painel` do protótipo (`RF-35`, `RF-59`,
 * `AC-87`).
 *
 * **Nenhum valor financeiro aparece aqui, e isso é critério de aceite**
 * (`T-102`), não escolha de layout: só etapa, pendência e tempo desde a
 * última atividade. O operador precisa saber quem travou onde — não quanto
 * a pessoa deve.
 *
 * **900px** (`AC-87`), como a fila: é tabela de casos, não coluna de leitura.
 *
 * `EC-14`: abandono é observável. Um caso parado há meses aparece com o
 * tempo decorrido, em vez de sumir silenciosamente da lista.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import { ErroHttp, obterPainelDoOperador, type LinhaDoPainel } from '../services/api'

function mensagemDoErro(falha: unknown): string {
  if (falha instanceof ErroHttp) {
    if (falha.status === 403) return 'Este painel é da equipe. Sua conta não tem esse acesso.'
    if (falha.status === 401) return 'Sua sessão expirou. Entre novamente.'
    return falha.detalhe
  }
  return 'Não foi possível carregar o painel.'
}

interface TelaOperadorProps {
  voltar?: () => void
}

export default function TelaOperador({ voltar }: TelaOperadorProps) {
  const [linhas, setLinhas] = useState<LinhaDoPainel[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const dados = await obterPainelDoOperador()
      setLinhas(dados.linhas)
    } catch (falha) {
      setErro(mensagemDoErro(falha))
    } finally {
      setCarregando(false)
    }
  }, [])

  useEffect(() => {
    void carregar()
  }, [carregar])

  return (
    <Tela
      titulo="Quem está onde"
      voltar={voltar}
      largura="equipe"
      onde={linhas.length > 0 ? `${linhas.length} caso${linhas.length === 1 ? '' : 's'}` : undefined}
      acoes={
        <Botao variante="secundario" onClick={() => void carregar()} disabled={carregando}>
          {carregando ? 'Atualizando…' : 'Atualizar o painel'}
        </Botao>
      }
    >
      <p className="lead">
        Etapa, o que aguarda conferência e tempo desde a última atividade.
      </p>

      {/* Só na primeira carga — ver a nota em `TelaRevisao` (T-164): esta
          tela também tem "Atualizar o painel", e o esqueleto sobre a lista
          já carregada seria ruído, não informação. */}
      {carregando && linhas.length === 0 && (
        <Esqueleto forma="lista" anuncio="Carregando o painel" itens={4} />
      )}

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}

      {!carregando && !erro && linhas.length === 0 && (
        <p role="status" className="nota">
          Nenhum caso no piloto ainda.
        </p>
      )}

      <ul className="lista list-none p-0">
        {linhas.map((linha) => (
          <li key={linha.CASO_ID} className="cartao">
            <div className="linha flex-wrap">
              <span className="font-bold">{linha.CASO_ID}</span>
              {linha.aguardando_revisao && (
                <span className="chip bg-warn-soft text-warn">Aguarda conferência</span>
              )}
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
              <dt className="text-muted">Etapa</dt>
              <dd className="m-0">{linha.estado}</dd>
              <dt className="text-muted">Parado há</dt>
              <dd className="m-0 tabular-nums">{linha.tempo_desde_ultima_atividade}</dd>
            </dl>
          </li>
        ))}
      </ul>

      <p className="carimbo">Nenhum valor financeiro aparece neste painel.</p>
    </Tela>
  )
}
