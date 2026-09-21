/**
 * Coleta — uma pergunta por vez (`RF-45`, `RF-50`, `RF-63`, `RF-69`, `RF-70`).
 *
 * **Esta tela nunca decide qual pergunta aparece.** Ela pede
 * `GET /caso/{id}/pergunta` e desenha o que vier; quando a condicional de
 * uma pergunta é falsa, quem avança até a próxima é o servidor (`RF-52`).
 * Não existe `condicao_exibicao` no tipo `Pergunta` — não há o que avaliar
 * aqui, por construção.
 *
 * **É a única tela com `mostrarTitulo={false}`.** O título visível é o
 * enunciado, que o `<legend>` de `CampoPergunta` já desenha; a casca emite o
 * `<h1 className="sr-only">` para que `AC-84` tenha o que focar. Dois títulos
 * na tela fariam o leitor de tela anunciar a pergunta duas vezes.
 *
 * ## O defeito que T-160 corrigiu
 *
 * A rota `#pergunta/{ID}/{item_id}` existia desde `T-149` — `hashParaRota` já
 * a decodificava, `TelaInicio` já a emitia com o alvo da retomada — e **esta
 * tela ignorava os dois parâmetros**: `carregar` chamava sempre
 * `obterProximaPergunta`. O efeito era silencioso e exatamente o do relato do
 * usuário (*"as perguntas que eu respondi não consigo editar"*): quem pedia
 * uma pergunta específica recebia a próxima pendente, com a URL dizendo outra
 * coisa. O backend nunca teve essa limitação — `GET
 * /caso/{id}/pergunta/{ID_PERGUNTA}` devolve qualquer pergunta com
 * `valor_atual` preenchido desde `T-123`.
 *
 * Agora `idPergunta` presente ⇒ `obterPergunta`; ausente ⇒ a próxima, como
 * antes. É a mesma tela nos dois casos, e é isso que `RF-69` exige: corrigir
 * usa a MESMA rota de gravação da resposta original, sem segunda via.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import CampoPergunta from '../componentes/CampoPergunta'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import {
  gravarResposta,
  obterPergunta,
  obterProximaPergunta,
  obterRespostasDoCaso,
} from '../services/api'
import type { Pergunta } from '../tipos'

interface TelaPerguntaProps {
  casoId: string
  voltar?: () => void
  onColetaCompleta: () => void
  /**
   * A pergunta a abrir, quando a rota a nomeia — `RF-69`, `AC-102`.
   *
   * Ausente = a próxima pendente, que é a coleta normal (`RF-45`). Presente =
   * correção: a pergunta abre com o valor anterior já preenchido, porque é
   * o servidor que o devolve em `valor_atual`/`valores_marcados`.
   */
  idPergunta?: string
  itemId?: string
  /**
   * Para onde ir depois de gravar uma CORREÇÃO — `AC-103`.
   *
   * Só é chamado quando a tela foi aberta com `idPergunta`: quem corrigiu uma
   * resposta veio da revisão e quer voltar a ela, não emendar na coleta. Na
   * coleta normal (`idPergunta` ausente) a tela segue para a próxima pergunta,
   * como sempre.
   */
  aoCorrigir?: () => void
  /** Abre outra pergunta — o caminho para a anterior (`RF-70`, `AC-105`). */
  abrirPergunta?: (idPergunta: string, itemId: string | null) => void
}

/**
 * A pergunta anterior já respondida — `RF-70`, `AC-105`.
 *
 * **Por que o payload de `/respostas` e não uma ordem inventada aqui.** O
 * cliente não conhece o conjunto de perguntas exibíveis (`RF-45`): reconstruir
 * "qual vem antes" a partir do `ID` seria o cliente reimplementando a ordem do
 * questionário, com um grafo condicional que ele não tem. `/respostas` já
 * devolve, na ordem dos registros e por parte, exatamente as perguntas que o
 * aluno **respondeu** — que é o conjunto que `AC-105` pede ("pergunta anterior
 * já respondida"), e vem do servidor.
 *
 * A alternativa seria um histórico de navegação no cliente. Foi recusada: ela
 * mostra por onde o aluno PASSOU nesta sessão, não o que ele respondeu, e
 * `RF-10` promete retomada entre aparelhos — num celular aberto do zero o
 * histórico estaria vazio e o caminho para trás sumiria sem motivo visível.
 *
 * Devolve `null` quando a pergunta atual é a primeira respondida, ou quando
 * ainda não há nenhuma: é o segundo pé de `AC-105` — na primeira pergunta não
 * se oferece "anterior".
 */
