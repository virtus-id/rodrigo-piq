/**
 * Fichas repetíveis — tela `fichas` do protótipo (`RF-04`, `RF-53`).
 *
 * 108 das 247 perguntas têm `escopo_repeticao != NENHUM`. Sem esta tela o
 * aluno não cadastra nem uma dívida, e o Bloco 5 — o núcleo do PIQ — fica
 * inalcançável.
 *
 * `completa` vem do servidor (`pendencias_obrigatorias`), nunca é recontado
 * aqui: obrigatoriedade é regra, e regra mora num lugar só.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import { criarFicha, listarFichas, removerFicha } from '../services/api'
import type { Ficha } from '../tipos'

interface TelaFichasProps {
  casoId: string
  escopo: string
  /** O nome de UM item — "Dívida". Compõe o rótulo de cada linha e do botão. */
  titulo: string
  /**
   * O plural de `titulo` — "Dívidas". Prop própria, e não `titulo + "s"`:
   * plural em português não é regular ("ação" → "ações", "margem" →
   * "margens"), e um `+ "s"` que hoje acerta por acaso (só existe o
   * escopo "Dívida") quebraria em silêncio no próximo escopo que usar
   * esta tela.
   */
  tituloPlural: string
  voltar?: () => void
  onAbrirFicha: (itemId: string) => void
}

export default function TelaFichas({
  casoId,
  escopo,
  titulo,
  tituloPlural,
  voltar,
  onAbrirFicha,
}: TelaFichasProps) {
  const [fichas, setFichas] = useState<Ficha[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const dados = await listarFichas(casoId, escopo)
      setFichas(dados.fichas)
    } catch {
      setErro('Não foi possível carregar as fichas.')
    } finally {
      setCarregando(false)
    }
  }, [casoId, escopo])

  useEffect(() => {
    void carregar()
  }, [carregar])

  async function aoAdicionar() {
    try {
      await criarFicha(casoId, escopo)
      await carregar()
    } catch {
      setErro('Não foi possível adicionar.')
    }
  }

  async function aoRemover(itemId: string) {
    try {
      await removerFicha(casoId, escopo, itemId)
      await carregar()
    } catch {
      setErro('Não foi possível remover.')
    }
  }

  return (
    <Tela
      titulo={`Suas ${tituloPlural.toLowerCase()}`}
      voltar={voltar}
      onde={fichas.length > 0 ? `${fichas.length} cadastrada${fichas.length === 1 ? '' : 's'}` : undefined}
      acoes={
        <Botao variante="secundario" onClick={() => void aoAdicionar()}>
          + Adicionar {titulo.toLowerCase()}
        </Botao>
      }
    >
      <p className="lead">Uma ficha para cada item. Toque em uma para completar.</p>

      {/* Só na primeira carga — ver a nota em `TelaRevisao` (T-164). Aqui a
          recarga vem de adicionar ou remover ficha, e o esqueleto sobre a
          lista existente faria a tela piscar a cada operação. */}
      {carregando && fichas.length === 0 && (
        <Esqueleto forma="lista" anuncio="Carregando suas fichas" itens={3} />
      )}

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}

      {!carregando && fichas.length === 0 && (
        <p role="status" className="nota">
          Nenhuma ficha cadastrada ainda.
        </p>
      )}

      <ul className="lista list-none p-0">
        {fichas.map((ficha, indice) => (
          <li key={ficha.item_id} className="item">
            <span className="num">{indice + 1}</span>
            <div className="min-w-0 flex-1">
              <button
                type="button"
                className="text-left font-bold text-accent"
                onClick={() => onAbrirFicha(ficha.item_id)}
              >
                {titulo} {ficha.item_id}
              </button>
              <small className="block text-muted">
                {ficha.campos.length} campo{ficha.campos.length === 1 ? '' : 's'}
              </small>
            </div>
            <span
              className={`chip ${ficha.completa ? 'bg-accent-soft text-accent' : 'bg-warn-soft text-warn'}`}
            >
              {ficha.completa ? 'Completa' : 'Pendência'}
            </span>
            <button
              type="button"
              aria-label={`Remover ${titulo} ${ficha.item_id}`}
              className="min-h-toque px-3 text-muted"
              onClick={() => void aoRemover(ficha.item_id)}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </Tela>
  )
}
