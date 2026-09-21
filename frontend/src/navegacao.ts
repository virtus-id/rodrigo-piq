/**
 * Roteamento por hash — `RF-57`, `AC-84`, `AC-86`, `AC-91` (T-149).
 *
 * É a transcrição de `go(id)` do protótipo validado (linha ~820), que faz
 * três coisas que nenhuma biblioteca de rota faz por conta própria: foca o
 * `<h1>` da tela nova, rola ao topo e atualiza `document.title`.
 *
 * **Por que não `react-router`.** A justificativa está em
 * `plans/app-aluno.plan.md` §R5.2, e `sdd.config.md` §6 exige que ela esteja
 * escrita: a biblioteca resolve mapas declarativos de dezenas de rotas
 * aninhadas, que não temos; e as três coisas acima — as únicas que de fato
 * precisamos — ela não entrega. Escreveríamos este mesmo arquivo dentro de um
 * `useEffect` acoplado a `useLocation`, mais 60 kB.
 *
 * **`Rota` é união discriminada de propósito.** Isso faz o `switch` do
 * `App.tsx` ser exaustivo POR TIPO: uma tela nova sem caso no `switch` não
 * compila. É a mesma trava que `app/casos/fases.py::fase_do_estado` tem no
 * servidor, do outro lado da fronteira.
 */
import { useCallback, useEffect, useState } from 'react'

/** Uma tela do fluxo. O `switch` do `App.tsx` cobre todos os membros. */
export type Rota =
  | { tela: 'entrada' }
  | { tela: 'consentimento' }
  | { tela: 'inicio' }
  | { tela: 'progresso' }
  | { tela: 'fichas' }
  /**
   * "Minhas respostas" — a revisão do que já foi dito (`RF-68`, T-160).
   *
   * Com `idPergunta`, é a CORREÇÃO de uma delas (`RF-69`, `AC-102`): a
   * pergunta abre para edição e, gravada, o aluno volta para a lista.
   *
   * **Por que a correção mora aqui e não em `pergunta`.** As duas telas
   * carregam a mesma pergunta pela mesma rota e gravam pela mesma rota
   * (`RF-69` proíbe uma segunda via); o que difere é de onde o aluno veio e
   * para onde ele volta. Pendurar isso em `#pergunta/{ID}` misturaria os dois
   * casos num só hash — e `#pergunta/{ID}` já significa outra coisa desde
   * `T-149`: a RETOMADA, em que gravar segue para a próxima pergunta, não
   * para a lista. Um mesmo hash com dois destinos depois do "Continuar" é a
   * ambiguidade que `AC-91` manda evitar.
   */
  | { tela: 'respostas'; idPergunta?: string; itemId?: string }
  | { tela: 'pergunta'; idPergunta?: string; itemId?: string }
  | { tela: 'calculando' }
  | { tela: 'aguardando' }
  | { tela: 'plano' }
  | { tela: 'bloco10' }
  | { tela: 'coleta-dirigida'; bloco: 7 | 8 }
  | { tela: 'acoes' }
  | { tela: 'acao'; acaoId: string }
  | { tela: 'recalculo' }
  | { tela: 'equipe-fila' }
  | { tela: 'equipe-caso'; casoId: string }
  | { tela: 'equipe-painel' }

/**
 * A rota para onde tudo cai quando não há nada melhor — `AC-91`, `EC-26`.
 *
 * Nunca uma tela em branco: o Início sabe ler a fase do caso e decidir o
 * próximo passo, então é o único destino honesto para um hash que não
 * reconhecemos.
 */
export const ROTA_PADRAO: Rota = { tela: 'inicio' }

/**
 * O evento que `irPara` dispara para avisar os hooks — `AC-86`.
 *
 * **`history.pushState` NÃO dispara `popstate`.** Essa é a armadilha nº 1
 * desta reescrita: o protótipo não a sente porque re-renderiza sincronamente
 * no `click`, mas no React o estado só muda se alguém avisar. Sem este
 * evento, o sintoma é "o botão não faz nada, mas a URL muda".
 */
const EVENTO_NAVEGACAO = 'piq:navegou'

/**
 * O prefixo do `<title>`, como no protótipo (`go()`, linha ~832).
 *
 * **A outra metade do título vem da tela, não daqui.** Houve um mapa
 * `TITULO_DA_TELA` neste módulo; ele foi removido por ser código morto **e
 * por já ter divergido**: dizia `'Meu progresso'` enquanto a tela passava
 * `'Onde você está'`. Duas fontes de verdade para o mesmo texto sempre
 * escolhem a errada na hora de ler. A fonte única é a prop `titulo` que cada
 * tela dá a `Tela.tsx`, que é também o texto do `<h1>` — então título da aba
 * e cabeçalho não podem discordar por construção.
 */
const TITULO_BASE = 'PIQ Meu Plano'

/** As telas da equipe — `RF-59`. Usadas para largura e para o filtro por papel. */
export const TELAS_DA_EQUIPE: ReadonlySet<Rota['tela']> = new Set([
  'equipe-fila',
  'equipe-caso',
  'equipe-painel',
] as const)

export function eTelaDaEquipe(rota: Rota): boolean {
  return TELAS_DA_EQUIPE.has(rota.tela)
}

