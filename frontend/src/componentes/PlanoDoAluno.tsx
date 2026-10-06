/**
 * O plano do aluno, só o conteúdo — `RF-50`, `RF-121`, `AC-14`, `AC-16`,
 * `AC-70` (T-347).
 *
 * **Um desenho, dois lugares.** A tela do aluno (`TelaPlano`) e a conferência do
 * revisor (`TelaEquipeCaso`) mostram ESTE componente: o que o revisor confere
 * é, linha por linha, o que o aluno vai receber — sem uma segunda redação. Ele
 * recebe o `plano` pronto; quem carrega (`obterPlano`) e quem dá a moldura
 * (`Tela`, título, "Baixar em PDF") é de quem o usa.
 *
 * **Modo revisor (`revisor`).** Acrescenta, sem tirar nada do que o aluno lê:
 * em cada dívida, a seção recolhível "Para o revisor" (dados de entrada dela e
 * a justificativa técnica da posição) e o motivo técnico de cada ação. E
 * esconde o que só faz sentido para o aluno ("Responder agora").
 *
 * **Todo texto vem do servidor, verbatim; nenhum número é calculado aqui** (Lei
 * nº 3). A única conta client-side é GEOMETRIA DE DESENHO dos gráficos SVG.
 */
import ComoFunciona from './ComoFunciona'
import DuvidasDoPlano from './DuvidasDoPlano'
import Icone from './Icone'
import JornadaDoPlano from './JornadaDoPlano'
import ListaDeDados from './ListaDeDados'
import PontoDePartida from './PontoDePartida'
import PrimeiraVitoria from './PrimeiraVitoria'
import PrimeiroPasso from './PrimeiroPasso'
import ResumoDoPlano from './ResumoDoPlano'
import Conquistas from './visuais/Conquistas'
import LinhaDoTempoDividas from './visuais/LinhaDoTempoDividas'
import type { EstadoInputs } from '../services/api'
import type { Plano } from '../tipos'

/** `RF-96`: o que não está no snapshot aparece assim, nunca estimado. */
const NAO_DISPONIVEL = 'não disponível'

interface PlanoDoAlunoProps {
  plano: Plano
  /**
   * Presente só na conferência do revisor (`RF-121`, `RF-122`): os dados de
   * entrada que produziram o plano, por dívida.
   */
  revisor?: { entradas: EstadoInputs }
}

