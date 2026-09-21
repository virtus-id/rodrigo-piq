/**
 * Máscara de entrada por `TipoResposta` — `RF-47`, `RF-48` (T-137).
 *
 * **A regra que governa este arquivo: formata, NUNCA corrige.**
 *
 * A autoridade sobre o que é um número válido é `app/montagem/conversao.py`,
 * no servidor. Este módulo existe só para o aluno VER o valor se formando
 * enquanto digita. Entrada ambígua (`"1.2,3"`) segue como digitada, vai ao
 * servidor e é recusada lá com `400`, sem gravação (`AC-77`, `EC-01`). Uma
 * máscara que "consertasse" o ambíguo criaria uma segunda regra de parsing
 * no cliente — exatamente o que o plano evita ao manter a conversão num
 * lugar só.
 *
 * As saídas abaixo são as MESMAS da tabela de `tests/app_aluno/
 * test_mascaras.py`, que prova em Python que cada uma é aceita por
 * `converter_para_dinheiro`/`converter_para_taxa`. Se este arquivo divergir
 * daquela tabela, o aluno digita, vê o campo formatado e leva `400` — o pior
 * dos mundos.
 */
import type { TipoResposta } from './tipos'

/** Só dígitos. Descarta o que `_CARACTERES_ACEITOS` recusaria de qualquer
 *  forma (`R$`, espaço, letra) — `EC-22`: colar `"R$ 1.234,56"` dá o mesmo
 *  resultado que teclar os dígitos. */
function apenasDigitos(texto: string): string {
  return texto.replace(/\D/g, '')
}

/** Agrupamento de milhar da leitura brasileira: primeiro grupo de 1 a 3
 *  dígitos, os seguintes com exatamente 3 — mesmo critério de
 *  `conversao.py::_milhar_valido`. */
function agruparMilhar(inteiro: string): string {
  return inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
}

/**
 * `MOEDA` → `1.234,56`.
 *
 * Os dois últimos dígitos são os centavos: o aluno digita da direita para a
 * esquerda num campo de dinheiro, como numa calculadora.
 */
export function formatarMoeda(bruto: string): string {
  let digitos = apenasDigitos(bruto)
  if (digitos === '') return ''
  while (digitos.length < 3) digitos = `0${digitos}`
  const inteiro = digitos.slice(0, -2).replace(/^0+(?=\d)/, '')
  return `${agruparMilhar(inteiro)},${digitos.slice(-2)}`
}

/**
 * `TAXA` → `4,5` (percentual, sem o símbolo).
 *
 * `converter_para_taxa` divide por 100 e `_CARACTERES_ACEITOS` recusa `%`:
 * 4,5% a.m. submete `"4,5"`, nunca `"0,045"` e nunca com o símbolo. O `%` é
 * sufixo VISUAL, renderizado fora do `<input>` (`AC-76`).
 *
 * Sem agrupamento de milhar: uma taxa mensal não chega a mil por cento, e
 * agrupar só criaria chance de emitir algo que o servidor recusaria.
 */
export function formatarTaxa(bruto: string): string {
  const texto = bruto.replace(/[^\d,]/g, '')
  const partes = texto.split(',')
  if (partes.length === 1) return partes[0]
  return `${partes[0]},${partes.slice(1).join('').slice(0, 2)}`
}

export function formatarInteiro(bruto: string): string {
  return apenasDigitos(bruto)
}

/** Os tipos que têm máscara. Os demais (seleções, texto livre, data nativa)
 *  passam direto — `DATA` usa `<input type="date">`, que já é ISO. */
const COM_MASCARA: ReadonlySet<TipoResposta> = new Set<TipoResposta>([
  'MOEDA',
  'TAXA',
  'NUMERO',
  'ESCALA_0_10',
])

export function temMascara(tipo: TipoResposta): boolean {
  return COM_MASCARA.has(tipo)
}

/** Aplica a máscara do tipo. Tipo sem máscara devolve o texto intacto. */
export function aplicarMascara(tipo: TipoResposta, bruto: string): string {
  switch (tipo) {
    case 'MOEDA':
      return formatarMoeda(bruto)
    case 'TAXA':
      return formatarTaxa(bruto)
    case 'NUMERO':
    case 'ESCALA_0_10':
      return formatarInteiro(bruto)
    default:
      return bruto
  }
}

/**
 * Uma string decimal do servidor (`"3000.00"`) → texto exibível
 * (`"3.000,00"`) — `RF-13` (T-150).
 *
 * **Por que não `Number()` nem `parseFloat`.** É o ponto flutuante que `RF-13`
 * proíbe em todo o sistema, e "só para exibir" é exatamente como o float
 * entra num lugar que o recusou em toda parte: `0.1 + 0.2` não é `0.3`, e um
 * centavo errado na tela do plano é um centavo que o aluno não reconhece.
 * Aqui a conversão é manipulação de STRING: separa inteiro de centavos pelo
 * ponto e entrega os dígitos a `formatarMoeda`, a mesma máscara da digitação.
 *
 * Tolera as formas que o servidor pode emitir: `"100"` (sem casas),
 * `"12.5"` (uma casa), `"0.05"`. `null` e vazio devolvem vazio — a ausência
 * de valor nunca vira `R$ 0,00` (`AC-70`: desconhecido não é zero).
 */
export function formatarDecimalDoServidor(valor: string | null): string {
  if (!valor) return ''
  const [inteiro = '0', centavos = ''] = valor.split('.')
  return formatarMoeda(inteiro + centavos.padEnd(2, '0').slice(0, 2))
}
