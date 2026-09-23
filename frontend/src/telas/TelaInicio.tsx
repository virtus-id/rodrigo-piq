/**
 * A tela Início — uma única próxima etapa — `RF-58`, `AC-81`, `EC-25`
 * (T-150).
 *
 * É o `renderInicio` do protótipo validado (linha ~917), e é o centro do
 * produto: substitui a barra de sete abas que a Rodada 4 inventou.
 *
 * **Por que uma etapa só.** A persona é um servidor público endividado e
 * inseguro. Para ele, sete opções — várias inaplicáveis ao seu momento — não
 * são liberdade: são a pergunta "o que eu faço agora?" devolvida sem resposta.
 * O servidor sabe a fase do caso e decide; esta tela desenha a decisão.
 *
 * **Esta tela não decide nada.** Ela não olha `fase` para escolher o destino
 * — o `destino` vem do servidor (`RF-34`, Lei nº 3). O `switch` abaixo escolhe
 * o TEXTO e o enquadramento visual de cada fase, que é trabalho de interface.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Icone from '../componentes/Icone'
import Tela from '../componentes/Tela'
import TrilhaDaJornada from '../componentes/TrilhaDaJornada'
import { formatarDecimalDoServidor } from '../mascaras'
import { type Rota } from '../navegacao'
import { obterInicio } from '../services/api'
import type { DestinoDaEtapa, Inicio } from '../tipos'

interface TelaInicioProps {
  casoId: string
  irPara: (rota: Rota) => void
  /**
   * `true` quando a conta é revisora — `RF-59`, `AC-80`.
   *
   * **A porta de entrada da área da equipe, e a única.** Sem ela as três
   * telas de equipe só eram alcançáveis digitando o hash, o que deixava
   * `AC-80` passando por vacuidade: nenhum link existia para ninguém.
   *
   * Não é autorização — quem autoriza é o servidor, a cada requisição. É só
   * o que decide se o caminho é oferecido.
   */
  eRevisor?: boolean
  /**
   * Encerra a sessão — `T-188`.
   *
   * Sem esta prop não havia NENHUM caminho de sair pela interface, para
   * ninguém: quem quisesse trocar de conta precisava apagar o cookie na
   * mão. Fica na raiz da navegação do aluno (aqui, e o equivalente em
   * `TelaRevisao` para o revisor) — as duas únicas telas sem `voltar`,
   * mesmo lugar onde "sair" termina fazendo sentido.
   */
  aoSair: () => void
}

/**
 * `destino` do servidor → `Rota` do cliente.
 *
 * O servidor manda um nome de tela, não uma URL: o roteamento é do cliente, e
 * acoplar o backend a hashes de navegação faria a interface não poder mudar de
 * rota sem mexer no servidor. Um destino que não reconhecemos cai no plano —
 * nunca numa tela em branco.
 */
function rotaDoDestino(inicio: Inicio): Rota {
  const { destino, ID_PERGUNTA, item_id } = inicio.proxima_etapa
  switch (destino) {
    case 'consentimento':
      return { tela: 'consentimento' }
    case 'pergunta':
      return {
        tela: 'pergunta',
        idPergunta: ID_PERGUNTA ?? undefined,
        itemId: item_id ?? undefined,
      }
    case 'calculando':
      return { tela: 'calculando' }
    case 'aguardando':
      return { tela: 'aguardando' }
    case 'bloco10':
      return { tela: 'bloco10' }
    case 'acoes':
      return { tela: 'acoes' }
    case 'progresso':
      return { tela: 'progresso' }
    case 'plano':
      return { tela: 'plano' }
    default:
      // `T-169`: a promessa do docblock, implementada. Sem este ramo a
      // função devolvia `undefined` para um `destino` que o cliente não
      // conhece — e `irPara(undefined)` quebrava a navegação.
      //
      // **Por que o plano, e não o Início.** Um destino desconhecido vem de
      // um servidor mais novo que este cliente; o plano é a tela que existe
      // em toda fase pós-cálculo e nunca depende de um parâmetro que o
      // cliente não saiba montar. Mandar ao Início daria um laço: o Início
      // é quem devolve o destino.
      return { tela: 'plano' }
  }
}

/**
 * O texto de cada próxima etapa — `RF-58`.
 *
 * **É aqui que a redação ao aluno vive, e não no servidor.** `AC-37` proíbe
 * string longa no código da aplicação, e a trava está certa: texto ao aluno
 * num arquivo de rota não passa por revisão de conteúdo. O servidor decide
 * QUAL é a etapa; esta tabela decide COMO dizer.
 *
 * `Record` sobre a união fechada `DestinoDaEtapa`: um destino novo sem texto
 * aqui não compila.
 */
