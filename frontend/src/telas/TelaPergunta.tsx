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
import CamposDoItem, {
  CampoNome,
  chaveDa,
  emBranco,
  type EstadoDaFilha,
  filhasAbertas,
  gravarEmSequencia,
  MENSAGEM_CAMPO_EM_BRANCO,
  MENSAGEM_FALTAM_CAMPOS,
  MENSAGEM_SEM_NOME,
  valorInicial,
} from '../componentes/CamposDoItem'
import Esqueleto from '../componentes/Esqueleto'
import PainelFotografia from '../componentes/PainelFotografia'
import Tela from '../componentes/Tela'
import TrilhaDaColeta from '../componentes/TrilhaDaColeta'
import {
  concluirItem,
  ErroHttp,
  gravarResposta,
  nomearFicha,
  obterPergunta,
  obterProximaPergunta,
} from '../services/api'
import type { ConfirmacaoDeResposta, FichaNova, Pergunta } from '../tipos'
import { avisoDeUmPorVez, TITULOS_POR_ESCOPO } from './TelaFichas'

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
  /**
   * Abre a lista de fichas que a resposta acabou de abrir (`T-212`) — ex.:
   * "Sim" em `B3.03`. Os escopos vêm do servidor, na ordem do registro.
   */
  onAbrirFichas?: (escopos: string[]) => void
  /**
   * A correção de uma linha da fotografia do mês (`RF-80`, T-228) — pela rota
   * de correção de `RF-69`, nunca uma segunda via de gravação.
   */
  abrirCorrecao?: (idPergunta: string, itemId: string) => void
  /**
   * `T-314`: a pergunta de ficha curta abre o formulário do item. Devolve
   * se abriu — quem sabe quais fichas são curtas é `App.tsx`.
   */
  abrirFormulario?: (pergunta: Pergunta) => boolean
}

/**
 * A pergunta anterior — `RF-70`, `AC-105`, `T-309`.
 *
 * Vem pronta do servidor em `pergunta.anterior`: a respondida logo antes
 * desta **no percurso** (ficha item a item, condicionais avaliadas). Antes a
 * tela montava a ordem a partir de `/respostas`, que é a ordem dos registros
 * agrupada por parte — numa ficha com dois itens "anterior" saltava para o
 * outro item. `null` na primeira pergunta: não se oferece "anterior".
 */

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
  // `T-206`: o total é GLOBAL (todas as obrigatórias em branco), não do
  // bloco — o rótulo diz o que o número conta (`RF-65`, `AC-96`).
  const obrigatorias = pendencias === 1 ? 'obrigatória restante' : 'obrigatórias restantes'
  return `Bloco ${pergunta.bloco} · no total, ${pendencias} ${obrigatorias}`
}

