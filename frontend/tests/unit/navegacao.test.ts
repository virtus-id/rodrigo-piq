/**
 * `navegacao.ts` — ida e volta entre `Rota` e hash (`T-203`, `EC-26`).
 *
 * O defeito: `{ tela: 'pergunta', itemId: 'D001' }` virava `#pergunta/D001`,
 * e `D001` voltava como ID de pergunta — a ficha abria num `404`.
 */
import { describe, expect, it } from 'vitest'

import { hashParaRota, rotaParaHash, type Rota } from '../../src/navegacao'

describe('rotaParaHash ↔ hashParaRota', () => {
  const casos: Rota[] = [
    { tela: 'pergunta', itemId: 'D001' },
    { tela: 'pergunta', idPergunta: 'B5.A01' },
    { tela: 'pergunta', idPergunta: 'B5.A01', itemId: 'D001' },
    { tela: 'pergunta' },
    { tela: 'respostas', itemId: 'D001' },
    { tela: 'respostas', idPergunta: 'B1.01' },
    { tela: 'respostas' },
    { tela: 'fichas' },
    { tela: 'fichas', escopo: 'RENDA_ADICIONAL_ID' },
    { tela: 'fichas', escopo: 'VINCULO_ID', seguintes: ['MARGEM_ID'] },
  ]

  it.each(casos)('volta idêntica: %o', (rota) => {
    expect(hashParaRota(rotaParaHash(rota))).toEqual(rota)
  })

  it('só com itemId preserva o segmento vazio da pergunta', () => {
    expect(rotaParaHash({ tela: 'pergunta', itemId: 'D001' })).toBe('pergunta//D001')
    expect(hashParaRota('#pergunta//D001')).toEqual({ tela: 'pergunta', itemId: 'D001' })
  })

  it('sem parâmetros continua curta', () => {
    expect(rotaParaHash({ tela: 'pergunta' })).toBe('pergunta')
    expect(rotaParaHash({ tela: 'pergunta', idPergunta: 'B1.01' })).toBe('pergunta/B1.01')
  })
})

describe('fichas com escopo (T-212)', () => {
  it('sem escopo continua `#fichas`, com escopo carrega o nome', () => {
    expect(rotaParaHash({ tela: 'fichas' })).toBe('fichas')
    expect(rotaParaHash({ tela: 'fichas', escopo: 'MARGEM_ID' })).toBe('fichas/MARGEM_ID')
    expect(hashParaRota('#fichas/VINCULO_ID/MARGEM_ID')).toEqual({
      tela: 'fichas',
      escopo: 'VINCULO_ID',
      seguintes: ['MARGEM_ID'],
    })
  })
})
