/**
 * Consentimento — tela `consentimento` do protótipo (`RF-30`, `AC-39`).
 *
 * **O texto é insumo externo, não redação minha.** `titulo` e `corpo` vêm de
 * `app/consentimento/textos/*.yaml` — responsabilidade do jurídico
 * (`PEND-01`). Enquanto aquele diretório estiver vazio, o servidor devolve
 * `503` e esta tela diz isso, em vez de mostrar um texto inventado ou de
 * deixar o aluno seguir sem aceitar.
 *
 * Nenhuma resposta é gravada antes do aceite: a guarda está no servidor
 * (`exigir_estado_permite_resposta`), não aqui — esta tela não é a
 * proteção, é a porta.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import { ErroHttp, obterTextoDoConsentimento, registrarConsentimento } from '../services/api'

/** O título enquanto o texto do jurídico não chegou — a casca exige um. */
const TITULO_PROVISORIO = 'Consentimento'

interface TelaConsentimentoProps {
  casoId: string
  voltar?: () => void
  onAceito: () => void
}

export default function TelaConsentimento({
  casoId,
  voltar,
  onAceito,
}: TelaConsentimentoProps) {
  const [titulo, setTitulo] = useState('')
  const [corpo, setCorpo] = useState('')
  const [aceite, setAceite] = useState(false)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const texto = await obterTextoDoConsentimento(casoId)
      setTitulo(texto.titulo)
      setCorpo(texto.corpo)
    } catch (falha) {
      setErro(
        falha instanceof ErroHttp && falha.status === 503
          ? 'O texto de consentimento ainda não foi publicado. Sem ele, a coleta não começa.'
          : 'Não foi possível carregar o texto.',
      )
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
        <Esqueleto forma="texto" anuncio="Carregando o texto de consentimento" />
      </Tela>
    )
  }

  if (erro && !titulo) {
    return (
      <Tela titulo={TITULO_PROVISORIO} voltar={voltar}>
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      </Tela>
    )
  }

  async function aoAceitar() {
    setEnviando(true)
    setErro(null)
    try {
      await registrarConsentimento(casoId, true)
      onAceito()
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : 'Não foi possível registrar.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    // O título da casca é o do jurídico, verbatim — o `<h1>` que a tela
    // desenhava era esse mesmo campo, e reescrevê-lo seria reescrever o texto.
    <Tela
      titulo={titulo}
      voltar={voltar}
      acoes={
        <Botao onClick={() => void aoAceitar()} disabled={!aceite || enviando}>
          {enviando ? 'Registrando…' : 'Concordar e começar'}
        </Botao>
      }
    >
      <div className="cartao">
        <p className="whitespace-pre-wrap">{corpo}</p>
      </div>

      <label className="opt">
        <input
          type="checkbox"
          className="h-[26px] w-[26px] accent-accent"
          checked={aceite}
          onChange={(e) => setAceite(e.target.checked)}
        />
        <span>Li e concordo</span>
      </label>

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}
    </Tela>
  )
}
