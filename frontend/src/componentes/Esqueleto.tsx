/**
 * Esqueleto de carregamento — `RF-75`, `AC-112`, `AC-113` (T-164).
 *
 * **O que ele substitui.** Treze telas mostravam literalmente
 * `<p role="status">Carregando…</p>`. Cada troca de tela piscava um texto
 * solto no canto superior, e quando os dados chegavam o layout saltava —
 * porque nada reservava o espaço do que vinha.
 *
 * **A árvore de acessibilidade não perde nada** (`AC-112`). O desenho é
 * `aria-hidden`; o anúncio continua sendo um `role="status"`, com a mesma
 * redação de antes. Quem usa leitor de tela recebe exatamente o que recebia.
 * Por isso o `role="status"` vive AQUI dentro, e não em cada tela: uma tela
 * que esquecesse de escrevê-lo perderia o anúncio em silêncio, e nenhum
 * teste de renderização pegaria isso.
 *
 * **Movimento é opcional** (`AC-113`). Com `prefers-reduced-motion: reduce`
 * o brilho não roda e o bloco aparece parado — o mesmo tratamento que o
 * `.pulse` recebeu em `T-150`. Movimento contínuo pode desencadear enjoo e
 * enxaqueca, e quem pediu menos movimento no sistema recebe a mesma
 * informação, sem ele.
 *
 * **Só no ramo de carregamento.** As telas têm três estados — `carregando`,
 * `erro`, dados — e este componente substitui apenas o primeiro. Um
 * esqueleto brilhando sobre uma requisição que falhou é pior que o texto que
 * substituiu: promete conteúdo que não vem.
 */

/**
 * As formas correspondem ao que cada tela carrega de fato — não há uma
 * forma genérica. Um esqueleto que não tem o formato do conteúdo apenas
 * troca o salto de layout de lugar.
 */
export type FormaDoEsqueleto =
  /** Cartão com dois valores em destaque lado a lado — a tela do plano. */
  | 'resumo'
  /** Lista de cartões com marca circular e duas linhas — ordem, ações, fichas. */
  | 'lista'
  /** Um enunciado e um campo — a tela de pergunta. */
  | 'pergunta'
  /** Bloco de texto corrido — consentimento, mensagens. */
  | 'texto'

interface EsqueletoProps {
  forma?: FormaDoEsqueleto
  /**
   * O que o leitor de tela anuncia. Cada tela diz o que está carregando —
   * "Carregando seu plano" informa mais que "Carregando…", e o custo de
   * escrever é zero.
   */
  anuncio?: string
  /** Quantos itens na forma `lista`. */
  itens?: number
}

/** Uma barra do esqueleto. `aria-hidden` vem do contêiner. */
function Barra({ largura, altura = 11 }: { largura: string; altura?: number }) {
  return <div className="sk" style={{ width: largura, height: `${altura}px` }} />
}

function Resumo() {
  return (
    <div className="cartao">
      <Barra largura="42%" />
      <div className="flex gap-6">
        {[0, 1].map((i) => (
          <div key={i} className="flex flex-1 flex-col gap-2">
            <Barra largura="74%" altura={27} />
            <Barra largura="56%" altura={9} />
          </div>
        ))}
      </div>
    </div>
  )
}

function ItemDeLista() {
  return (
    <div className="cartao">
      <div className="flex items-center gap-3">
        <div className="sk h-[26px] w-[26px] flex-none rounded-full" />
        <div className="flex flex-1 flex-col gap-2">
          <Barra largura="35%" />
          <Barra largura="70%" altura={9} />
        </div>
      </div>
    </div>
  )
}

function Pergunta() {
  return (
    <>
      <Barra largura="100%" altura={7} />
      <div className="flex flex-col gap-3">
        <Barra largura="85%" altura={22} />
        <Barra largura="60%" altura={22} />
      </div>
      <div className="sk h-[58px] w-full rounded-piq" />
    </>
  )
}

function Texto() {
  return (
    <div className="flex flex-col gap-2">
      <Barra largura="100%" />
      <Barra largura="96%" />
      <Barra largura="88%" />
      <Barra largura="45%" />
    </div>
  )
}

export default function Esqueleto({
  forma = 'texto',
  anuncio = 'Carregando…',
  itens = 3,
}: EsqueletoProps) {
  return (
    <>
      {/*
        O anúncio. `sr-only` porque o conteúdo visível é o desenho abaixo —
        mas ele EXISTE, e é o que `AC-112` exige: a informação que o
        `<p role="status">Carregando…</p>` dava não pode sumir da árvore de
        acessibilidade só porque a tela ficou mais bonita.
      */}
      <span role="status" className="sr-only">
        {anuncio}
      </span>

      {/*
        O desenho é decorativo: quem o lê é o olho. Para o leitor de tela
        ele seria uma sequência de caixas vazias — ruído puro.
      */}
      <div aria-hidden="true" className="flex flex-col gap-4">
        {forma === 'resumo' && <Resumo />}
        {forma === 'pergunta' && <Pergunta />}
        {forma === 'texto' && <Texto />}
        {forma === 'lista' &&
          Array.from({ length: itens }, (_, i) => <ItemDeLista key={i} />)}
      </div>
    </>
  )
}
