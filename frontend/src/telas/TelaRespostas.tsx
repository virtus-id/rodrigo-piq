/**
 * Minhas respostas — rever e corrigir o que já foi dito (`RF-68`, `RF-69`,
 * `AC-100`, `AC-101`, `AC-102`) (T-160).
 *
 * **Por que existe.** `RF-10` promete retomada sem redigitar, e o sistema
 * cumpria: a coleta voltava exatamente onde parou. Mas retomar não é
 * **conferir**. O relato do segundo teste com usuário foi literal — *"nem
 * consigo ver o que foi respondido, e se eu esquecer"* — e não havia nenhuma
 * superfície que mostrasse ao aluno o que ele já tinha dito.
 *
 * Para quem responde cem perguntas sobre o próprio dinheiro ao longo de
 * semanas, não poder reler o que disse é não poder confiar no plano que sai
 * dali.
 *
 * **Esta tela não decide o que aparece.** As cinco partes vêm do servidor
 * (`GET /caso/{id}/respostas`), inclusive as vazias — `AC-101` é contrato
 * daquela rota, não filtro daqui. O cliente nunca soube quais perguntas
 * existem (`RF-45`) e continua não sabendo.
 *
 * **"Editar" não é um segundo caminho de escrita** (`RF-69`). Ele apenas
 * navega para `#pergunta/{ID}/{item_id}`, a mesma tela de coleta, que grava
 * pela mesma rota de sempre. Uma segunda via de gravação seria uma segunda
 * regra de validação, e `EC-01` deixaria de ser soberano.
 *
 * **Menu de partes + painel (`T-334`).** As cinco partes ficam num menu
 * sempre visível; clicar numa mostra só as respostas dela. A parte aberta vive
 * na rota (`#respostas/bloco/{n}`): recarregar, ou voltar de uma correção,
 * reabre a MESMA parte em vez de jogar o aluno de volta ao topo. O menu é
 * deste componente e não da trilha da jornada/coleta — aquelas continuam
 * informativas (`AC-115`, `RF-100`).
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import { obterRespostasDoCaso, retomarEdicao } from '../services/api'
import { formatarDecimalDoServidor, formatarTaxaDoServidor } from '../mascaras'
import type { ParteDasRespostas, RespostaDada, RespostasDoCaso } from '../tipos'

interface TelaRespostasProps {
  casoId: string
  voltar: () => void
  /** A parte aberta, vinda da rota. Ausente ⇒ a primeira que tem resposta. */
  bloco?: number
  escolherBloco: (bloco: number) => void
  /** Abre a pergunta para correção — `RF-69`, `AC-102`. */
  editar: (idPergunta: string, itemId: string | null, bloco: number) => void
}

/**
 * O que o aluno respondeu, numa linha — `AC-100`.
 *
 * **"Não sei" é resposta, e aparece como tal** (`RF-11`). Escondê-la, ou
 * mostrá-la como um traço, faria o aluno procurar uma pergunta que ele já
 * resolveu — e "não sei" é uma decisão que ele tomou, não uma omissão.
 *
 * A vírgula que junta os valores é decisão DESTA camada: o servidor manda
 * lista justamente para não impor um separador (`SELECAO_MULTIPLA` tem vários
 * rótulos, e cada um deles é redação do questionário).
 */
function textoDaResposta(resposta: RespostaDada): string {
  if (resposta.respondida_como_nao_sei) return 'Você respondeu: não sei.'
  if (resposta.valores.length === 0) return 'Respondida.'
  return resposta.valores.map((valor) => exibir(valor, resposta.tipo)).join(', ')
}

/**
 * `T-335`: o servidor manda o valor cru (`0.08`, `2276.76`); aqui ele vira o que
 * o aluno digitou — "8%", "R$ 2.276,76". Só o que é número decimal: um rótulo
 * ou um código passa intacto.
 */
function exibir(valor: string, tipo: RespostaDada['tipo']): string {
  if (!/^\d+(\.\d+)?$/.test(valor)) return valor
  if (tipo === 'TAXA') return `${formatarTaxaDoServidor(valor)}%`
  if (tipo === 'MOEDA') return `R$ ${formatarDecimalDoServidor(valor)}`
  return valor
}

