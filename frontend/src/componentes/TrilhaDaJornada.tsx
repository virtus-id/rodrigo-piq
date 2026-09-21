/**
 * A jornada do caso em cinco etapas — `RF-64`, `AC-93`, `AC-94` (T-158).
 *
 * **Por que existe.** A tela Início respondia *"o que eu faço agora?"* com uma
 * etapa só (`RF-58`) e deixava intacta a pergunta anterior: *"onde eu estou, e
 * onde isso vai dar?"*. No primeiro uso real, o relato foi literal — *"me senti
 * perdido, sem saber o que é, qual o objetivo"*. O número "3 de 101" estava
 * correto e não informava nada: 101 do quê, rumo a quê.
 *
 * Para alguém endividado, saber que a coisa tem começo e fim não é conforto: é
 * o que separa "estou construindo um plano" de "estou preenchendo um
 * formulário sem tamanho conhecido" — e é essa segunda leitura que faz a
 * pessoa abandonar no meio.
 *
 * **A trilha fica sempre visível** (`AC-95`): não entra em `<details>`, não
 * fica atrás de botão. Esconder o mapa é o que produziu o problema.
 *
 * **Deriva do servidor, nunca do cliente** (`RF-67`, `AC-99`): a etapa em
 * curso vem de `fase`, o que falta vem de `progresso`. Nada de
 * `localStorage` — trocar de aparelho não pode mudar em que ponto da jornada
 * o aluno está (`RF-10`).
 */
import type { Fase, Inicio } from '../tipos'
import Icone from './Icone'

interface TrilhaDaJornadaProps {
  inicio: Inicio
}

/** Uma etapa da jornada, na ordem em que o aluno a percorre. */
interface EtapaDaJornada {
  /** As fases que colocam o aluno NESTA etapa. */
  fases: readonly Fase[]
  rotulo: string
  /** O que esta etapa entrega — responde "para que serve isto". */
  resumo: string
}

/**
 * As cinco etapas — espelho das cinco superfícies de interação da §1 da spec.
 *
 * `reprovado` entra em "conferência" de propósito: do ponto de vista do aluno
 * o plano continua com a equipe, e criar uma sexta etapa chamada "reprovado"
 * transformaria um passo do processo num veredito sobre ele.
 */
const ETAPAS: readonly EtapaDaJornada[] = [
  {
    fases: ['coleta'],
    rotulo: 'Suas respostas',
    resumo: 'Sobre sua renda, seus gastos e suas dívidas.',
  },
  {
    fases: [],
    rotulo: 'Cálculo do plano',
    resumo: 'O PIQ monta a ordem de quitação. Você não faz nada.',
  },
  {
    fases: ['revisao', 'reprovado'],
    rotulo: 'Conferência da equipe',
    resumo: 'Uma pessoa confere tudo antes de chegar a você.',
  },
  {
    fases: ['plano'],
    rotulo: 'Seu plano',
    resumo: 'A ordem projetada de quitação, e o que ela custa.',
  },
  {
    fases: ['acompanhamento'],
    rotulo: 'Acompanhamento',
    resumo: 'Você executa e conta como foi, mês a mês.',
  },
]

/**
 * O índice da etapa em curso — `AC-94`: exatamente uma, sempre.
 *
 * A fase `coleta` cobre tanto o início quanto a coleta dirigida (Blocos 7/8),
 * que é pós-plano. Nos dois casos o aluno está respondendo perguntas, e é isso
 * que a trilha comunica; qual bloco ele responde é assunto da tela de
 * pergunta, não do mapa.
 *
 * O "cálculo" (índice 1) nunca é fase própria — `CALCULANDO` é `revisao` em
 * `fases.py`, porque para o aluno as duas são "é com a gente". A trilha o
 * mostra como etapa porque ele **existe** na jornada e explica de onde o plano
 * vem; mas quem está calculando já aparece em "conferência", que é onde ele de
 * fato espera.
 */
/**
 * A etapa para a qual uma fase DESCONHECIDA cai — `T-171`.
 *
 * Índice 2, "Conferência da equipe", e não 0.
 *
 * **Por que o 0 estava errado.** O fallback existia para garantir que
 * nenhuma fase produza trilha sem etapa em curso (`AC-94`), e nisso
 * acertava; errava na etapa ESCOLHIDA. Uma fase que este cliente não
 * conhece vem de um servidor mais novo — e um servidor mais novo só tem
 * fases ADIANTE das cinco atuais, nunca atrás. Cair no índice 0 dizia a um
 * aluno que já tem plano que ele está de volta à primeira pergunta, com o
 * texto de acompanhamento sob o rótulo "Suas respostas".
 *
 * "Conferência" é a etapa honesta para "o caso está com a gente e este
 * cliente ainda não sabe em qual passo": não promete plano que talvez não
 * exista, não manda o aluno responder o que já respondeu, e é onde a
 * própria trilha já coloca `reprovado` — um estado em que o aluno também
 * não tem o que fazer além de esperar.
 *
 * `AC-94` fala das CINCO fases conhecidas, e continua valendo para todas:
 * este ramo só existe para a sexta, que a spec não descreve.
 */
