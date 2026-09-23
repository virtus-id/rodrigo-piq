/**
 * Fila de conferência — tela `equipe-fila` do protótipo (`RF-50`, `RF-59`,
 * `AC-28`, `AC-87`).
 *
 * **Os dois sinais aparecem SEPARADOS**, e isso não é escolha de layout:
 * `entra_por_politica` (a política do piloto, 100% revisado) e
 * `e_metodologico` (o campo `REVISAO_HUMANA_OBRIGATORIA` que o motor
 * levantou) são fatos diferentes. Um teste estático do servidor falha se
 * forem combinados num booleano só — combiná-los aqui, no visual, teria o
 * mesmo efeito prático de esconder a distinção do revisor.
 *
 * **900px, não 560px** (`AC-87`): a coluna de leitura do aluno existe para
 * uma pergunta por vez; o revisor compara linhas de uma tabela. É a única
 * diferença de layout entre as duas áreas, e vem da prop `largura`.
 *
 * Acesso é por papel: sem sessão dá `401`, conta não-revisora dá `403`.
 * Quem decide isso é o servidor, a cada requisição.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import { ErroHttp, obterFilaDeRevisao } from '../services/api'
import type { ItemDaFila } from '../tipos'

/**
 * `401`/`403` não são falhas: são a guarda de papel funcionando. Mostrar
 * "HTTP 403" a uma pessoa é despejar o código de status na cara dela —
 * o texto abaixo diz o que de fato aconteceu, sem inventar promessa de
 * acesso que o servidor não vai conceder.
 */
function mensagemDoErro(falha: unknown): string {
  if (falha instanceof ErroHttp) {
    if (falha.status === 403) return 'Esta tela é da equipe de conferência. Sua conta não tem esse acesso.'
    if (falha.status === 401) return 'Sua sessão expirou. Entre novamente.'
    return falha.detalhe
  }
  return 'Não foi possível carregar a fila.'
}

interface TelaRevisaoProps {
  voltar?: () => void
  /**
   * Abre a conferência de um caso — `AC-29`.
   *
   * **Sem isto a tela de conferência é inalcançável.** Ela existe desde
   * `T-150`, e as rotas que a alimentam desde `T-70`/`T-72`, mas a fila não
   * tinha como abri-la: o revisor via a lista e não podia agir sobre ela, o
   * que deixava `RF-23` (todo plano passa pela conferência) sem caminho na
   * interface.
   */
  abrirCaso?: (casoId: string) => void
  /**
   * Abre o painel "Quem está onde" — `T-186`.
   *
   * Sem isto o painel só era alcançável digitando `#equipe-painel` na mão:
   * nenhuma tela linkava para lá. A fila é a raiz da navegação do revisor
   * (não recebe `voltar` — ver a nota em `App.tsx`), então é dela que a
   * segunda área da equipe precisa ficar a um clique.
   */
  abrirPainel?: () => void
}

export default function TelaRevisao({ voltar, abrirCaso, abrirPainel }: TelaRevisaoProps) {
  const [itens, setItens] = useState<ItemDaFila[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const dados = await obterFilaDeRevisao()
      setItens(dados.itens)
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
      titulo="Planos aguardando conferência"
      voltar={voltar}
      largura="equipe"
      onde={itens.length > 0 ? `${itens.length} na fila` : undefined}
      acoes={
        <>
          {/* A fila é lida em turnos: recarregar é a ação principal do
              revisor, e sem ela a única forma de ver o que entrou é
              recarregar a página. */}
          <Botao variante="secundario" onClick={() => void carregar()} disabled={carregando}>
            {carregando ? 'Atualizando…' : 'Atualizar a fila'}
          </Botao>
          {abrirPainel && (
            <Botao variante="discreto" onClick={abrirPainel}>
              Ver o painel da equipe
            </Botao>
          )}
        </>
      }
    >
      <p className="lead">
        Todo plano passa por aqui antes de chegar ao aluno. Recálculos também.
      </p>

      {/*
        **Só na PRIMEIRA carga** (T-164). Esta tela tem "Atualizar a fila", e
        `carregando` também fica `true` na reconsulta — com a lista já na
        tela. Sem `itens.length === 0`, o esqueleto apareceria ACIMA dos
        itens reais a cada atualização: quatro cartões falsos empilhados
        sobre os verdadeiros, e um `role="status"` anunciando carregamento
        de algo que já está visível.

        O botão já diz "Atualizando…" enquanto isso — a reconsulta tem o seu
        próprio sinal, e não precisa de um segundo.
      */}
      {carregando && itens.length === 0 && (
        <Esqueleto forma="lista" anuncio="Carregando a fila" itens={4} />
      )}

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}

      {!carregando && !erro && itens.length === 0 && (
        <p role="status" className="nota">
          Nenhum plano aguardando conferência.
        </p>
      )}

      <ul className="lista list-none p-0">
        {itens.map((item) => (
          <li key={item.SNAPSHOT_ID} className="cartao">
            <div className="linha flex-wrap">
              <span className="font-bold">{item.CASO_ID}</span>
              <span className="text-muted">v{item.versao}</span>
            </div>

            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
              <dt className="text-muted">Data de referência</dt>
              <dd className="m-0 tabular-nums">{item.DATA_REFERENCIA}</dd>
              <dt className="text-muted">Método</dt>
              <dd className="m-0">{item.METODO_RECOMENDADO_PIQ}</dd>
              <dt className="text-muted">Status do método</dt>
              <dd className="m-0">{item.STATUS_METODO}</dd>
              {item.MOTIVO_RECALCULO && (
                <>
                  <dt className="text-muted">Motivo</dt>
                  <dd className="m-0">{item.MOTIVO_RECALCULO}</dd>
                </>
              )}
            </dl>

            {/* Dois chips, nunca um — ver a nota do cabeçalho. */}
            <div className="flex flex-wrap gap-2">
              {item.entra_por_politica && (
                <span className="chip bg-line text-muted">Política 100%</span>
              )}
              {item.e_metodologico && (
                <span className="chip bg-warn-soft text-warn">
                  Revisão obrigatória pelo motor
                </span>
              )}
            </div>

            <p className="carimbo">
              cálculo {item.ENGINE_VERSION} · parâmetros {item.PARAMETROS_VERSION}
            </p>

            {abrirCaso && (
              <Botao
                variante="secundario"
                onClick={() => abrirCaso(item.CASO_ID)}
              >
                Abrir para conferir
              </Botao>
            )}
          </li>
        ))}
      </ul>
    </Tela>
  )
}