/**
 * "N de M respondidas" — a contagem de uma parte.
 *
 * `total_de_perguntas` conta na mesma unidade das respostas (`T-297`): numa
 * ficha repetível, cada pergunta vale uma vez por item (36 perguntas × 3
 * dívidas = 108). O total inclui condicionais que talvez nunca abram, por
 * isso a frase não promete proporção — ela informa duas quantidades reais.
 */
function contagemDaParte(parte: ParteDasRespostas): string {
  const dadas = parte.respondidas.length
  const plural = dadas === 1 ? 'resposta' : 'respostas'
  return `${dadas} ${plural} de ${parte.total_de_perguntas} perguntas`
}

/** Um grupo de respostas: soltas (`item_id` nulo) ou de um item de ficha. */
export interface GrupoDeRespostas {
  itemId: string | null
  /** `null` para as soltas; "Dívida 1", "Dívida 2"… para as fichas. */
  titulo: string | null
  respostas: RespostaDada[]
}

/**
 * Junta as respostas de uma mesma ficha — `T-334`.
 *
 * O servidor entrega a pergunta 1 de todas as dívidas, depois a pergunta 2 de
 * todas… (`T-297`): ótimo para contar, ruim para ler "tudo da dívida X". Aqui
 * as soltas vão primeiro e cada `item_id` vira um cartão, na ordem em que
 * aparece e SEM reordenar as perguntas dentro dele. O título é só um ordinal:
 * o nome real da dívida já vem no enunciado de cada pergunta.
 */
export function agruparPorItem(respondidas: readonly RespostaDada[]): GrupoDeRespostas[] {
  const soltas = respondidas.filter((r) => r.item_id === null)
  const porItem = new Map<string, RespostaDada[]>()
  for (const r of respondidas) {
    if (r.item_id !== null) porItem.set(r.item_id, [...(porItem.get(r.item_id) ?? []), r])
  }
  const grupos: GrupoDeRespostas[] = []
  if (soltas.length) grupos.push({ itemId: null, titulo: null, respostas: soltas })
  let n = 0
  for (const [itemId, respostas] of porItem) {
    n += 1
    grupos.push({
      itemId,
      titulo: `${itemId.startsWith('D') ? 'Dívida' : 'Item'} ${n}`,
      respostas,
    })
  }
  return grupos
}

/**
 * Uma resposta, numa linha compacta — `T-339`.
 *
 * No desktop são três colunas (pergunta · resposta · "Editar" à direita), de
 * modo que cem respostas se leem como uma tabela, não como cem cartões. No
 * celular a pergunta e a resposta empilham à esquerda e o botão fica à
 * direita, na mesma altura. O botão é compacto de propósito: é uma ação
 * repetida em toda linha, e o que o aluno veio ler é a resposta.
 */