interface Anterior {
  ID: string
  item_id: string | null
}

function anteriorNaLista(
  linhas: readonly Anterior[],
  atual: { ID: string; item_id: string | null } | null,
): Anterior | null {
  if (linhas.length === 0) return null
  if (atual === null) return linhas[linhas.length - 1] ?? null

  const indice = linhas.findIndex(
    (linha) => linha.ID === atual.ID && linha.item_id === atual.item_id,
  )
  // A pergunta atual não está entre as respondidas (é a próxima pendente): a
  // anterior é a última que o aluno respondeu.
  if (indice === -1) return linhas[linhas.length - 1] ?? null
  // Está entre elas e é a PRIMEIRA — `AC-105`: não há anterior a oferecer.
  return indice === 0 ? null : (linhas[indice - 1] ?? null)
}

/**
 * O rótulo do item a partir do `item_id` — `D003` → `Dívida 3`.
 *
 * O `item_id` é o identificador do servidor, e mostrá-lo cru ("D003") pede ao
 * aluno que aprenda a nossa notação. A conversão é de APRESENTAÇÃO: o valor
 * que viaja em qualquer requisição continua sendo o `item_id` intacto.
 *
 * Os prefixos são os sete de `collection/repeticao.py::PREFIXO_POR_ESCOPO`, e
 * **não são todos de uma letra** (`DESP`, `REND`, `NM`). Daí o `match` sobre o
 * identificador inteiro em vez de fatiar o primeiro caractere: com o fatiamento,
 * `DESP002` viraria "Dívida 0" — um rótulo errado com cara de certo.
 *
 * Prefixo desconhecido devolve o `item_id` como está. Mostrar o identificador
 * é feio; inventar o nome do item é mentir sobre o que o aluno está vendo.
 */
const ROTULO_POR_PREFIXO: Readonly<Record<string, string>> = {
  D: 'Dívida',
  V: 'Vínculo',
  M: 'Margem',
  DESP: 'Despesa',
  A: 'Ação',
  REND: 'Renda',
  NM: 'Despesa não-mensal',
}

const FORMATO_DO_ITEM = /^([A-Z]+)(\d+)$/

function rotuloDoItem(itemId: string): string {
  const partes = FORMATO_DO_ITEM.exec(itemId)
  if (!partes) return itemId
  const [, prefixo, digitos] = partes
  const rotulo = ROTULO_POR_PREFIXO[prefixo]
  // `Number` sobre dígitos só tira os zeros à esquerda (`003` → `3`) — não é
  // a conversão de dinheiro que `RF-13` proíbe.
  return rotulo ? `${rotulo} ${Number(digitos)}` : itemId
}

/**
 * O localizador do `.top` — "Dívida 3 · pergunta 4 de 12" (`RF-63`, `AC-92`).
 *
 * `posicao`/`total_na_ficha` só existem dentro de ficha repetível; fora dela o
 * servidor manda `null` e o localizador cai no par bloco/pendências, que é o
 * único "onde estou" honesto quando não há ficha para contar.
 */
function localizador(pergunta: Pergunta, pendencias: number): string {
  if (pergunta.posicao !== null && pergunta.total_na_ficha !== null) {
    const item = pergunta.item_id ? `${rotuloDoItem(pergunta.item_id)} · ` : ''
    return `${item}pergunta ${pergunta.posicao} de ${pergunta.total_na_ficha}`
  }
  return `Bloco ${pergunta.bloco} · ${pendencias} pendência${pendencias === 1 ? '' : 's'}`
}

/** O avanço dentro da ficha, em pontos percentuais. `null` fora de ficha. */
function percentualDaFicha(pergunta: Pergunta): number | null {
  const { posicao, total_na_ficha: total } = pergunta
  if (posicao === null || total === null || total <= 0) return null
  return Math.min(100, Math.round((posicao / total) * 100))
}

