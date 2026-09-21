/**
 * Coleta dirigida — Blocos 7 e 8 (`RF-17`, `AC-19`, `AC-34`).
 *
 * **Só as dívidas que o motor sinalizou.** A lista vem de
 * `snapshot.ORDEM_ACOES`, lida no servidor por `dividas_para_bloco_7`/`_8` —
 * esta tela nunca consulta saldo, taxa ou qualquer critério de
 * elegibilidade. Se o motor não apontou a dívida, ela simplesmente não
 * aparece aqui.
 *
 * Os dois blocos compartilham a mesma tela porque compartilham a mesma
 * forma: fichas por `DIVIDA_ID`, campos vindos do registro. O que muda é
 * qual campo de `ORDEM_ACOES` abriu cada uma — decisão do servidor.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import CampoPergunta from '../componentes/CampoPergunta'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import { gravarResposta, obterColetaDirigida, type FichaDirigida } from '../services/api'

interface TelaColetaDirigidaProps {
  casoId: string
  bloco: 7 | 8
  voltar?: () => void
}

const TITULO: Record<7 | 8, string> = {
  7: 'Renegociação',
  8: 'Troca ou portabilidade',
}

const EXPLICACAO: Record<7 | 8, string> = {
  7: 'Perguntamos sobre estas dívidas porque o plano identificou que vale a pena renegociar.',
  8: 'Perguntamos sobre estas dívidas porque o plano identificou que vale a pena trocar.',
}

export default function TelaColetaDirigida({
  casoId,
  bloco,
  voltar,
}: TelaColetaDirigidaProps) {
  const [fichas, setFichas] = useState<FichaDirigida[]>([])
  const [valores, setValores] = useState<Record<string, string | string[]>>({})
  const [naoSei, setNaoSei] = useState<Record<string, boolean>>({})
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const dados = await obterColetaDirigida(casoId, bloco)
      setFichas(dados.fichas)
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar.')
    } finally {
      setCarregando(false)
    }
  }, [casoId, bloco])

  useEffect(() => {
    void carregar()
  }, [carregar])

  function chave(itemId: string, idPergunta: string): string {
    return `${itemId}::${idPergunta}`
  }

  async function aoGravar(itemId: string, idPergunta: string) {
    const k = chave(itemId, idPergunta)
    setErro(null)
    try {
      await gravarResposta(casoId, {
        idPergunta,
        valor: naoSei[k] ? undefined : valores[k],
        itemId,
        naoSei: naoSei[k],
      })
      await carregar()
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível salvar.')
    }
  }

  if (carregando) {
    return (
      <Tela titulo={TITULO[bloco]} voltar={voltar}>
        <Esqueleto forma="pergunta" anuncio="Carregando as perguntas" />
      </Tela>
    )
  }

  return (
    <Tela
      titulo={TITULO[bloco]}
      voltar={voltar}
      onde={
        fichas.length > 0
          ? `${fichas.length} dívida${fichas.length === 1 ? '' : 's'}`
          : undefined
      }
      acoes={
        // Cada campo grava sozinho, então o rodapé não tem o que submeter: a
        // ação que resta é sair da etapa. Sem ela o aluno só volta pelo `.top`,
        // que fica no alto de uma tela longa (`AC-85` existe por isso).
        voltar && (
          <Botao variante="secundario" onClick={voltar}>
            Terminei por agora
          </Botao>
        )
      }
    >
      <p className="lead">{EXPLICACAO[bloco]}</p>

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}

      {fichas.length === 0 && (
        <p role="status" className="nota">
          Nenhuma dívida foi sinalizada para esta etapa.
        </p>
      )}

      {fichas.map((ficha) => (
        <section key={ficha.item_id} className="flex flex-col gap-4">
          <h2 className="border-b border-line pb-2">Dívida {ficha.item_id}</h2>
          {ficha.campos.map((pergunta) => {
            const k = chave(ficha.item_id, pergunta.ID)
            return (
              <div key={pergunta.ID} className="cartao">
                <CampoPergunta
                  pergunta={pergunta}
                  valor={valores[k] ?? ''}
                  naoSei={naoSei[k] ?? false}
                  onValor={(v) => setValores((a) => ({ ...a, [k]: v }))}
                  onNaoSei={(m) => setNaoSei((a) => ({ ...a, [k]: m }))}
                />
                <Botao
                  variante="secundario"
                  onClick={() => void aoGravar(ficha.item_id, pergunta.ID)}
                >
                  Salvar
                </Botao>
              </div>
            )
          })}
        </section>
      ))}
    </Tela>
  )
}
