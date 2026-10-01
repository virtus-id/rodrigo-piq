/**
 * O plano do aluno — telas `plano`, `plano-estab` e `plano-vazio` do
 * protótipo (`RF-50`, `AC-14`, `AC-16`, `AC-70`).
 *
 * **Todo texto normativo vem do servidor, verbatim.** `titulo` e `corpo` são
 * a redação canônica de `Q-03`, carregada de `textos-canonicos.yaml` e
 * transportada sem uma vírgula de diferença — `AC-14` exige caractere por
 * caractere, e `AC-15` proíbe "definitiva"/"final"/"fixa" no lugar de
 * "projetada". Este componente **nunca** reescreve nem resume esses campos,
 * e isso vale também para o `titulo` que sobe à casca.
 *
 * **Nenhum número é calculado aqui** (Lei nº 3): prazo, custo e valores de
 * apoio são leitura de campo do snapshot, já formatados pelo servidor.
 */
import { useCallback, useEffect, useState } from 'react'

import Esqueleto from '../componentes/Esqueleto'
import Icone from '../componentes/Icone'
import Tela from '../componentes/Tela'
import { obterPlano } from '../services/api'
import type { Plano } from '../tipos'

/** O título enquanto o plano não chegou — a casca precisa de um sempre. */
const TITULO_PROVISORIO = 'Meu plano'

