/**
 * O plano do aluno — telas `plano`, `plano-estab` e `plano-vazio` do
 * protótipo (`RF-50`, `AC-14`, `AC-16`, `AC-70`).
 *
 * **Plano amigável (2026-10-03).** O título e o corpo deixaram de ser a
 * transcrição literal de `Q-03` e passaram a ser a redação de
 * "consultoria individual" aprovada pelo usuário nesta conversa — mas a
 * disciplina continua a mesma: **todo texto vem do servidor, verbatim.**
 * `titulo` e `corpo` são transportados sem uma vírgula de diferença — o
 * termo que qualifica o plano agora é "inteligente", nunca
 * "definitiva"/"final"/"fixa". Este componente **nunca** reescreve nem
 * resume esses campos.
 *
 * **Nenhum número é calculado aqui** (Lei nº 3): prazo, custo e valores de
 * apoio são leitura de campo do snapshot, já formatados pelo servidor. A
 * única conta client-side é GEOMETRIA DE DESENHO dos gráficos SVG
 * (`frontend/src/componentes/visuais/*`), nunca um valor exibido.
 */
import { useCallback, useEffect, useState } from 'react'

import Esqueleto from '../componentes/Esqueleto'
import Icone from '../componentes/Icone'
import PlanoDoAluno from '../componentes/PlanoDoAluno'
import Tela from '../componentes/Tela'
import { obterPlano } from '../services/api'
import type { Plano } from '../tipos'

/** O título enquanto o plano não chegou — a casca precisa de um sempre. */
const TITULO_PROVISORIO = 'Meu plano'

interface TelaPlanoProps {
  casoId: string
  voltar?: () => void
}

export default function TelaPlano({ casoId, voltar }: TelaPlanoProps) {
  const [plano, setPlano] = useState<Plano | null>(null)
  const [estado, setEstado] = useState<string>('')
  const [mensagem, setMensagem] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const dados = await obterPlano(casoId)
      setPlano(dados.plano)
      setEstado(dados.estado)
      setMensagem(dados.mensagem ?? null)
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
      <Tela titulo={TITULO_PROVISORIO} voltar={voltar}>
        <Esqueleto forma="resumo" anuncio="Carregando seu plano" />
      </Tela>
    )
  }

  if (erro) {
    return (
      <Tela titulo={TITULO_PROVISORIO} voltar={voltar}>
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      </Tela>
    )
  }

  // Sem plano liberado: o equivalente de `aguardando.html` — o estado do
  // caso, nunca uma tela de plano vazia.
  if (!plano) {
    return (
      <Tela titulo="Seu plano ainda não está liberado" voltar={voltar}>
        <p className="lead">{mensagem}</p>
        <p className="eyebrow">Estado do caso: {estado}</p>
      </Tela>
    )
  }

  return (
    <Tela
      titulo={plano.titulo}
      voltar={voltar}
      onde={plano.ordem.length > 0 ? `${plano.ordem.length} dívidas na ordem` : undefined}
      acoes={
        /* `OQ-09` (respondida): o aluno recebe o plano em TELA **e** em PDF.
           O PDF é a única saída que continua sendo HTML no servidor — é um
           documento para guardar ou imprimir, gerado pelo WeasyPrint sobre
           `report/templates/plano/`, e carrega a MESMA redação canônica
           desta tela (as duas leem `textos-canonicos.yaml`, `AC-14`).

           É um `<a href>`, não um `fetch`: o download precisa da navegação
           nativa do navegador, com o cookie de sessão que a rota exige. */
        <a
          className="btn-secundario no-underline"
          href={`/caso/${casoId}/plano/pdf`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {/* O ícone é `aria-hidden` e vem do componente (`AC-110`): o nome
              acessível do link continua sendo exatamente "Baixar em PDF",
              que é o que `plano.spec.ts:144` busca por `getByRole`. */}
          <Icone nome="baixar" />
          Baixar em PDF
        </a>
      }
    >
      <PlanoDoAluno plano={plano} />
    </Tela>
  )
}
