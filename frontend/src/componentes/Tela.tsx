/**
 * A casca de toda tela — `RF-57`, `RF-71`, `AC-82`, `AC-84`, `AC-85`,
 * `AC-106` (T-149, duas colunas em T-161).
 *
 * Três partes, como no protótipo validado (linhas 75–89):
 *
 *     ┌─ .top ─────────────┐   ‹ Voltar        localizador
 *     ├─ .corpo ───────────┤   o conteúdo, rolável
 *     ├─ .acoes ───────────┤   sticky: a ação nunca sai da tela
 *     └────────────────────┘
 *
 * **Nenhuma tela foge da casca** (`AC-82`). Uma tela com layout próprio é o
 * começo de um segundo modelo de navegação — foi assim que a barra de sete
 * abas nasceu.
 *
 * ## As duas colunas — `RF-71`, `AC-106` (T-161)
 *
 * *"Por que está com a largura fixa? A pessoa vai preencher pelo
 * computador."* Os 560px vêm do protótipo, que foi desenhado para celular, e
 * a decisão estava certa quando foi tomada; `OQ-29` foi respondida depois,
 * com "a maior parte será preenchida no computador", e ninguém releu a
 * largura à luz disso. No monitor, cem perguntas por uma fresta no meio de
 * uma tela vazia.
 *
 * **Progressivo, nunca substitutivo.** A 360px o layout é IDÊNTICO ao
 * validado: coluna única de 560px, `lateral` acima do conteúdo, na ordem
 * validada. A partir de `lg:` (1024px) a `lateral` vira coluna ao lado e o
 * conteúdo ganha até 760px. O protótipo foi validado com stakeholders para a
 * tela pequena, e é essa a tela que não pode mudar.
 *
 * **Tudo em utilitário do Tailwind, nada em JavaScript.** Layout é decisão de
 * CSS: resolvê-lo por media query em JS o quebraria antes da primeira
 * medição, e faria a tela saltar de um arranjo para o outro na carga.
 *
 * **`lg:max-w-[760px]` é classe arbitrária de propósito.** O token novo
 * caberia em `tailwind.config.js`, mas aquele arquivo é parseado por regex em
 * `tests/app_aluno/estatica/test_css_360px.py` — e o limite não é ilimitado
 * porque linha de texto longa cansa, que é o mesmo motivo do `max-w-tela`.
 */
import { type ReactNode, useEffect, useRef } from 'react'

import { aplicarFocoDeNavegacao } from '../navegacao'

interface TelaProps {
  /** Vai para `document.title` e, por padrão, para o `<h1>` visível. */
  titulo: string
  /** Ausente ⇒ sem "‹ Voltar". A tela Início é a raiz: não há para onde voltar. */
  voltar?: () => void
  /** O localizador à direita do topo — "Dívida 3 · pergunta 4 de 12". */
  onde?: string
  /** `aluno` = 560px (a coluna de leitura); `equipe` = 900px (`AC-87`). */
  largura?: 'aluno' | 'equipe'
  /**
   * `false` quando a tela desenha o próprio título — a de pergunta, cujo
   * `<legend>` já é o enunciado. O `<h1>` continua existindo, invisível:
   * ver a nota do `sr-only`, abaixo.
   */
  mostrarTitulo?: boolean
  /**
   * A identidade da COISA na tela, quando o título não a distingue — `AC-84`.
   *
   * **Por que não basta o `titulo`.** O efeito de foco depende do título, e
   * numa ficha repetível o enunciado é o MESMO para todos os itens:
   * `B5.A01` ("Para quem você deve nessa operação?") não tem interpolação,
   * então passar da dívida `D001` para a `D002` não muda o título, o efeito
   * não dispara, e quem usa leitor de tela segue ouvindo a pergunta da
   * dívida anterior enquanto responde a seguinte. É o caminho mais longo da
   * coleta (88 registros × N dívidas) — onde o dano acontece mais.
   *
   * A tela de pergunta passa `${ID}/${item_id}`. Telas cujo título já é
   * único omitem.
   */
  chave?: string
  /** O rodapé fixo. Sem ele, `.acoes` não é renderizado. */
  acoes?: ReactNode
  /**
   * O mapa da jornada — `RF-71`, `AC-106`.
   *
   * Vive na CASCA e não no conteúdo porque é ela que conhece as duas
   * geometrias: no celular a `lateral` é o primeiro filho do corpo, exatamente
   * onde o protótipo a validou; no desktop ela se destaca em coluna própria.
   * Se cada tela decidisse isso, haveria uma geometria por tela — e `AC-82`
   * existe justamente contra isso.
   *
   * Ausente ⇒ nenhuma coluna lateral é criada, e o conteúdo ocupa a largura
   * inteira. Uma coluna vazia ao lado seria pior que nenhuma.
   */
  lateral?: ReactNode
  children: ReactNode
}