const TEXTO_DA_ETAPA: Readonly<
  Record<DestinoDaEtapa, { rotulo: string; detalhe: string }>
> = {
  consentimento: {
    rotulo: 'Registrar o seu consentimento',
    detalhe: 'Antes de qualquer pergunta sobre o seu dinheiro.',
  },
  pergunta: {
    rotulo: 'Continuar de onde você parou',
    detalhe: 'Tudo o que você já respondeu está guardado.',
  },
  calculando: {
    rotulo: 'Montar o seu plano',
    detalhe: 'Você respondeu tudo o que precisávamos.',
  },
  aguardando: {
    rotulo: 'Aguardar a conferência',
    detalhe: 'Você não precisa fazer nada agora.',
  },
  progresso: {
    rotulo: 'Ver as suas respostas',
    detalhe: 'Nada do que você respondeu foi perdido.',
  },
  bloco10: {
    rotulo: 'Decidir sobre o dinheiro que você tem disponível',
    detalhe: 'Seu plano está pronto e conferido.',
  },
  acoes: {
    rotulo: 'Ver o que fazer agora',
    detalhe: 'Faça a próxima ação e conte como foi.',
  },
  plano: {
    rotulo: 'Ver o seu plano',
    detalhe: 'Seu caso foi encerrado.',
  },
}

/**
 * O valor em destaque, pronto para entrar na frase — `AC-88`.
 *
 * A conversão em si vive em `mascaras.ts` (`formatarDecimalDoServidor`), com
 * a mesma máscara da digitação — dinheiro não pode ter duas formatações no
 * mesmo app. Aqui fica só o enquadramento: o travessão e o `R$` que compõem
 * a frase do protótipo, e a composição é do CLIENTE porque o servidor manda
 * o valor separado do destino (`RF-13` + Lei nº 3).
 */
function formatarDestaque(valor: string | null): string {
  const texto = formatarDecimalDoServidor(valor)
  return texto ? ` — R$ ${texto}` : ''
}

/** A chamada da fase — o `eyebrow` do cartão de destaque, do protótipo. */
const CHAMADA_DA_FASE: Readonly<Record<Inicio['fase'], string>> = {
  coleta: 'Sua próxima etapa',
  revisao: 'Agora é com a gente',
  reprovado: 'Um instante a mais',
  plano: 'Sua próxima etapa',
  acompanhamento: 'Sua próxima ação',
}