export default function TelaPergunta({
  casoId,
  voltar,
  onColetaCompleta,
  idPergunta,
  itemId,
  aoCorrigir,
  abrirPergunta,
}: TelaPerguntaProps) {
  const [pergunta, setPergunta] = useState<Pergunta | null>(null)
  const [pendencias, setPendencias] = useState(0)
  const [valor, setValor] = useState<string | string[]>('')
  const [naoSei, setNaoSei] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [gravando, setGravando] = useState(false)
  /** As respondidas, em ordem — a fonte do caminho para trás (`RF-70`). */
  const [respondidas, setRespondidas] = useState<readonly Anterior[]>([])

  /**
   * **A correção é modo, não tela nova** (`RF-69`). Uma segunda tela de
   * edição seria uma segunda montagem de campo e uma segunda chamada de
   * gravação — duas oportunidades de divergir da coleta sobre a mesma
   * pergunta.
   *
   * **Quem manda é `aoCorrigir`, não `idPergunta`.** A tentação era deduzir o
   * modo do parâmetro da rota, mas `#pergunta/{ID}` também o traz desde
   * `T-149` — é a RETOMADA, em que o servidor nomeia onde o aluno parou e
   * gravar segue para a próxima pergunta. Deduzir pelo `idPergunta` mandaria
   * quem clicou em "Continuar de onde você parou" para a lista de respostas
   * depois de responder uma única pergunta. Quem sabe de onde o aluno veio é
   * quem o trouxe: `App.tsx`.
   */
  const corrigindo = aoCorrigir !== undefined

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      // `idPergunta` presente ⇒ ESTA pergunta, com o valor anterior que o
      // servidor devolve (`AC-102`). Ausente ⇒ a próxima pendente, que é a
      // coleta de sempre e continua decidida pelo servidor (`RF-45`).
      const dados = idPergunta
        ? await obterPergunta(casoId, idPergunta, itemId)
        : await obterProximaPergunta(casoId)
      if (!dados.pergunta) {
        onColetaCompleta()
        return
      }
      setPergunta(dados.pergunta)
      setPendencias(dados.total_pendencias ?? 0)
      // Reabre com o valor já respondido, quando houver (`AC-01`, `AC-102`).
      setValor(dados.pergunta.valores_marcados.length > 0
        ? dados.pergunta.valores_marcados
        : (dados.pergunta.valor_atual as string) ?? '')
      setNaoSei(dados.pergunta.respondida_como_nao_sei)
    } catch {
      setErro('Não foi possível carregar a pergunta.')
    } finally {
      setCarregando(false)
    }
  }, [casoId, idPergunta, itemId, onColetaCompleta])

  /**
   * A PRÓXIMA pendente, ignorando o `idPergunta` da rota — `T-175`.
   *
   * **Por que não dá para reusar `carregar`.** Ela relê o que a ROTA pede, e
   * na retomada a rota carrega um `idPergunta` (o Início repassa o
   * `ID_PERGUNTA` que `/inicio` devolveu). Depois de gravar, reler a rota
   * significa reler a MESMA pergunta — o aluno responde, grava, e a pergunta
   * volta, para sempre. A coleta não avançava pelo caminho que o produto
   * oferece.
   *
   * Quem decide qual é a próxima continua sendo o servidor (`RF-45`); esta
   * função só deixa de impor a pergunta da rota depois que ela já foi
   * respondida.
   */
  const carregarProxima = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const dados = await obterProximaPergunta(casoId)
      if (!dados.pergunta) {
        onColetaCompleta()
        return
      }
      setPergunta(dados.pergunta)
      setPendencias(dados.total_pendencias ?? 0)
      setValor(
        dados.pergunta.valores_marcados.length > 0
          ? dados.pergunta.valores_marcados
          : ((dados.pergunta.valor_atual as string) ?? ''),
      )
      setNaoSei(dados.pergunta.respondida_como_nao_sei)
    } catch {
      setErro('Não foi possível carregar a pergunta.')
    } finally {
      setCarregando(false)
    }
  }, [casoId, onColetaCompleta])

  useEffect(() => {
    void carregar()
  }, [carregar])

  /**
   * Busca a ordem das respondidas — `RF-70`.
   *
   * Falha aqui **degrada, não quebra**: sem a lista o caminho para trás
   * simplesmente não é oferecido, e a coleta segue. Um erro de carregamento de
   * um atalho não pode impedir o aluno de responder a pergunta que está na
   * tela.
   */
  useEffect(() => {
    if (!abrirPergunta) return
    let ativo = true
    obterRespostasDoCaso(casoId)
      .then((dados) => {
        if (!ativo) return
        setRespondidas(
          dados.partes.flatMap((parte) =>
            parte.respondidas.map((linha) => ({ ID: linha.ID, item_id: linha.item_id })),
          ),
        )
      })
      .catch(() => undefined)
    return () => {
      ativo = false
    }
  }, [casoId, abrirPergunta, idPergunta, itemId])

  async function aoResponder() {
    if (!pergunta) return
    setGravando(true)
    setErro(null)
    try {
      await gravarResposta(casoId, {
        idPergunta: pergunta.ID,
        valor: naoSei ? undefined : valor,
        itemId: pergunta.item_id,
        naoSei,
      })
      // `AC-103`: depois de corrigir, o aluno volta de onde veio — a revisão.
      // Emendar na próxima pergunta pendente o mandaria para o meio da coleta
      // sem ter pedido isso.
      if (corrigindo && aoCorrigir) {
        aoCorrigir()
        return
      }
      // `T-175`: a PRÓXIMA pendente, nunca a mesma de novo. `carregar()`
      // releria o `idPergunta` da rota — que na retomada ainda aponta para
      // a pergunta que acabou de ser respondida.
      await carregarProxima()
    } catch (falha) {
      // `AC-104`: a recusa do servidor (`EC-01`/`EC-02`) chega nomeada —
      // mostramos o que ele disse, nunca uma mensagem inventada aqui.
      //
      // **E não recarregamos.** O valor anterior continua gravado no servidor
      // (ele recusou a escrita inteira, não gravou pela metade), e o que o
      // aluno digitou continua no campo para ele corrigir. Um `carregar()`
      // aqui apagaria a digitação dele em cima de um erro que foi do valor
      // novo, não do antigo.
      setErro(falha instanceof Error ? falha.message : 'Não foi possível salvar.')
    } finally {
      setGravando(false)
    }
  }

  const anterior = anteriorNaLista(
    respondidas,
    pergunta ? { ID: pergunta.ID, item_id: pergunta.item_id } : null,
  )

  if (carregando) {
    return (
      <Tela titulo="Sua coleta" voltar={voltar}>
        <Esqueleto forma="pergunta" anuncio="Carregando a pergunta" />
      </Tela>
    )
  }

  if (!pergunta) {
    return (
      <Tela titulo="Sua coleta" voltar={voltar}>
        <p role="alert" className="aviso-erro">
          {erro ?? 'Nada para responder agora.'}
        </p>
      </Tela>
    )
  }

  const pct = percentualDaFicha(pergunta)

  return (
    <Tela
      // O título é o enunciado: `AC-84` refoca o `<h1>` a cada pergunta nova.
      titulo={pergunta.enunciado}
      // **A `chave` é o que faz `AC-84` valer nas fichas repetíveis.** O
      // enunciado sozinho não distingue os itens: `B5.A01` ("Para quem você
      // deve nessa operação?") não tem interpolação, então passar de `D001`
      // para `D002` mantém o mesmo título. Sem a chave, o foco não se move e
      // quem usa leitor de tela responde a dívida 2 ouvindo a pergunta da
      // dívida 1 — na ficha, que é o caminho mais longo da coleta.
      chave={`${pergunta.ID}/${pergunta.item_id ?? ''}`}
      mostrarTitulo={false}
      voltar={voltar}
      onde={localizador(pergunta, pendencias)}
      acoes={
        <>
          <Botao onClick={() => void aoResponder()} disabled={gravando}>
            {gravando ? 'Salvando…' : corrigindo ? 'Salvar a correção' : 'Continuar'}
          </Botao>
          {/* `AC-105`: o caminho para a pergunta anterior já respondida.
              Errar a anterior e perceber na seguinte é o caso mais comum de
              correção, e mandar o aluno à lista inteira para isso é
              desproporcional. Na primeira pergunta `anterior` é `null` e o
              botão não existe — não basta desabilitá-lo, porque um botão
              apagado ainda promete um caminho que não há. */}
          {abrirPergunta && anterior && (
            <Botao
              variante="discreto"
              onClick={() => abrirPergunta(anterior.ID, anterior.item_id)}
            >
              ‹ Pergunta anterior
            </Botao>
          )}
        </>
      }
    >
      {/* A barra mede o avanço DENTRO da ficha. Fora de ficha não há
          denominador — e uma barra sem denominador estimaria o que falta,
          que é justamente o que o cliente não sabe (`RF-45`). */}
      {pct !== null && (
        <div className="bar" aria-hidden="true">
          <i style={{ width: `${pct}%` }} />
        </div>
      )}

      <CampoPergunta
        pergunta={pergunta}
        valor={valor}
        naoSei={naoSei}
        onValor={setValor}
        onNaoSei={setNaoSei}
      />

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}
    </Tela>
  )
}
