/**
 * Painel de usuários — tela `equipe-painel` do protótipo (`RF-35`, `RF-59`,
 * `AC-87`; `RF-112`, `T-331`: só alunos, em tabela E-mail · Etapa · Status).
 *
 * **Nenhum valor financeiro aparece aqui, e isso é critério de aceite**
 * (`T-102`), não escolha de layout: só etapa, pendência e tempo desde a
 * última atividade. O operador precisa saber quem travou onde — não quanto
 * a pessoa deve.
 *
 * **Largura da equipe** (`AC-87`), como a fila: é tabela, não coluna de leitura.
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

const CELULA = 'py-2 pr-4 max-[640px]:block max-[640px]:py-0.5'
const ROTULO_NO_CELULAR = 'hidden text-muted max-[640px]:mr-2 max-[640px]:inline'

/** "há 2 horas" → "parado há 2 horas"; "agora mesmo" fica como está. */
function tempoParado(tempo: string): string {
  return tempo.startsWith('há ') ? `parado ${tempo}` : tempo
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
      titulo="Painel de usuários"
      voltar={voltar}
      largura="equipe"
      onde={linhas.length > 0 ? `${linhas.length} aluno${linhas.length === 1 ? '' : 's'}` : undefined}
      acoes={
        <Botao variante="secundario" onClick={() => void carregar()} disabled={carregando}>
          {carregando ? 'Atualizando…' : 'Atualizar o painel'}
        </Botao>
      }
    >
      <p className="lead">Alunos: em que etapa estão, o que aguarda e há quanto tempo.</p>

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
          Nenhum aluno no piloto ainda.
        </p>
      )}

      {/* `T-331` (`RF-112`): tabela de largura total, uma linha por aluno.
          Sem coluna Nome — o sistema não guarda nome (`OQ-68`). Até 640px
          vira lista empilhada, com o rótulo da coluna em cada célula, para
          não rolar de lado. */}
      {linhas.length > 0 && (
        <table className="w-full border-collapse text-left text-sm max-[640px]:block">
          <thead className="max-[640px]:sr-only">
            <tr className="border-b border-line text-muted">
              <th scope="col" className="py-2 pr-4 font-normal">E-mail</th>
              <th scope="col" className="py-2 pr-4 font-normal">Etapa</th>
              <th scope="col" className="py-2 font-normal">Status</th>
            </tr>
          </thead>
          <tbody className="max-[640px]:block">
            {linhas.map((linha) => (
              <tr
                key={linha.CASO_ID}
                className="border-b border-line align-top max-[640px]:block max-[640px]:py-2"
              >
                <td className={CELULA}>
                  <span className={ROTULO_NO_CELULAR} aria-hidden="true">E-mail</span>
                  {/* Sem e-mail, o código do caso (`T-327`). */}
                  <span className="break-all">{linha.email_do_aluno || linha.CASO_ID}</span>
                </td>
                <td className={CELULA}>
                  <span className={ROTULO_NO_CELULAR} aria-hidden="true">Etapa</span>
                  {linha.etapa}
                </td>
                <td className={`${CELULA} pr-0`}>
                  <span className={ROTULO_NO_CELULAR} aria-hidden="true">Status</span>
                  {linha.aguardando_revisao && (
                    <span className="block text-warn">Aguarda conferência</span>
                  )}
                  {(linha.bloqueio_inventario?.length ?? 0) > 0 && (
                    <span className="block text-warn">Cálculo bloqueado: inventário incompleto</span>
                  )}
                  <span className="block tabular-nums text-muted">
                    {tempoParado(linha.tempo_desde_ultima_atividade)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="carimbo">Nenhum valor financeiro aparece neste painel.</p>
    </Tela>
  )
}