export default function TelaInicio({ casoId, irPara, eRevisor, aoSair }: TelaInicioProps) {
  const [inicio, setInicio] = useState<Inicio | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      setInicio(await obterInicio(casoId))
    } catch {
      setErro('Não foi possível carregar a sua próxima etapa.')
    } finally {
      setCarregando(false)
    }
  }, [casoId])

  useEffect(() => {
    void carregar()
  }, [carregar])

  if (carregando) {
    return (
      <Tela titulo="Início">
        <Esqueleto forma="resumo" anuncio="Carregando sua próxima etapa" />
      </Tela>
    )
  }

  if (!inicio) {
    return (
      <Tela titulo="Início">
        <p role="alert" className="aviso-erro">
          {erro ?? 'Nada para mostrar agora.'}
        </p>
      </Tela>
    )
  }

  const { proxima_etapa: etapa, fase } = inicio
  // `T-169`: `destino` desconhecido (servidor mais novo que este cliente)
  // devolvia `undefined`, e a linha seguinte (`texto.rotulo`) lançava —
  // derrubando a aplicação inteira, já que não há `ErrorBoundary`. O
  // fallback é o texto de "ver o plano", coerente com `rotaDoDestino`, que
  // manda para lá pelo mesmo motivo.
  const texto = TEXTO_DA_ETAPA[etapa.destino] ?? TEXTO_DA_ETAPA.plano

  // O valor vem SEPARADO do rótulo (`AC-88`) e é composto AQUI. O servidor
  // manda "Decidir sobre o dinheiro que você tem disponível" + "3000.00";
  // é esta linha que produz a frase do protótipo. Fazer isso no servidor
  // significaria montar dinheiro dentro de texto, que `RF-13` proíbe.
  //
  // `formatarMoeda` consome dígitos crus (é a máscara de digitação), então a
  // string decimal do servidor é normalizada para centavos antes — nunca por
  // `Number()`, que é exatamente o ponto flutuante que `RF-13` proíbe.
  const destaque = texto.rotulo + formatarDestaque(inicio.valor_em_destaque)

  return (
    <Tela
      titulo="Início"
      // `RF-71`, `AC-106`: o mapa vai para a casca, que conhece as duas
      // geometrias. No celular ele continua ACIMA do conteúdo, exatamente
      // onde o protótipo o validou (`RF-64`: quem chega precisa saber onde
      // está antes de receber uma ordem do que fazer); no computador vira
      // coluna ao lado, e o conteúdo deixa de ser uma fresta.
      lateral={<TrilhaDaJornada inicio={inicio} />}
      acoes={
        <>
          <Botao onClick={() => irPara(rotaDoDestino(inicio))}>{texto.rotulo}</Botao>
          {/* O segundo botão NUNCA é uma alternativa de fluxo: é sempre uma
              consulta ao que já existe. A escolha segue sendo uma só. */}
          {fase === 'coleta' && (
            <Botao variante="discreto" onClick={() => irPara({ tela: 'progresso' })}>
              Ver meu progresso
            </Botao>
          )}
          {/* `RF-68`: a porta de "Minhas respostas", e a ÚNICA. Sem ela a
              tela só seria alcançável digitando o hash — foi assim que a
              revisão deixou de existir na prática até a Rodada 7.
              Aparece a partir da primeira resposta: com zero respostas não há
              o que rever, e oferecer a lista vazia seria um caminho que não
              leva a nada. */}
          {inicio.progresso.respondidas > 0 && (
            <Botao variante="discreto" onClick={() => irPara({ tela: 'respostas' })}>
              Ver e editar minhas respostas
            </Botao>
          )}
          {inicio.plano_liberado && fase !== 'coleta' && (
            <Botao variante="discreto" onClick={() => irPara({ tela: 'plano' })}>
              Ver meu plano
            </Botao>
          )}
          {/* `AC-80`: só a conta revisora vê este caminho. Para o aluno o
              botão não existe no DOM — não basta desabilitar, porque ele
              ainda leria "Fila de conferência" e se perguntaria o que é. */}
          {eRevisor === true && (
            <Botao variante="discreto" onClick={() => irPara({ tela: 'equipe-fila' })}>
              Ir para a fila de conferência
            </Botao>
          )}
          <Botao variante="discreto" onClick={aoSair}>
            Sair
          </Botao>
        </>
      }
    >
      {/* O mapa saiu daqui em T-161 — ele agora é a `lateral` da casca, que
          o coloca ANTES do passo no celular (`RF-64`, ordem validada) e ao
          lado no computador (`AC-106`). O conteúdo desta tela é a próxima
          etapa; o mapa é contexto dela, e contexto é geometria de casca. */}
      {/*
        O selo do lado do rótulo — `RF-74` (T-163). É reforço visual da
        próxima etapa, nunca o portador do significado: o texto ao lado diz
        tudo, e o ícone é `aria-hidden` por construção (`AC-110`).

        A borda de 2px do `.cartao-proximo` continua sendo o que marca esta
        tela (`RF-58`); o selo não a substitui.
      */}
      <div className="cartao-proximo">
        <div className="flex items-start gap-3">
          <span className="selo">
            <Icone nome="avancar" />
          </span>
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            {/* `T-169`: fase desconhecida renderizaria vazio — o eyebrow
                sumiria e o cartão perderia a chamada. */}
            <span className="eyebrow">{CHAMADA_DA_FASE[fase] ?? CHAMADA_DA_FASE.coleta}</span>
            <div className="grande">{destaque}</div>
          </div>
        </div>
        <p className="nota">{texto.detalhe}</p>
      </div>

      {/* A barra de progresso saiu daqui na Rodada 6. Ela dizia "3 de 101",
          e `RF-65` mostrou por que isso não informava: 101 do quê. Quem conta
          o que falta agora é a trilha, com unidade ("faltam 98 perguntas") e
          dentro da etapa a que o número pertence. Dois lugares mostrando o
          mesmo progresso com redações diferentes era parte da confusão. */}

      {/* `EC-25`: nas fases em que o aluno não tem o que fazer, a mensagem do
          ESTADO é o conteúdo — nunca uma tela vazia, e nunca o erro técnico
          de `ERRO_DE_CALCULO`, que o servidor já traduz. */}
      {fase !== 'coleta' && (
        <div className="aviso-ok" role="status">
          <div>{inicio.mensagem}</div>
        </div>
      )}
    </Tela>
  )
}
