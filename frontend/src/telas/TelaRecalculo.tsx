/**
 * O plano vai ser refeito — `RF-19`, `RF-28`, `AC-26`, `AC-30`, `V-01`
 * (T-150).
 *
 * É a tela `#recalculo` do protótipo (linha ~633). Aparece depois de um
 * evento que dispara recálculo: quitação confirmada ou evento material.
 *
 * **O que esta tela promete é o que o sistema garante.** "O plano anterior
 * fica guardado" não é conforto: `V-01` é append-only, com trigger no banco
 * e porta sem `atualizar`/`remover`. O novo snapshot nasce com
 * `versao = anterior + 1` encadeado ao anterior, e entra na fila de revisão
 * como qualquer outro (`AC-26` — a política não distingue primeiro envio de
 * recálculo).
 */
import Botao from '../componentes/Botao'
import Tela from '../componentes/Tela'
import type { Inicio } from '../tipos'

interface TelaRecalculoProps {
  inicio: Inicio | null
  /** "Entendi" — volta ao Início, que já refletirá a fase nova. */
  voltar: () => void
}

export default function TelaRecalculo({ inicio, voltar }: TelaRecalculoProps) {
  const versaoAnterior = inicio?.versao_do_plano ?? null

  return (
    <Tela
      titulo="Vamos refazer o seu plano"
      voltar={voltar}
      acoes={<Botao onClick={voltar}>Entendi</Botao>}
    >
      <div className="aviso-ok" role="status">
        <div>
          <strong>Anotado.</strong> Isso muda o seu plano.
        </div>
      </div>

      <p className="lead">
        O plano anterior fica guardado. O novo será calculado e conferido pela equipe
        antes de chegar até você.
      </p>

      {versaoAnterior !== null && (
        <div className="cartao">
          <span className="eyebrow">Histórico</span>
          <div className="linha">
            <span>Plano {versaoAnterior}</span>
            <span className="chip chip-mudo">Guardado</span>
          </div>
          <div className="linha">
            <span>Plano {versaoAnterior + 1}</span>
            <span className="chip chip-atencao">Em conferência</span>
          </div>
        </div>
      )}
    </Tela>
  )
}
