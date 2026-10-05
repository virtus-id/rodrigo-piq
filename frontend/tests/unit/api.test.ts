/**
 * O cliente mostra a recusa do servidor — `T-337`.
 *
 * O `HTTPException` do FastAPI manda `{"detail": "..."}`, e não `erro`: sem
 * lê-lo, o `409` da conferência chegava à tela como "HTTP 409".
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ErroHttp, retomarEdicao } from '../../src/services/api'

afterEach(() => {
  vi.restoreAllMocks()
})

function responder(status: number, corpo: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => corpo }),
  )
}

describe('pedir — mensagem da recusa', () => {
  it('lê o `detail` do HTTPException (409 da conferência)', async () => {
    responder(409, { detail: 'O aluno retirou este plano para editar.' })
    await expect(retomarEdicao('C1')).rejects.toMatchObject({
      status: 409,
      detalhe: 'O aluno retirou este plano para editar.',
    })
  })

  it('`erro` continua ganhando de `detail`', async () => {
    responder(409, { erro: 'Seu plano não está em conferência.', detail: 'outra coisa' })
    await expect(retomarEdicao('C1')).rejects.toBeInstanceOf(ErroHttp)
    await expect(retomarEdicao('C1')).rejects.toMatchObject({
      detalhe: 'Seu plano não está em conferência.',
    })
  })

  it('sem corpo legível, fica o status', async () => {
    responder(500, null)
    await expect(retomarEdicao('C1')).rejects.toMatchObject({ detalhe: 'HTTP 500' })
  })
})