export default function PlanoDoAluno({ plano, revisor }: PlanoDoAlunoProps) {
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
    <>
      {/* Revisão de design (2026-10-03): o plano chama o aluno pelo nome. */}
      <p className="eyebrow m-0">{preparadoPara}</p>

      {/* Redação vigente — do servidor, sem reescrita. */}
      <p className="lead">{plano.corpo}</p>

      {plano.explicacao_mes_1 && <p className="text-muted text-sm">{plano.explicacao_mes_1}</p>}

      {/* `T-352`: plano normal sem valor extra neste mês. */}
      {plano.aviso_sem_valor_extra && (
        <p className="aviso-atencao m-0" role="status">
          {plano.aviso_sem_valor_extra}
        </p>
      )}

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

      {/* O capítulo 2: logo após o resumo, o aluno vê as dívidas que o plano contém. */}
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
                  {/* `T-354`: a nota que o aluno deu e, em nota alta fora da
                      1ª posição, o aviso. Texto pronto; a ordem é do motor. */}
                  {posicao.incomodo && (
                    <p className="text-muted m-0 text-sm">
                      {posicao.incomodo}
                      {posicao.aviso_incomodo && ` ${posicao.aviso_incomodo}`}
                    </p>
                  )}
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
                  {/* `RF-122` (T-348): só o revisor. Os dados de entrada DESTA
                      dívida, como o motor os viu, com `DESCONHECIDO` visível. A
                      justificativa técnica da posição segue FORA da tela: o
                      critério do método aparece uma vez, no destaque da
                      conferência (`T-330`), e repeti-la por dívida foi o que
                      aquela decisão tirou. */}
                  {/* `T-354`: o que o aluno respondeu sobre atraso, cobrança
                      judicial e garantia, à vista; quem julga é o revisor. */}
                  {revisor && (posicao.fatos_de_risco ?? []).length > 0 && (
                    <ul
                      className="m-0 flex list-none flex-wrap gap-2 p-0"
                      aria-label="Respostas do aluno sobre risco da dívida"
                    >
                      {(posicao.fatos_de_risco ?? []).map((fato) => (
                        <li
                          key={fato.nome}
                          className="rounded-piq border border-line px-2 py-1 text-xs"
                        >
                          {fato.nome}: <strong>{fato.valor}</strong>
                        </li>
                      ))}
                    </ul>
                  )}
                  {revisor && (
                    <details className="rounded-piq border border-dashed border-line p-2">
                      <summary className="font-bold">Para o revisor</summary>
                      <div className="mt-2 flex flex-col gap-2">
                        <ListaDeDados
                          campos={
                            revisor.entradas.dividas.find(
                              (divida) => divida.DIVIDA_ID === posicao.DIVIDA_ID,
                            )?.campos ?? []
                          }
                        />
                      </div>
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
                {/* `T-326`: o motivo técnico do gate é do REVISOR; o aluno não o recebe. */}
                {revisor && acao.motivo && (
                  <small className="text-muted block">Motivo técnico: {acao.motivo}</small>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {plano.ponto_de_partida && (
        <PontoDePartida
          ponto={plano.ponto_de_partida}
          textos={plano.ponto_de_partida_textos ?? {}}
          titulo={secoes.ponto_de_partida ?? ''}
          mostrarValorExtra={!plano.MODO_ESTABILIZACAO && !ordemVazia}
        />
      )}

      {/* Capítulo 4, o ponto alto: o primeiro resultado vem antes do passo a passo. */}
      {!plano.MODO_ESTABILIZACAO && !ordemVazia && plano.primeira_vitoria && (
        <PrimeiraVitoria
          primeiraVitoria={plano.primeira_vitoria}
          titulo={secoes.primeira_vitoria ?? plano.primeira_vitoria_titulo ?? ''}
          complemento={plano.primeira_vitoria_complemento ?? ''}
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
                  {/* `RF-121`: a ação é do aluno — o revisor só lê a pendência. */}
                  {pendencia.ID_PERGUNTA && !revisor && (
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

      {/* `T-352`/`T-353`: o curso de entrada — introdução, aulas que ajudam e
          orientações em texto (sem percentual). Tudo do servidor. */}
      {plano.curso_ssd && (
        <section className="cartao" aria-labelledby="titulo-curso-ssd">
          <h2 id="titulo-curso-ssd">{plano.curso_ssd.introducao_titulo}</h2>
          <p className="m-0">{plano.curso_ssd.introducao}</p>
          <h3>{plano.curso_ssd.quadro_titulo}</h3>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {plano.curso_ssd.aulas.map((aula) => (
              <li key={aula.numero}>
                <strong>
                  Aula {aula.numero}: {aula.titulo}
                </strong>
                <span className="text-muted block text-sm">{aula.motivo}</span>
              </li>
            ))}
          </ul>
          {plano.curso_ssd.melhorar.length > 0 && (
            <>
              <h3>{plano.curso_ssd.melhorar_titulo}</h3>
              <p className="text-muted m-0">{plano.curso_ssd.melhorar_intro}</p>
              <ul className="m-0 flex list-none flex-col gap-1 p-0">
                {plano.curso_ssd.melhorar.map((item) => (
                  <li key={item.texto}>
                    {item.texto} <span className="text-muted">({item.aula})</span>
                  </li>
                ))}
              </ul>
            </>
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
    </>
  )
}
