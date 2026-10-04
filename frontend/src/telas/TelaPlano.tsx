/**
 * O plano do aluno — telas `plano`, `plano-estab` e `plano-vazio` do
 * protótipo (`RF-50`, `AC-14`, `AC-16`, `AC-70`).
 *
 * **Plano amigável (2026-10-03).** O título e o corpo deixaram de ser a
 * transcrição literal de `Q-03` e passaram a ser a redação de
 * "consultoria individual" aprovada pelo usuário nesta conversa — mas a
 * disciplina continua a mesma: **todo texto vem do servidor, verbatim.**
 * `titulo` e `corpo` são transportados sem uma vírgula de diferença — o
 * termo que qualifica o plano agora é "inteligente", nunca
 * "definitiva"/"final"/"fixa". Este componente **nunca** reescreve nem
 * resume esses campos.
 *
 * **Nenhum número é calculado aqui** (Lei nº 3): prazo, custo e valores de
 * apoio são leitura de campo do snapshot, já formatados pelo servidor. A
 * única conta client-side é GEOMETRIA DE DESENHO dos gráficos SVG
 * (`frontend/src/componentes/visuais/*`), nunca um valor exibido.
 */
import { useCallback, useEffect, useState } from 'react'

import ComoFunciona from '../componentes/ComoFunciona'
import DuvidasDoPlano from '../componentes/DuvidasDoPlano'
import Esqueleto from '../componentes/Esqueleto'
import Icone from '../componentes/Icone'
import JornadaDoPlano from '../componentes/JornadaDoPlano'
import PrimeiraVitoria from '../componentes/PrimeiraVitoria'
import PontoDePartida from '../componentes/PontoDePartida'
import PrimeiroPasso from '../componentes/PrimeiroPasso'
import ResumoDoPlano from '../componentes/ResumoDoPlano'
import Tela from '../componentes/Tela'
import Conquistas from '../componentes/visuais/Conquistas'
import LinhaDoTempoDividas from '../componentes/visuais/LinhaDoTempoDividas'
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

  const ordemVazia = plano.ordem.length === 0
  const secoes = plano.secoes ?? {}
  const textosDasDividas = plano.dividas_textos ?? {}
  const cabecalho = plano.cabecalho_textos ?? {}
  const preparadoPara = plano.nome_do_aluno
    ? (cabecalho.preparado_para ?? 'Plano preparado para {nome}').replace(
        '{nome}',
        plano.nome_do_aluno,
      )
    : (cabecalho.preparado_sem_nome ?? 'Plano preparado para você')

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
      {/* Revisão de design (2026-10-03): o plano chama o aluno pelo nome. */}
      <p className="eyebrow m-0">{preparadoPara}</p>

      {/* Redação vigente — do servidor, sem reescrita. */}
      <p className="lead">{plano.corpo}</p>

      {plano.explicacao_mes_1 && <p className="text-muted text-sm">{plano.explicacao_mes_1}</p>}

      {plano.MODO_ESTABILIZACAO && (
        <div className="aviso-atencao" role="status">
          <div>
            <strong className="block">Primeiro, equilibrar o seu mês.</strong>
            Hoje, considerando o que entra e o que sai, o resultado do seu mês é de{' '}
            {plano.RESULTADO_CAIXA_OBSERVADO}. Esse valor ainda não pode ser usado para
            quitar dívidas. Nesta fase, o objetivo é equilibrar as contas do mês.
          </div>
        </div>
      )}

      {!plano.MODO_ESTABILIZACAO && (
        <ResumoDoPlano
          prazoTotal={plano.PRAZO_TOTAL}
          custoFuturoTotal={plano.CUSTO_FUTURO_TOTAL}
          valorMensalDestinado={plano.valor_mensal_destinado}
          mostrarValorMensal={!ordemVazia}
          textos={plano.resumo_textos ?? {}}
        />
      )}

      {plano.ponto_de_partida && (
        <PontoDePartida
          ponto={plano.ponto_de_partida}
          textos={plano.ponto_de_partida_textos ?? {}}
          titulo={secoes.ponto_de_partida ?? ''}
          mostrarValorExtra={!plano.MODO_ESTABILIZACAO && !ordemVazia}
        />
      )}

      {!plano.MODO_ESTABILIZACAO && !ordemVazia && plano.passo_atual && (
        <PrimeiroPasso
          passo={plano.passo_atual}
          titulo={secoes.primeiro_passo ?? plano.primeiro_passo_titulo ?? ''}
          textos={
            plano.primeiro_passo_textos ?? { como_pagar_a_mais: plano.como_pagar_a_mais ?? '' }
          }
        />
      )}

      {!plano.MODO_ESTABILIZACAO && !ordemVazia && plano.primeira_vitoria && (
        <PrimeiraVitoria
          primeiraVitoria={plano.primeira_vitoria}
          titulo={secoes.primeira_vitoria ?? plano.primeira_vitoria_titulo ?? ''}
          complemento={plano.primeira_vitoria_complemento ?? ''}
        />
      )}

      {!plano.MODO_ESTABILIZACAO && !ordemVazia && (plano.como_funciona?.length ?? 0) > 0 && (
        <ComoFunciona
          passos={plano.como_funciona ?? []}
          rotulos={plano.como_funciona_rotulos ?? []}
          titulo={secoes.como_funciona ?? plano.como_funciona_titulo ?? ''}
        />
      )}

      {!plano.MODO_ESTABILIZACAO && !ordemVazia && (plano.grade_meses?.length ?? 0) > 0 && (
        <JornadaDoPlano
          grade={plano.grade_meses ?? []}
          anos={plano.grade_anos ?? []}
          textos={plano.grade_meses_textos ?? {}}
          titulo={secoes.jornada ?? plano.jornada_titulo ?? ''}
        />
      )}

      {!plano.MODO_ESTABILIZACAO && !ordemVazia && (
        <section className="cartao" aria-labelledby="titulo-linha-do-tempo">
          <h2 id="titulo-linha-do-tempo">
            {plano.linha_do_tempo_textos?.titulo || 'Quando cada dívida termina'}
          </h2>
          {plano.linha_do_tempo_textos?.introducao && (
            <p className="text-muted m-0">{plano.linha_do_tempo_textos.introducao}</p>
          )}
          <LinhaDoTempoDividas
            ordem={plano.ordem}
            prazoTotalMeses={plano.PRAZO_TOTAL_INT}
            textos={plano.linha_do_tempo_textos ?? {}}
          />
        </section>
      )}

      {plano.ordem.length > 0 ? (
        <>
          <h2>{secoes.dividas ?? 'Suas dívidas, uma a uma'}</h2>
          {textosDasDividas.introducao && (
            <p className="text-muted m-0">{textosDasDividas.introducao}</p>
          )}
          <ol className="lista list-none p-0">
            {plano.ordem.map((posicao) => {
              const fatos = posicao.fatos ?? []
              const rotulosDosFatos = new Set(fatos.map((fato) => fato.rotulo))
              // Os valores de apoio sustentam a POSIÇÃO (`AC-17`); os que já
              // aparecem nos números fixos não se repetem.
              const outrosValores = posicao.valores_de_apoio.filter(
                (apoio) => !rotulosDosFatos.has(apoio.rotulo),
              )
              return (
                <li key={posicao.DIVIDA_ID} className="cartao">
                  <div className="flex items-center gap-3">
                    <span className="grid h-10 w-10 flex-none place-items-center rounded-full bg-accent font-bold text-accent-ink">
                      {posicao.indice}
                    </span>
                    <div className="min-w-0 flex-1">
                      {textosDasDividas.posicao && (
                        <span className="eyebrow block">
                          {textosDasDividas.posicao.replace('{indice}', String(posicao.indice))}
                        </span>
                      )}
                      {/* `T-326` (`RF-111`): "tipo (credor)", nunca o código. */}
                      <p className="m-0 font-bold">{posicao.nome}</p>
                    </div>
                  </div>
                  {/*
                    `T-177`: o ALUNO lê a explicação em português. A
                    `JUSTIFICATIVA_POSICAO` técnica é texto de auditoria:
                    desde `T-305` só o revisor a recebe, e esta tela não a
                    mostra nem como fallback.
                  */}
                  <p className="m-0">{posicao.explicacao}</p>
                  {/* Revisão de design: os números de toda dívida ficam à
                      vista, inclusive o mês em que ela termina (`T-304`,
                      lido do cronograma gravado). */}
                  <dl className="m-0 grid grid-cols-2 gap-2">
                    {fatos.map((fato) => (
                      <div key={fato.rotulo} className="rounded-piq border border-line p-2">
                        <dt className="text-muted text-xs">{fato.rotulo}</dt>
                        <dd className="m-0 whitespace-nowrap font-bold tabular-nums">{fato.valor}</dd>
                      </div>
                    ))}
                    <div className="rounded-piq border border-accent bg-accent-soft p-2">
                      <dt className="text-muted text-xs">
                        {textosDasDividas.termina_no ?? 'Termina no'}
                      </dt>
                      <dd className="m-0 font-bold">
                        {posicao.mes_de_quitacao
                          ? `Mês ${posicao.mes_de_quitacao}`
                          : NAO_DISPONIVEL}
                      </dd>
                    </div>
                  </dl>
                  {/* `RF-92` (T-267): nível 2 ou 3 não bloqueia, mas fica
                      visível por dívida. */}
                  {posicao.fonte && (
                    <p className="text-muted m-0 text-sm">Fonte das informações: {posicao.fonte}</p>
                  )}
                  {/* `RF-82` (T-245): só na dívida com seguro prestamista. */}
                  {posicao.orientacao_seguro && (
                    <p className="text-muted m-0 text-sm">{posicao.orientacao_seguro}</p>
                  )}
                  {/* Na tela, os demais números ficam a um toque; no PDF
                      eles aparecem abertos. */}
                  {outrosValores.length > 0 && (
                    <details>
                      <summary>Ver outros números desta dívida</summary>
                      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                        {outrosValores.map((apoio) => (
                          <div key={apoio.rotulo} className="contents">
                            <dt className="text-muted">{apoio.rotulo}</dt>
                            <dd className="m-0 tabular-nums">{apoio.valor}</dd>
                          </div>
                        ))}
                      </dl>
                    </details>
                  )}
                </li>
              )
            })}
          </ol>
          {!plano.MODO_ESTABILIZACAO && <Conquistas ordem={plano.ordem} />}
        </>
      ) : (
        // `EC-07`: ordem vazia nunca aparece como lista vazia sem contexto;
        // o que precisa ser resolvido antes vem em primeiro plano.
        <div className="flex flex-col gap-3">
          <h2>Primeiro, o que precisa ser resolvido</h2>
          <ul className="lista list-none p-0">
            {plano.acoes.map((acao, i) => (
              <li key={`${acao.DIVIDA_ID ?? 'sem-divida'}-${i}`} className="cartao">
                {/* `T-306`: o que fazer, em português, por `TIPO_ACAO`; o
                    motivo técnico do gate não vem ao aluno. */}
                <p>{acao.descricao}</p>
                {acao.nome_divida && <small className="text-muted">{acao.nome_divida}</small>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* `AC-70`: reserva desconhecida é estado explícito, nunca R$ 0,00. */}
      <section className="cartao" aria-labelledby="titulo-reserva">
        <h2 id="titulo-reserva" className="flex items-center gap-2">
          <Icone nome="reserva" /> {secoes.reserva ?? 'Sua reserva'}
        </h2>
        {plano.reserva_mobilizavel.pendente_de_decisao ? (
          <p className="m-0">
            <strong>Decisão pendente.</strong> Essa parte do plano fica em aberto até
            você decidir.
          </p>
        ) : (
          <>
            <p className="valor-hero m-0 tabular-nums">{plano.reserva_mobilizavel.valor}</p>
            {plano.reserva_explicacao && (
              <p className="text-muted m-0">{plano.reserva_explicacao}</p>
            )}
          </>
        )}
      </section>

      {(plano.pendencias_acionaveis?.length ?? 0) > 0 ? (
        <div className="aviso-atencao" role="status">
          <div>
            <strong className="block">Este plano ainda é provisório.</strong>
            Faltam algumas informações sobre as suas dívidas. Assim que você as informar, o
            plano é refeito.
            {plano.pendencias?.inventario_incompleto &&
              ' O cadastro das suas dívidas ainda não foi confirmado como completo.'}
            <ul className="lista mt-2 list-none p-0">
              {(plano.pendencias_acionaveis ?? []).map((pendencia, i) => (
                <li key={`${pendencia.DIVIDA_ID}-${pendencia.rotulo}-${i}`}>
                  <strong>{pendencia.nome_divida}</strong>: falta informar {pendencia.rotulo}.
                  {pendencia.onde_achar && (
                    <span className="text-muted block">Onde encontrar: {pendencia.onde_achar}</span>
                  )}
                  {pendencia.ID_PERGUNTA && (
                    <a
                      className="btn-discreto"
                      href={`#respostas/${pendencia.ID_PERGUNTA}/${pendencia.DIVIDA_ID}`}
                    >
                      Responder agora
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        plano.pendencias && (
          <div className="aviso-atencao" role="status">
            <div>
              <strong className="block">Este plano ainda é provisório.</strong>
              {plano.pendencias.inventario_incompleto && 'O inventário ainda não está completo. '}
              {plano.pendencias.campos_faltantes_por_divida.map((p) => (
                <span key={p.DIVIDA_ID} className="block">
                  {p.nome}: falta {p.campos.join(', ')}
                </span>
              ))}
            </div>
          </div>
        )
      )}

      {/*
        `RF-98`, `AC-152` (`T-277`): o cenário adicional é uma seção PRÓPRIA,
        abaixo do plano e rotulada; nunca mistura os seus números ao resumo e
        à ordem acima, que são da projeção-base. Tudo lido do snapshot e
        formatado pelo servidor (Lei nº 3).
      */}
      {plano.cenario_adicional && (
        <section className="cartao" aria-labelledby="titulo-cenario-adicional">
          <h2 id="titulo-cenario-adicional">{plano.cenario_adicional.rotulo}</h2>
          <p className="text-muted">{plano.cenario_adicional.explicacao}</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            <dt className="text-muted">para quitar todas as dívidas</dt>
            <dd className="m-0 tabular-nums">{plano.cenario_adicional.PRAZO_TOTAL}</dd>
            <dt className="text-muted">total que você pagaria</dt>
            <dd className="m-0 tabular-nums">{plano.cenario_adicional.CUSTO_FUTURO_TOTAL}</dd>
            <dt className="text-muted">ordem de quitação</dt>
            <dd className="m-0">{plano.cenario_adicional.ordem.join(', ')}</dd>
          </dl>
          {plano.cenario_adicional.itens.length > 0 && (
            <ul className="lista list-none p-0">
              {plano.cenario_adicional.itens.map((item, i) => (
                <li key={item.ITEM_ID ?? `${item.mes}-${i}`} className="tabular-nums">
                  {item.valor} no Mês {item.mes}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <DuvidasDoPlano duvidas={plano.duvidas ?? []} titulo={secoes.duvidas ?? ''} />

      {plano.sobre_este_plano && (
        <section className="cartao" aria-labelledby="titulo-sobre">
          <h2 id="titulo-sobre">{secoes.sobre ?? 'Sobre este plano'}</h2>
          <p className="text-muted m-0">{plano.sobre_este_plano}</p>
        </section>
      )}

      {/* `AC-16`: carimbo de versão na saída. Uma tela sem carimbo não diz
          de qual cálculo veio. */}
      <p className="carimbo flex items-center gap-2">
        <Icone nome="conferencia" />
        <span>
          versão do cálculo {plano.ENGINE_VERSION} · parâmetros{' '}
          {plano.PARAMETROS_VERSION}
          {plano.ordem.length > 0 && !plano.MODO_ESTABILIZACAO && ` · método ${plano.metodo}`}
        </span>
      </p>
    </Tela>
  )
}
