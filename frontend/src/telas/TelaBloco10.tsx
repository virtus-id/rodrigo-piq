/**
 * Bloco 10 — o dinheiro disponível agora (`RF-18`, `AC-22`, `AC-23`,
 * `AC-24`).
 *
 * **Nunca se pergunta em qual dívida o dinheiro entra** (`AC-24`). As duas
 * perguntas têm `escopo_repeticao: NENHUM` justamente por isso: quem decide
 * a alocação é o plano, não o aluno e não esta tela. Perguntar seria
 * devolver ao aluno uma decisão que o método existe para tomar.
 *
 * **O limite é do servidor** (`AC-23`): `0 ≤ APROVADO ≤ RECOMENDADO` é
 * validado por `validar_cruzada` contra o campo do snapshot. Esta tela
 * exibe o recomendado, mas não valida — se validasse, seriam duas regras
 * onde deve haver uma.
 *
 * A tela só existe quando `ATAQUE_IMEDIATO_RECOMENDADO > 0`; abaixo disso o
 * servidor devolve `409` e não há o que perguntar.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import CampoPergunta from '../componentes/CampoPergunta'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import { ErroHttp, obterBloco10, responderBloco10 } from '../services/api'
import type { Pergunta } from '../tipos'

/** O título enquanto o recomendado não chegou — a casca precisa de um. */
const TITULO_PROVISORIO = 'Dinheiro disponível'

interface TelaBloco10Props {
  casoId: string
  voltar?: () => void
}

export default function TelaBloco10({ casoId, voltar }: TelaBloco10Props) {
  const [recomendado, setRecomendado] = useState('')
  const [campos, setCampos] = useState<Pergunta[]>([])
  const [valores, setValores] = useState<Record<string, string | string[]>>({})
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [fechado, setFechado] = useState(false)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const dados = await obterBloco10(casoId)
      setRecomendado(dados.ATAQUE_IMEDIATO_RECOMENDADO)
      setCampos(dados.campos)
      setFechado(false)
    } catch (falha) {
      // `409` = a guarda do servidor fechou a etapa (sem plano liberado, ou
      // recomendado igual a zero). `404` = a rota não existe naquele
      // servidor. Nos DOIS casos não há o que perguntar, e o certo é dizer
      // isso — nunca renderizar "Você tem ___ que pode usar agora" com o
      // valor vazio, que foi o que esta tela fez antes desta correção.
      if (falha instanceof ErroHttp && (falha.status === 409 || falha.status === 404)) {
        setFechado(true)
      } else {
        setErro(falha instanceof Error ? falha.message : 'Não foi possível carregar.')
      }
    } finally {
      setCarregando(false)
    }
  }, [casoId])

  useEffect(() => {
    void carregar()
  }, [carregar])

  async function aoConfirmar(idPergunta: string) {
    const valor = valores[idPergunta]
    if (typeof valor !== 'string') return
    setErro(null)
    try {
      await responderBloco10(casoId, idPergunta, valor)
      await carregar()
    } catch (falha) {
      // `AC-23`: o servidor recusa valor fora de `0 ≤ APROVADO ≤
      // RECOMENDADO` e nomeia o motivo — mostramos o que ele disse.
      setErro(falha instanceof Error ? falha.message : 'Não foi possível salvar.')
    }
  }

  if (carregando) {
    return (
      <Tela titulo={TITULO_PROVISORIO} voltar={voltar}>
        <Esqueleto forma="pergunta" anuncio="Carregando a decisão" />
      </Tela>
    )
  }

  if (fechado) {
    return (
      <Tela titulo="Nada a decidir agora" voltar={voltar}>
        <p className="lead">
          Esta etapa só aparece quando há recurso disponível para adiantar quitações.
        </p>
      </Tela>
    )
  }

  return (
    <Tela
      titulo={`Você tem ${recomendado} que pode usar agora`}
      voltar={voltar}
      acoes={
        // Cada campo confirma pela rota própria do Bloco 10, então o rodapé
        // não submete nada: a ação que sobra é encerrar a etapa.
        voltar && (
          <Botao variante="secundario" onClick={voltar}>
            Terminei por agora
          </Botao>
        )
      }
    >
      <p className="lead">
        Quanto disso você quer colocar nas dívidas? Você não precisa escolher em qual
        dívida — o plano cuida disso.
      </p>

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}

      {campos.map((pergunta) => (
        <div key={pergunta.ID} className="cartao">
          <CampoPergunta
            pergunta={pergunta}
            valor={valores[pergunta.ID] ?? ''}
            naoSei={false}
            onValor={(v) => setValores((a) => ({ ...a, [pergunta.ID]: v }))}
            onNaoSei={() => undefined}
          />
          <Botao onClick={() => void aoConfirmar(pergunta.ID)}>Confirmar</Botao>
        </div>
      ))}
    </Tela>
  )
}
