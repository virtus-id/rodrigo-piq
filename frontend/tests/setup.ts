/**
 * Setup do Vitest — `.claude/instructions/testing.instructions.md`.
 *
 * Os matchers do jest-dom e a limpeza entre testes só fazem sentido quando
 * há DOM. O padrão deste projeto é `environment: 'node'` (ver
 * `vite.config.ts`): teste de lógica pura não carrega DOM nenhum. Um teste
 * de componente pede DOM no próprio arquivo, por docblock:
 *
 *     // @vitest-environment happy-dom
 *
 * Por isso o carregamento abaixo é condicional — importar
 * `@testing-library/react` sem `document` quebraria antes de qualquer teste
 * rodar.
 *
 * **`happy-dom`, não `jsdom`**: a cadeia de dependências do jsdom quebra
 * neste Node 22.9 com `ERR_REQUIRE_ESM` em `@csstools/css-calc` (verificado
 * isoladamente, fora do Vitest).
 *
 * Nenhum mock global de rede aqui: cada teste declara o que intercepta,
 * para que nunca reste dúvida sobre qual resposta está sendo exercitada.
 */
if (typeof document !== 'undefined') {
  await import('@testing-library/jest-dom/vitest')
  const { cleanup } = await import('@testing-library/react')
  const { afterEach } = await import('vitest')

  afterEach(() => {
    cleanup()
  })
}
