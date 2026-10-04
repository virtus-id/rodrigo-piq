/**
 * Conquistas — plano amigável (2026-10-03).
 *
 * Uma prateleira de selos, um por dívida do plano, em contorno (ainda não
 * conquistados). Nenhum selo aparece preenchido: a confirmação de
 * quitação (Bloco 11/acompanhamento) é fora do escopo desta tarefa.
 *
 * Desenhado em HTML/CSS (não SVG), reaproveitando `.marca`/`.conquista` de
 * `index.css` — mais simples que um SVG para uma grade que já responde ao
 * layout do cartão em qualquer largura de tela.
 */
import type { PosicaoDaOrdem } from '../../tipos'
import Icone from '../Icone'

interface ConquistasProps {
  ordem: PosicaoDaOrdem[]
}

export default function Conquistas({ ordem }: ConquistasProps) {
  if (ordem.length === 0) return null

  // Puramente decorativo (`aria-hidden` no contêiner inteiro): o nome de
  // cada dívida e o mês de quitação já estão, em texto, na lista "Suas
  // dívidas, na ordem de quitação" — este bloco não repete esse texto como
  // nó de texto (usa `title` no selo, lido só por quem passa o mouse),
  // para não duplicar conteúdo que um leitor de tela leria duas vezes nem
  // quebrar uma busca por texto único no nome da dívida.
  return (
    <div aria-hidden="true" className="flex flex-wrap justify-center gap-5">
      {ordem.map((posicao, indice) => (
        <div key={posicao.DIVIDA_ID} className="conquista" style={{ width: '88px' }}>
          <span className="marca" title={posicao.nome}>
            <Icone nome="trofeu" />
          </span>
          <span className="text-xs">Dívida {indice + 1}</span>
          <span className="text-muted text-xs">
            {posicao.mes_de_quitacao ? `Mês ${posicao.mes_de_quitacao}` : 'não disponível'}
          </span>
        </div>
      ))}
    </div>
  )
}