/** `RF-96`: o que não está no snapshot aparece assim, nunca estimado. */
const NAO_DISPONIVEL = 'não disponível'

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
      {/* Redação canônica — do servidor, sem reescrita. */}
      <p className="lead">{plano.corpo}</p>

      {plano.MODO_ESTABILIZACAO && (
        <div className="aviso-atencao" role="status">
          <div>
            <strong className="block">Antes de atacar as dívidas.</strong>
            Nesta fase o objetivo é equilibrar o mês. O caixa observado é{' '}
            {plano.RESULTADO_CAIXA_OBSERVADO}.
          </div>
        </div>
      )}

      {/*
        O resumo vem ANTES do detalhe — `RF-73`, `AC-109` (T-167).

        **Por que subiu.** Prazo e custo ficavam num `<dl>` de duas colunas
        DEPOIS da ordem, no mesmo cartão cinza de qualquer outra tela. Mas é
        esta a resposta que o aluno abriu a tela para ver: quanto tempo, e
        quanto custa. A ordem de quitação é o detalhe que sustenta a
        resposta, não a resposta.

        **Nenhum número é calculado aqui** (Lei nº 3). `PRAZO_TOTAL` e
        `CUSTO_FUTURO_TOTAL` chegam do snapshot já formatados pelo servidor
        e são exibidos verbatim — esta tarefa move e redimensiona, não
        recalcula nem reformata.
      */}
      <div className="cartao-destaque">
        <span className="eyebrow">Se você seguir este plano</span>
        {/*
          `flex-col-reverse` põe o VALOR acima do RÓTULO na tela, mantendo a
          ordem exigida pelo HTML no DOM (`<dt>` antes de `<dd>`). Inverter
          no DOM leria "até a última quitação" depois do número num leitor
          de tela — e um `<dd>` antes do seu `<dt>` é HTML inválido.
        */}
        <dl className="flex flex-wrap gap-x-8 gap-y-4">
          <div className="flex min-w-[120px] flex-1 flex-col-reverse">
            <dt className="rotulo-hero">até a última quitação</dt>
            <dd className="valor-hero m-0">{plano.PRAZO_TOTAL}</dd>
          </div>
          <div className="flex min-w-[120px] flex-1 flex-col-reverse">
            <dt className="rotulo-hero">de custo futuro</dt>
            <dd className="valor-hero m-0">{plano.CUSTO_FUTURO_TOTAL}</dd>
          </div>
          {/* `T-304` (`DE-08`): a capacidade que alimenta o cronograma, lida
              do snapshot. Fora da estabilização: nessa fase não há ataque. */}
          {!plano.MODO_ESTABILIZACAO && (
            <div className="flex min-w-[120px] flex-1 flex-col-reverse">
              <dt className="rotulo-hero">a cada mês para quitar, além das parcelas</dt>
              <dd className="valor-hero m-0">
                {plano.valor_mensal_destinado || NAO_DISPONIVEL}
              </dd>
            </div>
          )}
        </dl>
      </div>

      {plano.ordem.length > 0 ? (
        <ol className="lista list-none p-0">
          {plano.ordem.map((posicao) => (
            <li key={posicao.DIVIDA_ID} className="cartao">
              <div className="flex items-baseline gap-4">
                {/* Não é `.item .num`: aquele seletor só vale dentro de
                    `.item`, e a ordem do plano é cartão, não linha de lista. */}
                <span className="font-serif text-[1.5rem] font-semibold text-accent">
                  {posicao.indice}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-bold">{posicao.DIVIDA_ID}</p>
                  {/*
                    `T-177`: o ALUNO lê a explicação em português. A
                    `JUSTIFICATIVA_POSICAO` técnica ("método BOLA_DE_NEVE,
                    critério: menor VALOR_RELEVANTE_PARA_QUITACAO… desempate
                    O-05") é texto de auditoria: desde `T-305` só o revisor a
                    recebe, e esta tela não a mostra nem como fallback.
                  */}
                  <p className="text-muted">{posicao.explicacao}</p>
                  {/* `T-304` (`DE-08`): lido do cronograma gravado. */}
                  <p className="text-muted">
                    Quitação prevista:{' '}
                    {posicao.mes_de_quitacao
                      ? `mês ${posicao.mes_de_quitacao} do plano`
                      : NAO_DISPONIVEL}
                  </p>
                  {/* `RF-92` (T-267): nível 2 ou 3 não bloqueia, mas fica
                      visível por dívida. */}
                  {posicao.fonte && (
                    <p className="text-muted">
                      Fonte de comprovação: {posicao.fonte}
                    </p>
                  )}
                  {/* `RF-82` (T-245): só na dívida com seguro prestamista. */}
                  {posicao.orientacao_seguro && (
                    <p className="text-muted">{posicao.orientacao_seguro}</p>
                  )}
                </div>
              </div>
              {posicao.valores_de_apoio.length > 0 && (
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                  {posicao.valores_de_apoio.map((apoio) => (
                    <div key={apoio.rotulo} className="contents">
                      <dt className="text-muted">{apoio.rotulo}</dt>
                      <dd className="m-0 tabular-nums">{apoio.valor}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </li>
          ))}
        </ol>
      ) : (
        // `EC-07`: ordem vazia nunca aparece como lista vazia sem contexto —
        // o que precisa ser resolvido antes vem em primeiro plano.
        <div className="flex flex-col gap-3">
          <h2>Primeiro, o que precisa ser resolvido</h2>
          <ul className="lista list-none p-0">
            {plano.acoes.map((acao, i) => (
              <li key={`${acao.DIVIDA_ID ?? 'sem-divida'}-${i}`} className="cartao">
                <p>{acao.descricao}</p>
                {acao.DIVIDA_ID && <small className="text-muted">{acao.DIVIDA_ID}</small>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* O cartão "Por mês" saiu daqui em T-167: os dois valores que ele
          mostrava são agora o resumo NO TOPO da tela (`AC-109`). Mantê-lo
          aqui repetiria prazo e custo na mesma tela, com duas formatações
          diferentes — que é exatamente a confusão que a Rodada 6 removeu do
          Início quando tirou a barra de progresso duplicada. */}

      {/* `AC-70`: reserva desconhecida é estado explícito, nunca R$ 0,00. */}
      <div className="cartao">
        <span className="eyebrow">
          <Icone nome="reserva" /> Sua reserva
        </span>
        {plano.reserva_mobilizavel.pendente_de_decisao ? (
          <p>
            <strong>Decisão pendente.</strong> Essa parte do plano fica em aberto até
            você decidir.
          </p>
        ) : (
          <p className="tabular-nums">{plano.reserva_mobilizavel.valor}</p>
        )}
      </div>

      {plano.pendencias && (
        <div className="aviso-atencao" role="status">
          <div>
            <strong className="block">Este plano está provisório.</strong>
            {plano.pendencias.inventario_incompleto && 'O inventário ainda não está completo. '}
            {plano.pendencias.campos_faltantes_por_divida.map((p) => (
              <span key={p.DIVIDA_ID} className="block">
                {p.DIVIDA_ID}: falta {p.campos.join(', ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/*
        `RF-98`, `AC-152` (`T-277`): o cenário adicional é uma seção PRÓPRIA,
        abaixo do plano e rotulada — nunca mistura os seus números ao resumo
        e à ordem acima, que são da projeção-base. Tudo lido do snapshot e
        formatado pelo servidor (Lei nº 3).
      */}
      {plano.cenario_adicional && (
        <section className="cartao" aria-labelledby="titulo-cenario-adicional">
          <h2 id="titulo-cenario-adicional">{plano.cenario_adicional.rotulo}</h2>
          <p className="text-muted">{plano.cenario_adicional.explicacao}</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            <dt className="text-muted">até a última quitação</dt>
            <dd className="m-0 tabular-nums">{plano.cenario_adicional.PRAZO_TOTAL}</dd>
            <dt className="text-muted">de custo futuro</dt>
            <dd className="m-0 tabular-nums">{plano.cenario_adicional.CUSTO_FUTURO_TOTAL}</dd>
            <dt className="text-muted">ordem</dt>
            <dd className="m-0">{plano.cenario_adicional.ordem.join(' → ')}</dd>
          </dl>
          {plano.cenario_adicional.itens.length > 0 && (
            <ul className="lista list-none p-0">
              {plano.cenario_adicional.itens.map((item) => (
                <li key={item.ITEM_ID} className="tabular-nums">
                  {item.ITEM_ID}: {item.valor} no mês {item.mes}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* `AC-16`: carimbo de versão na saída. Uma tela sem carimbo não diz
          de qual cálculo veio. */}
      {/* O ícone entra ANTES do texto e é `aria-hidden`: `plano.spec.ts:121`
          casa `/versão do cálculo 1\.0\.1/` por regex sobre o texto, que
          segue idêntico. */}
      <p className="carimbo flex items-center gap-2">
        <Icone nome="conferencia" />
        <span>
          versão do cálculo {plano.ENGINE_VERSION} · parâmetros{' '}
          {plano.PARAMETROS_VERSION} · método {plano.cenario}
        </span>
      </p>
    </Tela>
  )
}