const ETAPA_DE_FASE_DESCONHECIDA = 2

function indiceDaEtapaEmCurso(fase: Fase): number {
  const indice = ETAPAS.findIndex((etapa) => etapa.fases.includes(fase))
  return indice === -1 ? ETAPA_DE_FASE_DESCONHECIDA : indice
}

/**
 * O que falta na etapa em curso, COM unidade — `RF-65`, `AC-96`.
 *
 * "3 de 101" não informa: o aluno não sabe 101 do quê. "Faltam 98 perguntas"
 * informa, e a diferença é entre uma barra de progresso e uma promessa.
 */
function oQueFalta(inicio: Inicio): string | null {
  const { fase, progresso } = inicio

  if (fase === 'coleta') {
    const faltam = progresso.total - progresso.respondidas
    if (faltam <= 0) return 'Você respondeu tudo o que precisávamos.'
    return faltam === 1 ? 'Falta 1 pergunta.' : `Faltam ${faltam} perguntas.`
  }

  if (fase === 'revisao') return 'A espera é com a equipe. Avisamos por e-mail.'
  if (fase === 'reprovado') return 'A equipe pediu um ajuste. Alguém entra em contato.'
  if (fase === 'plano') return 'Há uma decisão sua para tomar.'
  if (fase === 'acompanhamento') return 'Faça a próxima ação e conte como foi.'

  // `T-171`: fase que este cliente não conhece. Antes caía em "faça a
  // próxima ação" — uma ORDEM, para alguém de cuja situação não sabemos
  // nada. A frase abaixo é a única honesta: acompanha o degrau
  // "Conferência", onde `indiceDaEtapaEmCurso` coloca a fase desconhecida
  // pelo mesmo motivo.
  return 'O seu caso está com a equipe. Avisamos quando houver novidade.'
}

export default function TrilhaDaJornada({ inicio }: TrilhaDaJornadaProps) {
  const emCurso = indiceDaEtapaEmCurso(inicio.fase)
  const falta = oQueFalta(inicio)

  return (
    <section className="cartao" aria-label="Sua jornada no PIQ">
      <span className="eyebrow">Onde você está</span>

      {/*
        `trilha` (T-166) substitui `lista` como classe do `<ol>`: é ela que
        desenha o trilho contínuo ligando os degraus (`RF-77`). A estrutura
        interna NÃO muda — cinco `<li>`, `.linha span` com o rótulo,
        `aria-current="step"` na etapa em curso —, porque `navegacao.spec.ts`
        usa os três como seletor (`:796`, `:801`, `:860`).
      */}
      <ol className="trilha list-none p-0">
        {ETAPAS.map((etapa, indice) => {
          const concluida = indice < emCurso
          const atual = indice === emCurso

          return (
            <li
              key={etapa.rotulo}
              className={`degrau ${concluida ? 'feito' : ''} ${atual ? 'agora' : ''}`}
              // `aria-current="step"` é o que faz um leitor de tela anunciar
              // "etapa atual" — sem ele a trilha vira uma lista de cinco
              // itens indistinguíveis para quem não vê a cor.
              aria-current={atual ? 'step' : undefined}
            >
              {/*
                A marca do degrau. Continua `aria-hidden`: o estado já é
                anunciado por `aria-current` e pelos chips "Feito"/"Agora",
                e um leitor de tela lendo "✓" ou "3" antes de cada rótulo
                seria ruído.

                **Não é botão, e nunca será** (`AC-115`). A trilha é
                informativa: tornar os degraus clicáveis restabeleceria a
                barra de sete abas que `RF-57`/`AC-83` mataram.
              */}
              <span aria-hidden="true" className="marca">
                {concluida ? <Icone nome="concluido" /> : indice + 1}
              </span>

              <div className="min-w-0 flex-1">
                {/*
                  O espaçamento e a quebra vivem no CSS (`.degrau .linha`,
                  T-166): na coluna lateral de 300px, rótulo e chip nem
                  sempre cabem juntos, e quem cede a linha é o chip — nunca
                  o rótulo, que quebrado em duas linhas faz o olho ler duas
                  etapas onde há uma.
                */}
                <div className="linha">
                  <span className={atual ? 'font-bold' : concluida ? '' : 'text-muted'}>
                    {etapa.rotulo}
                  </span>
                  {atual && <span className="chip chip-atencao">Agora</span>}
                  {concluida && <span className="chip chip-ok">Feito</span>}
                </div>
                {/* O resumo aparece na etapa atual e nas futuras: é ele que
                    responde "para que serve". Nas concluídas some — o aluno
                    já passou por lá e sabe. */}
                {!concluida && <small className="block text-muted">{etapa.resumo}</small>}
                {atual && falta && <small className="block font-bold">{falta}</small>}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