function FichaDaResposta({
  resposta,
  editar,
  estreita = false,
}: {
  resposta: RespostaDada
  /** Ausente ⇒ só leitura (`RF-114`): sem o botão. */
  editar?: () => void
  /**
   * Cartão que divide a linha com outro (monitor largo, `T-340`): a partir de
   * `xl:` a linha volta a empilhar pergunta e resposta, porque o cartão já não
   * tem largura para três colunas. Fora disso são três colunas desde `lg:`.
   */
  estreita?: boolean
}) {
  const linha = estreita
    ? 'lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_auto] lg:gap-x-6 xl:grid-cols-[minmax(0,1fr)_auto] xl:gap-x-4'
    : 'lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_auto] lg:gap-x-6'
  const valor = estreita
    ? 'lg:col-start-2 lg:row-start-1 lg:self-center xl:col-start-1 xl:row-start-auto xl:self-auto'
    : 'lg:col-start-2 lg:row-start-1 lg:self-center'
  const botao = estreita
    ? 'lg:col-start-3 lg:row-span-1 xl:col-start-2 xl:row-span-2'
    : 'lg:col-start-3 lg:row-span-1'

  return (
    <li
      className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-0.5 border-b border-line py-1.5 last:border-b-0 ${linha}`}
    >
      <small className="col-start-1 text-muted lg:self-center xl:self-auto">
        {resposta.enunciado}
      </small>
      <strong className={`col-start-1 break-words text-base ${valor}`}>
        {textoDaResposta(resposta)}
        {resposta.respondida_como_nao_sei && (
          <span className="chip chip-mudo ml-2 align-middle">Não sei</span>
        )}
      </strong>
      {editar && (
        <Botao
          variante="discreto"
          className={`col-start-2 row-span-2 row-start-1 !w-auto !min-h-0 !border px-3 py-1 text-sm ${botao}`}
          onClick={editar}
        >
          Editar
        </Botao>
      )}
    </li>
  )
}

/**
 * O menu das cinco partes — `T-334`.
 *
 * Botões de verdade (`<nav>` + `aria-current="page"`): é navegação dentro da
 * tela, e por isso não é a trilha da coleta, que continua só informativa.
 * No celular é uma faixa que rola na horizontal; a partir de `lg:` é a coluna
 * lateral. A parte vazia leva "Vazia", e não some: `AC-101`.
 */
function MenuDasPartes({
  partes,
  ativa,
  escolher,
}: {
  partes: readonly ParteDasRespostas[]
  ativa: number | undefined
  escolher: (bloco: number) => void
}) {
  return (
    <nav aria-label="Partes das respostas">
      <ul className="m-0 flex list-none gap-2 overflow-x-auto p-0 lg:flex-col lg:overflow-visible">
        {partes.map((parte) => {
          const eAtiva = parte.bloco === ativa
          const vazia = parte.respondidas.length === 0
          return (
            <li key={parte.bloco} className="flex-none lg:flex-auto">
              <button
                type="button"
                aria-current={eAtiva ? 'page' : undefined}
                onClick={() => escolher(parte.bloco)}
                className={`w-full rounded-xl border px-3 py-2 text-left ${
                  eAtiva ? 'border-accent bg-accent-soft' : 'border-line bg-transparent'
                }`}
              >
                <span className="block font-bold">{parte.rotulo}</span>
                <small className="block text-muted">
                  {vazia ? 'Vazia' : contagemDaParte(parte)}
                </small>
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

/** As respostas de UMA parte — o painel à direita do menu. */
function PainelDaParte({
  parte,
  editar,
  titulo,
}: {
  parte: ParteDasRespostas
  /** Ausente ⇒ só leitura (`RF-114`). */
  editar?: (idPergunta: string, itemId: string | null) => void
  titulo: React.RefObject<HTMLHeadingElement | null>
}) {
  return (
    <section aria-labelledby="titulo-da-parte" className="flex flex-col gap-2">
      <div>
        <h2 id="titulo-da-parte" ref={titulo} tabIndex={-1} className="m-0">
          {parte.rotulo}
        </h2>
        <small className="block text-muted">{contagemDaParte(parte)}</small>
      </div>

      {parte.respondidas.length === 0 ? (
        // `AC-101`: a parte vazia DIZ que está vazia. Uma lista em branco
        // sugeriria erro de carregamento.
        <p className="nota">Você ainda não respondeu nada desta parte.</p>
      ) : (
        <div className="grid gap-2 xl:grid-cols-2 xl:items-start">
          {agruparPorItem(parte.respondidas).map((grupo) => (
            <div
              key={grupo.itemId ?? 'soltas'}
              className={
                grupo.titulo
                  ? 'cartao gap-1 p-3 lg:px-4'
                  : 'rounded-piq border border-line bg-surface px-3 lg:px-4 xl:col-span-2'
              }
            >
              {grupo.titulo && <span className="eyebrow">{grupo.titulo}</span>}
              <ul className="m-0 list-none p-0">
                {grupo.respostas.map((resposta) => (
                  <FichaDaResposta
                    // `ID` sozinho não é único: numa ficha repetível a mesma
                    // pergunta rende uma linha por dívida.
                    key={`${resposta.ID}/${resposta.item_id ?? ''}`}
                    resposta={resposta}
                    estreita={grupo.titulo !== null}
                    editar={editar ? () => editar(resposta.ID, resposta.item_id) : undefined}
                  />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export default function TelaRespostas({
  casoId,
  voltar,
  bloco,
  escolherBloco,
  editar,
}: TelaRespostasProps) {
  const [respostas, setRespostas] = useState<RespostasDoCaso | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const tituloDaParte = useRef<HTMLHeadingElement>(null)
  // `RF-115`: a retirada do plano da conferência pede confirmação em linha.
  const [confirmando, setConfirmando] = useState(false)
  const [retirando, setRetirando] = useState(false)
  const [erroRetirada, setErroRetirada] = useState<string | null>(null)

  async function retirarDaConferencia() {
    setRetirando(true)
    setErroRetirada(null)
    try {
      await retomarEdicao(casoId)
      setConfirmando(false)
      // Relê: o servidor devolve `editavel: true` e a lista volta a ter "Editar".
      await carregar()
    } catch (falha) {
      setErroRetirada(
        falha instanceof Error ? falha.message : 'Não foi possível retirar o plano agora.',
      )
    } finally {
      setRetirando(false)
    }
  }

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      setRespostas(await obterRespostasDoCaso(casoId))
    } catch {
      setErro('Não foi possível carregar as suas respostas.')
    } finally {
      setCarregando(false)
    }
  }, [casoId])

  useEffect(() => {
    void carregar()
  }, [carregar])

  // A parte da rota, se existir; senão a primeira que TEM resposta; senão a
  // primeira. Abrir tudo faria a tela nascer com cem linhas.
  const partes = respostas?.partes ?? []
  const ativa =
    partes.find((parte) => parte.bloco === bloco) ??
    partes.find((parte) => parte.respondidas.length > 0) ??
    partes[0]

  // Trocar de parte move o foco para o título do painel (leitor de tela). Só
  // na TROCA: no primeiro render quem foca é o `<h1>` da `Tela` (`AC-84`).
  // `undefined` até a primeira parte existir: a carga inicial NÃO é troca (antes
  // ela puxava o foco para o título e o desenhava com a borda de foco).
  const parteAnterior = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (ativa && parteAnterior.current !== undefined && parteAnterior.current !== ativa.bloco) {
      tituloDaParte.current?.focus()
    }
    parteAnterior.current = ativa?.bloco
  }, [ativa])

  if (carregando) {
    return (
      <Tela titulo="Minhas respostas" voltar={voltar}>
        <Esqueleto forma="lista" anuncio="Carregando suas respostas" itens={4} />
      </Tela>
    )
  }

  if (!respostas || !ativa) {
    return (
      <Tela titulo="Minhas respostas" voltar={voltar}>
        <p role="alert" className="aviso-erro">
          {erro ?? 'Nada para mostrar agora.'}
        </p>
      </Tela>
    )
  }

  // `RF-114`: ausente ⇒ editável (servidor antigo não manda o campo).
  const editavel = respostas.editavel !== false

  return (
    <Tela
      titulo="Minhas respostas"
      voltar={voltar}
      largura="ampla"
      acoes={<Botao onClick={voltar}>Voltar ao início</Botao>}
      lateral={<MenuDasPartes partes={partes} ativa={ativa.bloco} escolher={escolherBloco} />}
    >
      {editavel ? (
        <p className="lead">
          Tudo o que você já respondeu fica aqui. Mudou de ideia, ou errou um número? É só
          editar.
        </p>
      ) : (
        <section className="cartao" aria-label="Plano em conferência">
          <strong>
            {respostas.pode_retomar_edicao
              ? 'Seu plano está em conferência.'
              : 'Estamos montando o seu plano.'}
          </strong>
          <p className="nota">
            {respostas.pode_retomar_edicao
              ? 'Por isso as respostas estão só para leitura: a equipe confere exatamente o que você enviou. Se perceber algo errado, você pode retirar o plano da conferência e editar.'
              : 'Assim que o cálculo terminar, o plano segue para a conferência. Até lá, as respostas ficam só para leitura.'}
          </p>

          {respostas.pode_retomar_edicao && !confirmando && (
            <Botao variante="discreto" className="self-start" onClick={() => setConfirmando(true)}>
              Quero editar minhas respostas
            </Botao>
          )}

          {respostas.pode_retomar_edicao && confirmando && (
            <div className="flex flex-col gap-2" role="group" aria-label="Confirmar a retirada">
              <p>
                <strong>
                  Seu plano sai da conferência. Quando você enviar de novo, ele volta para a
                  fila.
                </strong>
              </p>
              <div className="flex flex-wrap gap-2">
                <Botao onClick={() => void retirarDaConferencia()} disabled={retirando}>
                  Retirar o plano e editar
                </Botao>
                <Botao
                  variante="discreto"
                  onClick={() => setConfirmando(false)}
                  disabled={retirando}
                >
                  Cancelar
                </Botao>
              </div>
            </div>
          )}

          {erroRetirada && (
            <p role="alert" className="aviso-erro">
              {erroRetirada}
            </p>
          )}
        </section>
      )}

      <PainelDaParte
        parte={ativa}
        titulo={tituloDaParte}
        editar={editavel ? (id, item) => editar(id, item, ativa.bloco) : undefined}
      />
    </Tela>
  )
}
