/**
 * Playwright — `.claude/instructions/testing.instructions.md` (T-138).
 *
 * As partes daquele arquivo que se aplicam a este projeto: testes em
 * `tests/e2e/`, nomeados `*.spec.ts`, rede interceptada com `page.route`
 * para determinismo, e ao menos um teste em viewport mobile. As partes que
 * NÃO se aplicam são as do domínio (buscar cidade, trocar unidade,
 * previsão): descrevem um app de previsão do tempo, de outro projeto.
 *
 * O viewport mobile é 360×740 de propósito — a persona do PIQ é um servidor
 * público respondendo com o celular na mão e o contracheque ao lado, e 360px
 * é a largura que a NFR de responsividade fixa.
 */
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.spec.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list']],
  use: {
    // `localhost`, não `127.0.0.1`: é o que o Vite anuncia, e no Windows os
    // dois podem resolver diferente (IPv6 `::1` vs IPv4). Apontar para o
    // endereço errado faz o Playwright esperar 120s por um servidor que
    // está no ar.
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    // O servidor de desenvolvimento faz proxy para o FastAPI sobre TLS com
    // certificado autoassinado.
    ignoreHTTPSErrors: true,
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile-360',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 360, height: 740 },
        isMobile: false,
      },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
