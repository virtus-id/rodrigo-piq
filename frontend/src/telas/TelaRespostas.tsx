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
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import { obterRespostasDoCaso } from '../services/api'
import type { ParteDasRespostas, RespostaDada, RespostasDoCaso } from '../tipos'

interface TelaRespostasProps {
  casoId: string
  voltar: () => void
  /** Abre a pergunta para correção — `RF-69`, `AC-102`. */
  editar: (idPergunta: string, itemId: string | null) => void
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
  return resposta.valores.join(', ')
}

/**
 * "N de M respondidas" — a contagem de uma parte.
 *
 * `total_de_perguntas` é o número de REGISTROS do bloco, e numa parte com
 * ficha repetível o número de respostas pode passar dele (36 perguntas × 3
 * dívidas). Não é erro de contagem: são respostas diferentes à mesma pergunta,
 * e juntá-las esconderia qual valor é de qual dívida. Por isso a frase não
 * promete proporção — ela informa duas quantidades reais.
 */
function contagemDaParte(parte: ParteDasRespostas): string {
  const dadas = parte.respondidas.length
  const plural = dadas === 1 ? 'resposta' : 'respostas'
  return `${dadas} ${plural} de ${parte.total_de_perguntas} perguntas`
}

/**
 * Uma parte da coleta — `<details>` por parte, com a primeira aberta.
 *
 * **`<details>` e não um acordeão próprio**: o elemento nativo já é navegável
 * por teclado (Tab alcança o `<summary>`, Enter/Espaço abre), já anuncia
 * estado a leitor de tela, e funciona sem JavaScript. Escrever um acordeão à
 * mão significaria reimplementar `aria-expanded`, foco e teclas — e errar
 * algum.
 *
 * **`AC-95` não é contrariado.** Aquele critério proíbe a TRILHA dentro de
 * `<details>`: o mapa da jornada não pode ser escondido. Aqui o que fecha é
 * uma lista de respostas dadas, que é consulta sob demanda; o que precisa
 * estar sempre visível — quais são as cinco partes e quantas respostas tem
 * cada uma — está no `<summary>`, que nunca fecha.
 */
function ParteDaRevisao({
  parte,
  comecaAberta,
  editar,
}: {
  parte: ParteDasRespostas
  /**
   * Abre no primeiro render — `defaultOpen`, não `open`.
   *
   * **`open={...}` prendia o elemento.** Com o atributo controlado e sem
   * handler de `onToggle`, o React o reimpõe a cada render: clicar no
   * `<summary>` abria e o próximo render fechava de volta. O aluno via a
   * primeira parte aberta e **nenhuma outra abria** — a tela existia para ele
   * reler tudo, e só deixava reler um quinto.
   *
   * `defaultOpen` entrega o elemento ao navegador: ele guarda o estado, o
   * teclado funciona (Tab no `<summary>`, Enter/Espaço), e o React não
   * interfere. Era o uso certo desde o começo — `<details>` foi escolhido
   * justamente por ser nativo.
   */
  comecaAberta: boolean
  editar: (idPergunta: string, itemId: string | null) => void
}) {
  return (
    <details
      className="cartao"
      // `ref` em vez de `open`: o atributo é posto UMA vez, no nó real, e
      // depois o navegador é dono dele. Com `open` no JSX — mesmo
      // condicional — o React o reimpõe a cada render e o clique no
      // `<summary>` não persiste.
      ref={(no) => {
        if (no && comecaAberta && !no.dataset.iniciada) {
          no.open = true
          no.dataset.iniciada = '1'
        }
      }}
    >
      <summary className="cursor-pointer">
        <span className="font-bold">{parte.rotulo}</span>
        <small className="block text-muted">{contagemDaParte(parte)}</small>
      </summary>

      {parte.respondidas.length === 0 ? (
        // `AC-101`: a parte vazia DIZ que está vazia. Uma lista em branco
        // sugeriria erro de carregamento, e sumir da tela faria o aluno
        // procurar onde a parte foi parar.
        <p className="nota">Você ainda não respondeu nada desta parte.</p>
      ) : (
        <ul className="lista list-none p-0">
          {parte.respondidas.map((resposta) => (
            <li
              // `ID` sozinho não é único: numa ficha repetível a mesma
              // pergunta rende uma linha por dívida. O par com `item_id` é o
              // que identifica a resposta.
              key={`${resposta.ID}/${resposta.item_id ?? ''}`}
              className="item flex-col items-stretch gap-2"
            >
              <div>{resposta.enunciado}</div>
              <strong className="break-words">{textoDaResposta(resposta)}</strong>
              <Botao
                variante="discreto"
                className="self-start"
                onClick={() => editar(resposta.ID, resposta.item_id)}
              >
                Editar
              </Botao>
            </li>
          ))}
        </ul>
      )}
    </details>
  )
}

export default function TelaRespostas({ casoId, voltar, editar }: TelaRespostasProps) {
  const [respostas, setRespostas] = useState<RespostasDoCaso | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)

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

  if (carregando) {
    return (
      <Tela titulo="Minhas respostas" voltar={voltar}>
        <Esqueleto forma="lista" anuncio="Carregando suas respostas" itens={4} />
      </Tela>
    )
  }

  if (!respostas) {
    return (
      <Tela titulo="Minhas respostas" voltar={voltar}>
        <p role="alert" className="aviso-erro">
          {erro ?? 'Nada para mostrar agora.'}
        </p>
      </Tela>
    )
  }

  // A primeira parte que TEM resposta abre por padrão; se nenhuma tiver, abre
  // a primeira. Abrir todas faria a tela nascer com cem linhas, e abrir
  // nenhuma daria ao aluno cinco caixas fechadas onde ele veio ler algo.
  const indiceAberto = Math.max(
    0,
    respostas.partes.findIndex((parte) => parte.respondidas.length > 0),
  )

  return (
    <Tela
      titulo="Minhas respostas"
      voltar={voltar}
      acoes={<Botao onClick={voltar}>Voltar ao início</Botao>}
    >
      <p className="lead">
        Tudo o que você já respondeu fica aqui. Mudou de ideia, ou errou um número? É só
        editar.
      </p>

      <div className="lista">
        {respostas.partes.map((parte, indice) => (
          <ParteDaRevisao
            key={parte.bloco}
            parte={parte}
            comecaAberta={indice === indiceAberto}
            editar={editar}
          />
        ))}
      </div>
    </Tela>
  )
}
