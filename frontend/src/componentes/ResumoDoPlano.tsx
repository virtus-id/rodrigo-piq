/**
 * Resumo do plano — `.cartao-destaque` (`T-167`, `RF-73`/`AC-109`), com a
 * frase de apoio a cada número: "R$ 300,00" sozinho não diz o que o valor
 * significa; a frase embaixo diz.
 *
 * Revisão de redação (2026-10-03): rótulos e explicações vêm do servidor
 * (`textos-canonicos.yaml::resumo`); os textos abaixo são só o recurso
 * para um payload antigo, sem eles.
 *
 * **Nenhum número é calculado aqui** (Lei nº 3): os valores chegam do
 * snapshot já formatados pelo servidor e são exibidos sem alteração.
 */
interface ResumoDoPlanoProps {
  prazoTotal: string
  custoFuturoTotal: string
  valorMensalDestinado?: string
  /** Oculta o valor mensal: ordem vazia não tem ataque em curso. */
  mostrarValorMensal: boolean
  textos: Record<string, string>
}

const NAO_DISPONIVEL = 'não disponível'

interface NumeroProps {
  valor: string
  rotulo: string
  explicacao: string
}

function Numero({ valor, rotulo, explicacao }: NumeroProps) {
  return (
    <div className="flex min-w-[140px] flex-1 flex-col gap-1">
      {/* `flex-col-reverse` mantém `<dt>` antes de `<dd>` no DOM (HTML
          válido e leitura correta no leitor de tela) e o valor acima. */}
      <div className="flex flex-col-reverse">
        <dt className="rotulo-hero">{rotulo}</dt>
        <dd className="valor-hero m-0">{valor}</dd>
      </div>
      <p className="text-muted m-0 text-sm">{explicacao}</p>
    </div>
  )
}

export default function ResumoDoPlano({
  prazoTotal,
  custoFuturoTotal,
  valorMensalDestinado,
  mostrarValorMensal,
  textos,
}: ResumoDoPlanoProps) {
  return (
    <div className="cartao-destaque">
      <span className="eyebrow">Se você seguir este plano</span>
      <dl className="flex flex-wrap gap-x-8 gap-y-5">
        <Numero
          valor={prazoTotal}
          rotulo={textos.prazo_rotulo || 'para quitar todas as dívidas do plano'}
          explicacao={textos.prazo_explicacao || ''}
        />
        {mostrarValorMensal && (
          <Numero
            valor={valorMensalDestinado || NAO_DISPONIVEL}
            rotulo={textos.valor_mensal_rotulo || 'a mais todo mês, além das parcelas'}
            explicacao={textos.valor_mensal_explicacao || ''}
          />
        )}
        <Numero
          valor={custoFuturoTotal}
          rotulo={textos.custo_futuro_rotulo || 'é o total que você ainda vai pagar'}
          explicacao={textos.custo_futuro_explicacao || ''}
        />
      </dl>
    </div>
  )
}
