/**
 * Iconografia do PIQ — `RF-74`, `AC-110`, `AC-111` (T-163).
 *
 * **Todo ícone é decorativo, e o componente torna o contrário impossível.**
 * O `<svg>` sai daqui sempre com `aria-hidden="true"`, sempre com
 * `focusable="false"`, e **sem** `<title>`. Não existe prop que permita
 * mudar isso — não por rigidez, mas porque a alternativa já quebrou coisa:
 *
 * 1. `AC-114` exige que o nome acessível do botão da tela de pergunta seja
 *    exatamente `Continuar`, e `coleta.spec.ts:285` compara por igualdade
 *    estrita. Um `<title>` dentro do `<svg>` entra na composição do nome
 *    acessível em alguns leitores, e a igualdade quebra.
 * 2. `focusable="false"` é explícito porque em motores legados o padrão de
 *    `<svg>` é focável — o que acrescentaria uma parada de Tab entre o campo
 *    e a ação principal, e `coleta.spec.ts:297` permite no máximo duas.
 *
 * **Ícone nunca carrega significado sozinho** (`AC-110`, WCAG 1.4.1): o
 * rótulo textual existe sempre ao lado. Aqui o ícone é reforço de leitura,
 * nunca substituto — a persona tem baixa visão presumida, e um pictograma
 * sem palavra é exatamente o que ela não consegue usar.
 *
 * **Por que não uma biblioteca.** O vocabulário é o do PIQ — dívida, prazo,
 * conferência, reserva. Nenhum pacote traz isso, e trazer centenas de ícones
 * para usar oito pesa no carregamento de quem está em rede instável
 * (`plans/app-aluno.plan.md:177`). São oito `path`, escritos aqui.
 *
 * O `public/icons.svg` que existia até esta tarefa continha ícones de
 * Bluesky, Discord e GitHub: era boilerplate do template do Vite, sem uma
 * única referência no código. Removido (`AC-111`).
 */
import type { SVGProps } from 'react'

/**
 * Os nomes são os do domínio, em pt-BR (`sdd.config.md` §7) — não os do
 * desenho. `conferencia` diz o que o ícone significa no PIQ; "escudo" diria
 * o que ele parece, e no dia em que o desenho mudasse o nome mentiria.
 */
export type NomeDoIcone =
  | 'avancar'
  | 'concluido'
  | 'prazo'
  | 'taxa'
  | 'dinheiro'
  | 'conferencia'
  | 'baixar'
  | 'reserva'
  | 'sair'

/**
 * Traçado aberto, 20×20, `stroke` herdando `currentColor`.
 *
 * Contorno e não preenchimento: a paleta tem um acento só (`#0F6E56`), e
 * silhueta cheia nesse verde vira mancha escura ao lado de texto. O traço
 * de 1.8–2 acompanha o peso da Atkinson Hyperlegible.
 */
const TRACADO: Readonly<Record<NomeDoIcone, string>> = {
  avancar: 'M4 10h12M11 5l5 5-5 5',
  concluido: 'M4 10.5l4 4 8-8.5',
  // Relógio — prazo é tempo até a última quitação.
  prazo: 'M10 6.2v4l2.6 1.6',
  // Linha ascendente — taxa é o que cresce contra o aluno.
  taxa: 'M4 14L9 8.5l3 3L16 6',
  // Cédula.
  dinheiro: 'M3 6h14v8H3zM10 12.2a2.2 2.2 0 100-4.4 2.2 2.2 0 000 4.4',
  // Escudo — a conferência humana que protege o plano (`RF-23`).
  conferencia: 'M10 2.6l6 2.7v4.3c0 3.6-2.5 6.3-6 7.8-3.5-1.5-6-4.2-6-7.8V5.3z',
  baixar: 'M10 3v9M6 8.5l4 4 4-4M4 16h12',
  // Cofre/reserva — o dinheiro guardado, não mobilizado.
  reserva: 'M4 7.5h12v8H4zM7 7.5V5.2h6v2.3M10 10.4v2.2',
  // Porta (moldura aberta à direita) + seta saindo — encerrar sessão (`T-190`).
  sair: 'M8 4H4v12h4M8 10h7M12 6l4 4-4 4',
}

/** Ícones cujo desenho inclui um círculo além do traçado. */
const COM_CIRCULO: ReadonlySet<NomeDoIcone> = new Set<NomeDoIcone>(['prazo'])

/**
 * As props de acessibilidade ficam FORA do que se pode passar.
 *
 * `Omit` impede em tempo de compilação; a ordem do spread impede em tempo de
 * execução (ver abaixo). As duas coisas são necessárias: `Omit` não protege
 * quem faz `{...(props as never)}`, e a auditoria estática de
 * `test_iconografia.py` lê o TEXTO do fonte — ela veria `aria-hidden="true"`
 * escrito aqui e não perceberia um override chegando por prop.
 */
interface IconeProps
  extends Omit<
    SVGProps<SVGSVGElement>,
    'children' | 'aria-hidden' | 'role' | 'focusable' | 'tabIndex'
  > {
  nome: NomeDoIcone
}

export default function Icone({ nome, className = '', ...resto }: IconeProps) {
  return (
    <svg
      // `{...resto}` vem ANTES dos atributos de acessibilidade, de propósito:
      // no JSX o último atributo vence, então nada que chegue por prop
      // consegue sobrescrever `aria-hidden`, `role` ou `focusable`. Com o
      // spread por último, um `role="img"` passado de fora tornaria o ícone
      // visível ao leitor de tela e quebraria `AC-114` — e a auditoria
      // estática, que lê o fonte, não veria nada de errado.
      {...resto}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`icone ${className}`}
      // Os três atributos que tornam o ícone invisível à acessibilidade e à
      // navegação por teclado — ver o docblock do módulo.
      aria-hidden="true"
      focusable="false"
      role="presentation"
    >
      {COM_CIRCULO.has(nome) && <circle cx="10" cy="10" r="7" />}
      <path d={TRACADO[nome]} />
    </svg>
  )
}
