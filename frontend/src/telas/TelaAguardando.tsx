/**
 * Aguardando conferência — `RF-23`, `RF-25`, `AC-25`, `AC-26` (T-150).
 *
 * É a tela `#aguardando` do protótipo (linha ~505). **Todo** snapshot passa
 * pela fila antes de chegar ao aluno, recálculos inclusive — o aluno vê uma
 * espera clara, nunca um plano não conferido.
 *
 * Os botões "Simular: equipe liberou" do protótipo eram andaime de
 * demonstração e ficaram fora (`RF-50`, decisão do especialista).
 */
import Botao from '../componentes/Botao'
import Tela from '../componentes/Tela'
import type { Inicio } from '../tipos'

interface TelaAguardandoProps {
  /** O mesmo payload da tela Início — a mensagem do estado vem dele. */
  inicio: Inicio | null
  voltar: () => void
}

export default function TelaAguardando({ inicio, voltar }: TelaAguardandoProps) {
  return (
    <Tela
      titulo="Você não precisa fazer nada agora"
      voltar={voltar}
      onde={inicio?.versao_do_plano ? `Plano v${inicio.versao_do_plano}` : undefined}
      acoes={<Botao onClick={voltar}>Voltar ao início</Botao>}
    >
      {/*
        **A mensagem é a DAQUELE estado, e é a única afirmação sobre o cálculo
        que esta tela faz** — `EC-25`.

        Havia aqui um "Seu plano foi calculado" fixo, copiado do protótipo
        (linha 422). No protótipo `#aguardando` só era alcançável de
        `AGUARDANDO_REVISAO`, onde a frase é verdadeira. Com o mapa de fases
        de `RF-61`, `ERRO_DE_CALCULO` cai na MESMA fase `revisao` e no mesmo
        destino — e para esse aluno o plano **não** foi calculado: o cálculo
        falhou. A tela afirmava algo falso.

        `mensagem_do_estado_do_caso` diz "Seu plano está em revisão." ou "Seu
        plano está em nova análise." conforme o caso. Nos dois a resposta ao
        aluno é a mesma — *é com a gente* —, sem que nenhum deles leia uma
        frase que não vale para ele, e sem expor o erro técnico.
      */}
      <div className="aviso-ok" role="status">
        <div>
          {inicio ? (
            <>
              <strong>{inicio.mensagem}</strong> Uma pessoa da equipe confere tudo antes
              de você receber.
            </>
          ) : (
            <>Uma pessoa da equipe confere tudo antes de você receber.</>
          )}
        </div>
      </div>

      <p className="nota">
        Avisaremos por e-mail assim que o plano estiver liberado. Normalmente leva até 2
        dias úteis.
      </p>
    </Tela>
  )
}
