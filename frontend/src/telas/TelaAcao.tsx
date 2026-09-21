/**
 * Uma ação do Bloco 11 — `RF-27`, `RF-33`, `AC-46`, `AC-50` (T-156).
 *
 * É `#acao-status` + `#acao-info` do protótipo validado (linhas ~586–614),
 * agora numa tela só: o aluno abre a ação, diz em que pé ela está
 * (`B11.01`, os seis valores de `ACAO_STATUS`) e, tendo concluído, registra o
 * resultado pela pergunta do **tipo** daquela ação.
 *
 * **Por que uma tela e não o acordeão da lista.** `TelaAcoes` resolvia os dois
 * passos expandindo campos inline — funcionava, mas punha a ação principal no
 * meio do conteúdo, e numa lista de cinco ações o aluno perdia de vista qual
 * delas estava respondendo. O fluxo linear guiado (`RF-57`) pede uma coisa por
 * tela, com o rodapé fixo dizendo o que fazer a seguir.
 *
 * **Esta tela não decide quais perguntas exibir.** `GET /caso/{id}/acoes` já
 * devolve os `campos` de cada ação, ramificados por `TIPO_ACAO` no servidor
 * (`AC-46`: ação de informação abre `B11.03-INF` e só ela). O cliente desenha
 * o que veio — `RF-52`.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import CampoPergunta from '../componentes/CampoPergunta'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import { type Acao, obterAcoes, responderAcao } from '../services/api'

interface TelaAcaoProps {
  casoId: string
  acaoId: string
  voltar: () => void
}

/** Chave de estado por campo — uma ação pode ter mais de uma pergunta. */
function chave(idPergunta: string): string {
  return idPergunta
}

export default function TelaAcao({ casoId, acaoId, voltar }: TelaAcaoProps) {
  const [acao, setAcao] = useState<Acao | null>(null)
  const [valores, setValores] = useState<Record<string, string | string[]>>({})
  const [naoSei, setNaoSei] = useState<Record<string, boolean>>({})
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [gravando, setGravando] = useState(false)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const { acoes } = await obterAcoes(casoId)
      // A ação vem da lista, não de uma rota por `ACAO_ID`: é a mesma fonte
      // que `TelaAcoes` usa, então as duas telas nunca discordam sobre o que
      // está pendente.
      setAcao(acoes.find((a) => a.ACAO_ID === acaoId) ?? null)
    } catch {
      setErro('Não foi possível carregar esta ação.')
    } finally {
      setCarregando(false)
    }
  }, [casoId, acaoId])

  useEffect(() => {
    void carregar()
  }, [carregar])

  async function aoGravar(idPergunta: string) {
    setGravando(true)
    setErro(null)
    try {
      const k = chave(idPergunta)
      await responderAcao(casoId, {
        idPergunta,
        // `item_id` é o `ACAO_ID` — o Bloco 11 é repetível por AÇÃO, nunca
        // por dívida (`RF-33`, `AC-50`): a ação de economia não tem dívida
        // associada e ainda assim precisa ser reportável.
        itemId: acaoId,
        valor: naoSei[k] ? undefined : valores[k],
        naoSei: naoSei[k] ?? false,
      })
      // Recarrega: responder `B11.01` com "consegui" faz o servidor abrir a
      // pergunta de resultado do tipo. Quem decide isso é ele (`AC-46`).
      await carregar()
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível salvar.')
    } finally {
      setGravando(false)
    }
  }

  if (carregando) {
    return (
      <Tela titulo="Sobre uma ação" voltar={voltar}>
        <Esqueleto forma="pergunta" anuncio="Carregando a ação" />
      </Tela>
    )
  }

  if (!acao) {
    return (
      <Tela
        titulo="Esta ação não está mais pendente"
        voltar={voltar}
        acoes={<Botao onClick={voltar}>Ver o que fazer agora</Botao>}
      >
        {/* Não é erro: uma ação some da lista quando o recálculo a resolve.
            Dizer "não encontrada" sugeriria falha do sistema. */}
        <p className="lead">
          {erro ?? 'Ela pode ter sido concluída ou substituída por um plano novo.'}
        </p>
      </Tela>
    )
  }

  const pendentes = acao.campos
  const terminou = pendentes.length === 0

  return (
    <Tela
      titulo={acao.descricao}
      voltar={voltar}
      onde={acao.DIVIDA_ID ?? acao.TIPO_ACAO}
      acoes={
        terminou ? (
          <Botao onClick={voltar}>Ver o que fazer agora</Botao>
        ) : (
          <Botao variante="discreto" onClick={voltar}>
            Voltar para a lista
          </Botao>
        )
      }
    >
      <div className="linha flex-wrap">
        <span className="eyebrow">{acao.TIPO_ACAO}</span>
        {acao.prioridade_excepcional && (
          <span className="chip chip-atencao">Prioridade</span>
        )}
      </div>

      {acao.VALOR_ACAO_FINANCEIRA_IMEDIATA && (
        <p className="tabular-nums text-muted">
          {/* String do servidor — `RF-13`. Não formatamos aqui porque o campo
              pode vir de origens com casas diferentes; exibir o que veio é
              mais honesto que arriscar um centavo errado. */}
          Valor envolvido: {acao.VALOR_ACAO_FINANCEIRA_IMEDIATA}
        </p>
      )}

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}

      {terminou && (
        <p role="status" className="aviso-ok">
          <span>Tudo registrado por aqui. Obrigado por contar como foi.</span>
        </p>
      )}

      {pendentes.map((pergunta) => {
        const k = chave(pergunta.ID)
        return (
          <div key={pergunta.ID} className="flex flex-col gap-3">
            <CampoPergunta
              pergunta={pergunta}
              valor={valores[k] ?? ''}
              naoSei={naoSei[k] ?? false}
              onValor={(v) => setValores((a) => ({ ...a, [k]: v }))}
              onNaoSei={(m) => setNaoSei((a) => ({ ...a, [k]: m }))}
            />
            <Botao disabled={gravando} onClick={() => void aoGravar(pergunta.ID)}>
              {gravando ? 'Salvando…' : 'Salvar'}
            </Botao>
          </div>
        )
      })}
    </Tela>
  )
}