// `T-319`: os campos da ficha curta moraram aqui até a ficha nova precisar
// deles também; re-exportados para quem já os importava.
export { chaveDa, type EstadoDaFilha, filhasAbertas, valorInicial }

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
  onAbrirFichas,
  abrirCorrecao,
  abrirFormulario,
}: TelaPerguntaProps) {
  const [pergunta, setPergunta] = useState<Pergunta | null>(null)
  const [pendencias, setPendencias] = useState(0)
  const [valor, setValor] = useState<string | string[]>('')
  const [naoSei, setNaoSei] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [gravando, setGravando] = useState(false)
  /**
   * Gravada com aviso (`T-240`): a resposta já está salva, e a tela PARA na
   * mesma pergunta para anunciar o aviso junto do campo. O próximo
   * "Continuar" segue com esta confirmação, sem gravar de novo — a menos
   * que o aluno mude a resposta.
   */
  const [confirmacaoComAviso, setConfirmacaoComAviso] = useState<ConfirmacaoDeResposta | null>(
    null,
  )
  /**
   * `T-307`: o que o aluno preencheu nas perguntas da thread, pela chave.
   * Trocar de opção esconde as filhas e elas não são enviadas; voltar à
   * opção mostra de novo o que tinha sido digitado.
   */
  const [filhas, setFilhas] = useState<Record<string, EstadoDaFilha>>({})
  /**
   * `T-319` (`RF-106`): a ficha curta que a opção abre, na mesma tela. Os
   * campos dela ficam em `filhas` (a chave traz o `item_id` provisório); o
   * nome é o da despesa não listada; `itemNovo`, o item que a mãe criou —
   * guardado para que reenviar depois de um erro grave no mesmo item.
   */
  const [nomeNovo, setNomeNovo] = useState('')
  const [erroNomeNovo, setErroNomeNovo] = useState<string | null>(null)
  const [itemNovo, setItemNovo] = useState<string | null>(null)

  function estadoDa(filha: Pergunta): EstadoDaFilha {
    return (
      filhas[chaveDa(filha)] ?? {
        valor: valorInicial(filha),
        naoSei: filha.respondida_como_nao_sei,
        erro: null,
        aviso: null,
      }
    )
  }

  function mudarFilha(filha: Pergunta, mudanca: Partial<EstadoDaFilha>) {
    // Mudou a resposta: o aviso anterior não vale mais — grava de novo.
    setConfirmacaoComAviso(null)
    setFilhas((atual) => ({
      ...atual,
      // `T-325`: base `atual`, não o `filhas` da renderização anterior.
      [chaveDa(filha)]: {
        ...(atual[chaveDa(filha)] ?? estadoDa(filha)),
        aviso: null,
        erro: null,
        ...mudanca,
      },
    }))
  }

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
        : await obterProximaPergunta(casoId, itemId)
      if (!dados.pergunta) {
        onColetaCompleta()
        return
      }
      if (!corrigindo && abrirFormulario?.(dados.pergunta)) return
      setPergunta(dados.pergunta)
      setFilhas({})
      setNomeNovo('')
      setErroNomeNovo(null)
      setItemNovo(null)
      setPendencias(dados.total_pendencias ?? 0)
      // Reabre com o valor já respondido, quando houver (`AC-01`, `AC-102`).
      setValor(valorInicial(dados.pergunta))
      setNaoSei(dados.pergunta.respondida_como_nao_sei)
    } catch {
      setErro('Não foi possível carregar a pergunta.')
    } finally {
      setCarregando(false)
    }
  }, [casoId, idPergunta, itemId, onColetaCompleta, corrigindo, abrirFormulario])

  useEffect(() => {
    void carregar()
  }, [carregar])

  /**
   * `T-319`: a ficha nova da opção escolhida — consulta à tabela do servidor,
   * como as complementares. Não na correção: ela volta à revisão.
   */
  const escolhida = Array.isArray(valor) ? (valor[0] ?? '') : valor
  const fichaNova: FichaNova | undefined =
    pergunta && !corrigindo && !naoSei ? pergunta.ficha_nova?.[escolhida] : undefined
  const titulosDaFichaNova = fichaNova ? TITULOS_POR_ESCOPO[fichaNova.escopo] : undefined

  async function aoResponder() {
    if (!pergunta) return
    if (confirmacaoComAviso) {
      const confirmacao = confirmacaoComAviso
      setConfirmacaoComAviso(null)
      if (fichaNova && itemNovo) {
        setGravando(true)
        try {
          await concluirFichaNova(fichaNova, itemNovo, confirmacao)
        } catch (falha) {
          setErro(falha instanceof Error ? falha.message : 'Não foi possível salvar.')
        } finally {
          setGravando(false)
        }
      } else seguir(confirmacao)
      return
    }
    setErro(null)
    // `T-320`: na ficha nova, nada em branco — destaca e não grava nada.
    if (fichaNova) {
      const faltam = emBranco(fichaNova.perguntas, estadoDa)
      const semNome = fichaNova.pede_nome && !nomeNovo.trim()
      if (faltam.length || semNome) {
        setFilhas((atual) => ({
          ...atual,
          ...Object.fromEntries(
            faltam.map((p) => [chaveDa(p), { ...estadoDa(p), erro: MENSAGEM_CAMPO_EM_BRANCO }]),
          ),
        }))
        setErroNomeNovo(semNome ? MENSAGEM_SEM_NOME : null)
        setErro(MENSAGEM_FALTAM_CAMPOS)
        return
      }
    }
    setGravando(true)
    try {
      const daMae = await gravarResposta(casoId, {
        idPergunta: pergunta.ID,
        valor: naoSei ? undefined : valor,
        itemId: pergunta.item_id,
        naoSei,
      })
      // `T-307` (RF-99): depois da mãe, as filhas abertas, uma a uma, pela
      // MESMA rota (`RF-69`) — a mãe gravada primeiro é o que abre cada
      // filha no servidor. Filha recusada mostra o erro junto dela; a mãe e
      // as anteriores já estão gravadas, e reenviar regrava igual.
      let confirmacao = daMae
      const avisos = [...(daMae.avisos ?? [])]
      const abrirFichas = [...(daMae.abrir_fichas ?? [])]
      const estados: Record<string, EstadoDaFilha> = {}
      for (const filha of filhasAbertas(pergunta, valor, naoSei)) {
        const estado: EstadoDaFilha = { ...estadoDa(filha), erro: null, aviso: null }
        estados[chaveDa(filha)] = estado
        try {
          confirmacao = await gravarResposta(casoId, {
            idPergunta: filha.ID,
            valor: estado.naoSei ? undefined : estado.valor,
            itemId: filha.item_id,
            naoSei: estado.naoSei,
          })
        } catch (falha) {
          estado.erro = falha instanceof Error ? falha.message : 'Não foi possível salvar.'
          setFilhas((atual) => ({ ...atual, ...estados }))
          return
        }
        const avisosDaFilha = confirmacao.avisos ?? []
        if (avisosDaFilha.length) {
          estado.aviso = avisosDaFilha.map((aviso) => aviso.mensagem).join(' ')
        }
        avisos.push(...avisosDaFilha)
        abrirFichas.push(...(confirmacao.abrir_fichas ?? []))
      }
      setFilhas((atual) => ({ ...atual, ...estados }))
      confirmacao = {
        ...confirmacao,
        avisos,
        abrir_fichas: [...new Set(abrirFichas)],
      }
      if (fichaNova) {
        await salvarFichaNova(fichaNova, confirmacao)
        return
      }
      // `T-240`: o aviso vai para o canal que o campo já anuncia
      // (`role="status"` ligado por `aria-describedby`, em `CampoPergunta`).
      // Nenhuma regra aqui: o texto e a decisão de avisar são do servidor.
      if (avisos.length) {
        if (daMae.avisos?.length) {
          setPergunta({
            ...pergunta,
            aviso: daMae.avisos.map((aviso) => aviso.mensagem).join(' '),
          })
        }
        setConfirmacaoComAviso(confirmacao)
        return
      }
      seguir(confirmacao)
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

  /**
   * `T-319` (`RF-106`): a mãe gravada criou o item (`T-311`/`T-316`) e a
   * `proxima` do servidor aponta a primeira pergunta dele — é nesse
   * `item_id` que os campos são gravados, na ordem, e o item é concluído.
   */
  async function salvarFichaNova(ficha: FichaNova, confirmacao: ConfirmacaoDeResposta) {
    const criada = confirmacao.proxima.pergunta
    const item =
      itemNovo ?? (criada?.escopo_repeticao === ficha.escopo ? criada.item_id : null)
    if (!item) throw new Error('Não foi possível salvar.')
    setItemNovo(item)
    let falhou = false
    if (ficha.pede_nome) {
      try {
        await nomearFicha(casoId, ficha.escopo, item, nomeNovo.trim())
        setErroNomeNovo(null)
      } catch (falha) {
        setErroNomeNovo(falha instanceof Error ? falha.message : 'Não foi possível salvar.')
        falhou = true
      }
    }
    const gravacao = await gravarEmSequencia(casoId, ficha.perguntas, estadoDa, item)
    setFilhas((atual) => ({ ...atual, ...gravacao.estados }))
    if (falhou || gravacao.falhou) return
    if (gravacao.avisou) {
      setConfirmacaoComAviso(confirmacao)
      return
    }
    await concluirFichaNova(ficha, item, confirmacao)
  }

  /**
   * Concluído (`T-320`), a lista do escopo abre com "+ Adicionar outro(a)"
   * e "Continuar" (`T-311`). Se o servidor recusar — a resposta abriu uma
   * pergunta que não estava na tela —, o formulário do item a mostra.
   */
  async function concluirFichaNova(
    ficha: FichaNova,
    item: string,
    confirmacao: ConfirmacaoDeResposta,
  ) {
    try {
      await concluirItem(casoId, ficha.escopo, item)
    } catch (falha) {
      const primeira = ficha.perguntas[0]
      if (
        falha instanceof ErroHttp &&
        falha.status === 400 &&
        primeira &&
        abrirFormulario?.({ ...primeira, item_id: item })
      ) {
        return
      }
      throw falha
    }
    if (onAbrirFichas) {
      onAbrirFichas([ficha.escopo, ...confirmacao.abrir_fichas.filter((e) => e !== ficha.escopo)])
    } else seguir(confirmacao)
  }

  function seguir(confirmacao: ConfirmacaoDeResposta) {
    // `AC-103`: depois de corrigir, o aluno volta de onde veio — a revisão.
    // Emendar na próxima pergunta pendente o mandaria para o meio da coleta
    // sem ter pedido isso.
    if (corrigindo && aoCorrigir) {
      aoCorrigir()
      return
    }
    // `T-212`: sem ficha criada, o servidor não tem pergunta daquele
    // escopo a oferecer — o aluno vai à lista criar a primeira.
    if (onAbrirFichas && confirmacao.abrir_fichas.length) {
      onAbrirFichas(confirmacao.abrir_fichas)
      return
    }
    // `T-193`: a PRÓXIMA pendente (`T-175`: nunca a mesma de novo) já veio
    // dentro da confirmação de gravação — o servidor já sabia qual era no
    // mesmo instante em que confirmou o `POST`. Sem isto, uma segunda
    // requisição (`GET /pergunta`, com seu próprio check de sessão) pedia
    // de volta algo que o servidor tinha acabado de calcular. Quem decide
    // continua sendo só o servidor (`RF-45`) — isto só para de pedir duas
    // vezes.
    if (!confirmacao.proxima.pergunta) {
      onColetaCompleta()
      return
    }
    const proxima = confirmacao.proxima.pergunta
    if (abrirFormulario?.(proxima)) return
    setPergunta(proxima)
    setFilhas({})
    setNomeNovo('')
    setErroNomeNovo(null)
    setItemNovo(null)
    setPendencias(confirmacao.total_pendencias)
    setValor(valorInicial(proxima))
    setNaoSei(proxima.respondida_como_nao_sei)
  }

  const anterior = pergunta?.anterior ?? null
  const seguinte = pergunta?.seguinte ?? null

  /**
   * `T-318`: "Pergunta seguinte ›" só navega — gravar é do "Continuar". Com
   * uma alteração não salva, pergunta antes de descartá-la, em vez de
   * gravar por baixo (o aluno pode só ter mexido sem querer).
   */
  function irParaSeguinte() {
    if (!pergunta || !seguinte || !abrirPergunta) return
    const alterou =
      !confirmacaoComAviso &&
      (JSON.stringify(valor) !== JSON.stringify(valorInicial(pergunta)) ||
        naoSei !== pergunta.respondida_como_nao_sei ||
        Object.keys(filhas).length > 0 ||
        nomeNovo !== '')
    if (
      alterou &&
      !window.confirm(
        'Você mudou a resposta e ainda não salvou. Ir para a pergunta seguinte sem salvar?',
      )
    ) {
      return
    }
    abrirPergunta(seguinte.ID, seguinte.item_id)
  }
  // `T-308`: na correção o "voltar" leva à revisão, não ao Início.
  const rotuloVoltar = corrigindo ? '‹ Voltar' : undefined

  if (carregando) {
    return (
      <Tela titulo="Sua coleta" voltar={voltar} rotuloVoltar={rotuloVoltar}>
        <Esqueleto forma="pergunta" anuncio="Carregando a pergunta" />
      </Tela>
    )
  }

  if (!pergunta) {
    return (
      <Tela titulo="Sua coleta" voltar={voltar} rotuloVoltar={rotuloVoltar}>
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
      rotuloVoltar={rotuloVoltar}
      onde={localizador(pergunta, pendencias)}
      // `T-310` (RF-100): a trilha das cinco partes, do servidor.
      lateral={pergunta.trilha ? <TrilhaDaColeta trilha={pergunta.trilha} /> : undefined}
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
          {/* `T-318`: depois de voltar, avançar sem responder de novo. Na
              fronteira `seguinte` é `null` — ali o aluno precisa responder. */}
          {abrirPergunta && seguinte && (
            <Botao variante="discreto" onClick={irParaSeguinte}>
              Pergunta seguinte ›
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

      {/* `T-228` (RF-79): o servidor anexa o painel só à pergunta que o
          declara no registro — nenhuma decisão por `ID` aqui. */}
      {pergunta.painel && (
        <PainelFotografia painel={pergunta.painel} aoCorrigir={abrirCorrecao} />
      )}

      <CampoPergunta
        pergunta={pergunta}
        valor={valor}
        naoSei={naoSei}
        onValor={(novo) => {
          // Mudou a resposta: o aviso anterior não vale mais — grava de novo.
          setConfirmacaoComAviso(null)
          setValor(novo)
        }}
        onNaoSei={(marcado) => {
          setConfirmacaoComAviso(null)
          setNaoSei(marcado)
        }}
      />

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}

      {/* `T-307` (RF-99): a thread — as perguntas que a opção escolhida
          abre, logo abaixo, na mesma tela. A `key` refaz a entrada (e a
          transição) a cada troca de opção. */}
      {filhasAbertas(pergunta, valor, naoSei).length > 0 && (
        <div
          key={Array.isArray(valor) ? valor[0] : valor}
          role="group"
          aria-label="Perguntas abertas pela sua resposta"
          className="thread"
        >
          {filhasAbertas(pergunta, valor, naoSei).map((filha) => {
            const estado = estadoDa(filha)
            return (
              <div key={chaveDa(filha)} className="flex flex-col gap-2">
                <CampoPergunta
                  pergunta={{ ...filha, aviso: estado.aviso ?? filha.aviso }}
                  valor={estado.valor}
                  naoSei={estado.naoSei}
                  onValor={(novo) => mudarFilha(filha, { valor: novo, erro: null })}
                  onNaoSei={(marcado) => mudarFilha(filha, { naoSei: marcado, erro: null })}
                />
                {estado.erro && (
                  <p role="alert" className="aviso-erro">
                    {estado.erro}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* `T-319` (RF-106): os campos do primeiro item da ficha curta que a
          opção abre, logo abaixo — decididos pelo servidor. */}
      {fichaNova && (
        <div
          key={`ficha-${escolhida}`}
          role="group"
          aria-label="Perguntas abertas pela sua resposta"
          className="thread"
        >
          {titulosDaFichaNova && <p className="nota">{avisoDeUmPorVez(titulosDaFichaNova)}</p>}
          {fichaNova.pede_nome && (
            <CampoNome
              id="nome-ficha-nova"
              valor={nomeNovo}
              erro={erroNomeNovo}
              onMudar={(novo) => {
                setConfirmacaoComAviso(null)
                setNomeNovo(novo)
                setErroNomeNovo(null)
              }}
            />
          )}
          <CamposDoItem perguntas={fichaNova.perguntas} estadoDe={estadoDa} mudar={mudarFilha} />
        </div>
      )}
    </Tela>
  )
}