export default function Tela({
  titulo,
  voltar,
  onde,
  largura = 'aluno',
  mostrarTitulo = true,
  chave,
  acoes,
  lateral,
  children,
}: TelaProps) {
  const cabecalho = useRef<HTMLHeadingElement>(null)

  // `[chave, titulo]`, NUNCA `[]` — `AC-84`. Com `[]`, trocar o conteúdo
  // dentro de um componente já montado não refocaria o `<h1>`. E só
  // `[titulo]` não basta: numa ficha repetível o enunciado repete entre
  // itens, então a `chave` é o que distingue "outra pergunta" de "mesma
  // pergunta, item seguinte". Ver a nota da prop.
  useEffect(() => {
    aplicarFocoDeNavegacao(titulo, cabecalho.current)
  }, [chave, titulo])

  return (
    <div className="flex justify-center">
      {/*
        `min-h-screen` vai na COLUNA, não no wrapper — é o que o protótipo faz
        (`.screen`, linha 73: `min-height: calc(100vh - 44px)`).

        Com a altura no wrapper e a coluna encolhida ao conteúdo, o `.acoes`
        `sticky` gruda no fim de um conteúdo curto e **sobrepõe** o que vem
        acima. Foi o que aconteceu quando a trilha da Rodada 6 entrou: o
        rodapé cobriu o cartão da próxima etapa. A coluna precisa ocupar a
        janela inteira para o `.corpo` (`flex-1`) empurrar o rodapé até o pé.
      */}
      {/*
        A largura máxima da COLUNA INTEIRA.

        No celular é a do protótipo, intocada: `max-w-tela` (560px) para o
        aluno, `max-w-equipe` (900px) para a equipe (`AC-87`). A partir de
        `lg:` a coluna do aluno cresce o bastante para caber a lateral + o
        conteúdo lado a lado — e para, porque tela larga não autoriza linha de
        texto infinita. As telas da equipe não mudam: `AC-87` fixou 900px
        para elas, e este requisito é sobre a tela do ALUNO.
      */}
      <div
        className={`flex min-h-screen w-full flex-col ${
          largura === 'equipe'
            ? 'max-w-equipe'
            : lateral
              ? 'max-w-tela lg:max-w-[1120px]'
              : 'max-w-tela lg:max-w-[760px]'
        }`}
      >
        <div className="top">
          {voltar ? (
            <button type="button" className="back" onClick={voltar}>
              ‹ Voltar
            </button>
          ) : (
            // Não é decoração. O `.top` é `justify-between`: sem este span o
            // localizador migra para a esquerda. O protótipo faz exatamente
            // isso (linhas 227 e 409).
            <span />
          )}
          {onde ? <span className="where">{onde}</span> : <span />}
        </div>

        <div className="corpo">
          {/*
            O `<h1>` existe SEMPRE, visível ou não — `AC-84` precisa de algo
            para focar, e uma tela sem heading é uma tela que leitor de tela
            não consegue anunciar. `sr-only` o mantém na árvore de
            acessibilidade e fora da tela.

            Ele fica FORA das duas colunas: é o título da tela inteira, não do
            conteúdo, e empurrá-lo para dentro de uma coluna o desalinharia da
            lateral no desktop.
          */}
          <h1 ref={cabecalho} className={mostrarTitulo ? undefined : 'sr-only'}>
            {titulo}
          </h1>

          {lateral ? (
            /*
              `AC-106`, as duas geometrias no mesmo DOM.

              A 360px: `flex flex-col` — a lateral vem ANTES do conteúdo, que
              é a ordem do protótipo validado, e nada tem largura mínima que
              force rolagem lateral.

              A ≥1024px: `lg:flex-row` põe a lateral à esquerda com largura
              fixa de leitura (`lg:w-[300px] lg:flex-none`) e o conteúdo fica
              com `lg:flex-1 lg:min-w-0` — o `min-w-0` não é enfeite: sem ele
              um filho de flex tem `min-width:auto` e um texto longo estoura a
              coluna em vez de quebrar.

              `lg:sticky lg:top-4` mantém o mapa à vista enquanto o conteúdo
              rola. É o que `AC-95` pede em espírito — o mapa visível sem
              interação — na tela em que rolar cem perguntas o tiraria de vista.
            */
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start">
              <div className="lg:w-[300px] lg:flex-none lg:sticky lg:top-4">{lateral}</div>
              <div className="flex min-w-0 flex-1 flex-col gap-5">{children}</div>
            </div>
          ) : (
            children
          )}
        </div>

        {acoes && <div className="acoes">{acoes}</div>}
      </div>
    </div>
  )
}
