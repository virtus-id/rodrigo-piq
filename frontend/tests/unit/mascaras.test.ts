/**
 * A máscara do cliente concorda com a fronteira do servidor — `RF-47`,
 * `AC-75`, `AC-76`, `AC-77` (T-137).
 *
 * **Esta tabela é a MESMA de `tests/app_aluno/test_mascaras.py`**, onde cada
 * saída é submetida a `converter_para_dinheiro`/`converter_para_taxa` e
 * provada aceita, produzindo o `Decimal` esperado. Aqui provamos o outro
 * lado: que o TypeScript produz exatamente essas saídas.
 *
 * As duas metades juntas fecham o contrato. Se divergirem, o aluno digita,
 * vê o campo formatado bonito, e leva `400` do servidor.
 */
import { describe, expect, it } from 'vitest'

import {
  aplicarMascara,
  formatarDecimalDoServidor,
  formatarMoeda,
  formatarTaxa,
  temMascara,
} from '../../src/mascaras'

describe('MOEDA', () => {
  // (digitado, exibido) — a coluna do Decimal esperado vive no teste Python.
  const casos: ReadonlyArray<readonly [string, string]> = [
    ['123456', '1.234,56'],
    ['100', '1,00'],
    ['5', '0,05'],
    ['50', '0,50'],
    ['999', '9,99'],
    ['100000', '1.000,00'],
    ['123456789', '1.234.567,89'],
    ['820000', '8.200,00'],
  ]

  it.each(casos)('digitar %s exibe %s', (digitado, exibido) => {
    expect(formatarMoeda(digitado)).toBe(exibido)
  })

  it('campo vazio continua vazio — nunca vira 0,00', () => {
    expect(formatarMoeda('')).toBe('')
  })

  it('EC-22: colar "R$ 1.234,56" dá o mesmo que teclar os dígitos', () => {
    expect(formatarMoeda('R$ 1.234,56')).toBe(formatarMoeda('123456'))
  })
})

describe('TAXA', () => {
  const casos: ReadonlyArray<readonly [string, string]> = [
    ['4,5', '4,5'],
    ['12', '12'],
    ['0,99', '0,99'],
    ['2,75', '2,75'],
  ]

  it.each(casos)('digitar %s exibe %s', (digitado, exibido) => {
    expect(formatarTaxa(digitado)).toBe(exibido)
  })

  it('AC-76: nunca emite o caractere %, que o servidor recusa', () => {
    expect(formatarTaxa('4,5%')).not.toContain('%')
    expect(formatarTaxa('4,5%')).toBe('4,5')
  })

  it('AC-76: envia o percentual, não a fração — 4,5 nunca vira 0,045', () => {
    expect(formatarTaxa('4,5')).toBe('4,5')
  })

  it('limita a duas casas decimais', () => {
    expect(formatarTaxa('4,5678')).toBe('4,56')
  })
})

describe('a máscara formata, nunca corrige', () => {
  it('AC-77: entrada ambígua NÃO é "salva" — vai ao servidor e é recusada lá', () => {
    // "1.2,3" é ambíguo para `_milhar_valido`. A máscara não tem o direito
    // de adivinhar o que o aluno quis dizer; ela reduz aos dígitos e o
    // servidor decide. O que ela jamais pode fazer é inventar um valor
    // válido diferente do que foi digitado.
    const formatado = formatarMoeda('1.2,3')
    expect(formatado).toBe('1,23')
    // E o que importa: o resultado vem SÓ dos dígitos, sem interpretar os
    // separadores originais.
    expect(formatado).toBe(formatarMoeda('123'))
  })
})

describe('quais tipos têm máscara', () => {
  it('MOEDA, TAXA, NUMERO e ESCALA_0_10 têm', () => {
    expect(temMascara('MOEDA')).toBe(true)
    expect(temMascara('TAXA')).toBe(true)
    expect(temMascara('NUMERO')).toBe(true)
    expect(temMascara('ESCALA_0_10')).toBe(true)
  })

  it('seleções, texto e data não têm — DATA usa <input type=date>, já ISO', () => {
    expect(temMascara('SELECAO_UNICA')).toBe(false)
    expect(temMascara('SELECAO_MULTIPLA')).toBe(false)
    expect(temMascara('TEXTO_CURTO')).toBe(false)
    expect(temMascara('SIM_NAO_TALVEZ')).toBe(false)
    expect(temMascara('DATA')).toBe(false)
  })

  it('tipo sem máscara passa o texto intacto', () => {
    expect(aplicarMascara('TEXTO_CURTO', 'Casa da Maria')).toBe('Casa da Maria')
    expect(aplicarMascara('DATA', '2026-03-15')).toBe('2026-03-15')
  })
})

describe('formatarDecimalDoServidor — RF-13 na saída', () => {
  // A tabela cobre o que o servidor REALMENTE emite: `Decimal` serializado
  // por `str(...)`, que produz casas variáveis conforme o valor.
  it.each([
    ['3000.00', '3.000,00'],
    ['0.50', '0,50'],
    ['0.05', '0,05'],
    ['1234567.89', '1.234.567,89'],
    ['100', '100,00'],
    ['12.5', '12,50'],
    ['0.00', '0,00'],
    ['999999999.99', '999.999.999,99'],
  ])('%s vira %s', (doServidor, esperado) => {
    expect(formatarDecimalDoServidor(doServidor)).toBe(esperado)
  })

  it('AC-70: ausência de valor devolve vazio, nunca R$ 0,00', () => {
    // Desconhecido não é zero. Um `0,00` aqui seria uma afirmação sobre o
    // dinheiro do aluno que ninguém calculou.
    expect(formatarDecimalDoServidor(null)).toBe('')
    expect(formatarDecimalDoServidor('')).toBe('')
  })

  it('RF-13: a conversão não passa por float', () => {
    // `0.1 + 0.2 !== 0.3` em ponto flutuante. Se a implementação usasse
    // `Number()`, um valor com muitas casas perderia precisão; como ela
    // manipula string, os dígitos chegam intactos.
    expect(formatarDecimalDoServidor('0.07')).toBe('0,07')
    expect(formatarDecimalDoServidor('70.07')).toBe('70,07')
    // Valor além do inteiro seguro de IEEE-754 (2^53): via float, o último
    // dígito mudaria.
    expect(formatarDecimalDoServidor('90071992547409.91')).toBe(
      '90.071.992.547.409,91',
    )
  })
})