/** `Rota` → o hash da URL, sem o `#`. */
export function rotaParaHash(rota: Rota): string {
  switch (rota.tela) {
    case 'pergunta':
    case 'respostas': {
      // A pergunta viaja com o alvo da retomada (`pergunta`) ou da correção
      // (`respostas`), para que recarregar a página não perca o lugar. Os
      // dois são opcionais: sem eles, `pergunta` deixa o servidor decidir
      // qual é a próxima (`RF-45`) e `respostas` é a lista inteira.
      const partes = [rota.tela, rota.idPergunta, rota.itemId].filter(Boolean)
      return partes.join('/')
    }
    case 'acao':
      return `${rota.tela}/${rota.acaoId}`
    case 'coleta-dirigida':
      return `${rota.tela}/${rota.bloco}`
    case 'equipe-caso':
      return `${rota.tela}/${rota.casoId}`
    default:
      return rota.tela
  }
}

/**
 * O hash da URL → `Rota`. Hash desconhecido, malformado ou vazio cai em
 * `ROTA_PADRAO` (`AC-91`, `EC-26`).
 *
 * Um `#coleta-dirigida/9` — bloco que não existe — também cai no padrão: um
 * parâmetro inválido não é motivo para uma tela branca.
 */
export function hashParaRota(hash: string): Rota {
  const limpo = hash.replace(/^#/, '')
  if (!limpo) return ROTA_PADRAO

  const [tela, ...resto] = limpo.split('/')

  switch (tela) {
    case 'entrada':
    case 'consentimento':
    case 'inicio':
    case 'progresso':
    case 'fichas':
    case 'calculando':
    case 'aguardando':
    case 'plano':
    case 'bloco10':
    case 'acoes':
    case 'recalculo':
    case 'equipe-fila':
    case 'equipe-painel':
      return { tela }
    case 'pergunta':
    case 'respostas':
      return { tela, idPergunta: resto[0], itemId: resto[1] }
    case 'coleta-dirigida': {
      const bloco = Number(resto[0])
      return bloco === 7 || bloco === 8 ? { tela, bloco } : ROTA_PADRAO
    }
    case 'acao':
      return resto[0] ? { tela, acaoId: resto[0] } : ROTA_PADRAO
    case 'equipe-caso':
      return resto[0] ? { tela, casoId: resto[0] } : ROTA_PADRAO
    default:
      return ROTA_PADRAO
  }
}

/**
 * Navega para `rota`, empilhando no histórico do navegador.
 *
 * Dispara `EVENTO_NAVEGACAO` porque `pushState` não dispara `popstate` — ver
 * a nota daquela constante. Fora de um componente de propósito: chamável de
 * qualquer lugar, inclusive de um `catch`.
 */
export function irPara(rota: Rota): void {
  const hash = `#${rotaParaHash(rota)}`
  if (window.location.hash !== hash) {
    window.history.pushState(null, '', hash)
  }
  window.dispatchEvent(new CustomEvent(EVENTO_NAVEGACAO))
}

/**
 * Substitui a rota corrente sem empilhar — para normalizar uma URL inválida
 * sem deixar no histórico um passo que o "voltar" reapresentaria.
 */
export function substituirRota(rota: Rota): void {
  window.history.replaceState(null, '', `#${rotaParaHash(rota)}`)
  window.dispatchEvent(new CustomEvent(EVENTO_NAVEGACAO))
}

/**
 * A rota corrente, reagindo a navegação própria E ao histórico do navegador.
 *
 * **Escuta os DOIS eventos** (`AC-86`, `EC-27`): `popstate` para o voltar do
 * navegador, `piq:navegou` para as nossas próprias transições. Escutar só um
 * quebra metade da navegação, e a metade que quebra depende de qual.
 */
export function useRota(): [Rota, (rota: Rota) => void] {
  const [rota, setRota] = useState<Rota>(() => hashParaRota(window.location.hash))

  useEffect(() => {
    const sincronizar = () => setRota(hashParaRota(window.location.hash))
    window.addEventListener('popstate', sincronizar)
    window.addEventListener(EVENTO_NAVEGACAO, sincronizar)
    return () => {
      window.removeEventListener('popstate', sincronizar)
      window.removeEventListener(EVENTO_NAVEGACAO, sincronizar)
    }
  }, [])

  return [rota, useCallback((destino: Rota) => irPara(destino), [])]
}

/**
 * Os três comportamentos de acessibilidade de `go()` — `AC-84`.
 *
 * Chamado pela casca (`Tela.tsx`), não pelo roteador: é a tela que sabe seu
 * título e possui o `<h1>`. Sempre os três juntos — uma navegação que rola ao
 * topo mas não move o foco deixa quem usa leitor de tela ouvindo a tela
 * anterior.
 */
export function aplicarFocoDeNavegacao(titulo: string, cabecalho: HTMLElement | null): void {
  document.title = `${TITULO_BASE} · ${titulo}`
  window.scrollTo(0, 0)
  if (cabecalho) {
    // `tabindex="-1"` torna focável por script sem entrar na ordem de Tab.
    // `preventScroll` porque já rolamos ao topo — sem ele o navegador
    // desfaria a rolagem para trazer o heading à vista.
    cabecalho.setAttribute('tabindex', '-1')
    cabecalho.focus({ preventScroll: true })
  }
}
