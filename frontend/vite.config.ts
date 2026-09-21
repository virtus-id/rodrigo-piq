/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

/**
 * `RF-51` (T-132) — o front conversa com a API real do FastAPI.
 *
 * O proxy aponta para `https://localhost:8443` (a aplicação servida por
 * `scripts/subir_demo.py`). `secure: false` porque o certificado de
 * desenvolvimento é autoassinado — isso vale **apenas** para o proxy do Vite
 * em desenvolvimento; a exigência de HTTPS da aplicação não é afrouxada em
 * lugar nenhum, e o cookie de sessão continua `Secure`.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'https://localhost:8443',
        changeOrigin: true,
        secure: false,
      },
      '/caso': {
        target: 'https://localhost:8443',
        changeOrigin: true,
        secure: false,
      },
      '/conta': {
        target: 'https://localhost:8443',
        changeOrigin: true,
        secure: false,
      },
      '/revisao': {
        target: 'https://localhost:8443',
        changeOrigin: true,
        secure: false,
      },
      '/operador': {
        target: 'https://localhost:8443',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  test: {
    // `node` por padrão, de propósito: teste de lógica pura (máscara,
    // serialização) não carrega DOM nenhum — mais rápido, e imune à cadeia
    // de dependências do jsdom, que neste Node 22.9 quebra com
    // `ERR_REQUIRE_ESM` em `@csstools/css-calc` (verificado isoladamente).
    //
    // Teste de COMPONENTE pede DOM por docblock no próprio arquivo:
    //     // @vitest-environment happy-dom
    // `environmentMatchGlobs` não existe mais no Vitest 4; o docblock é
    // local ao arquivo que precisa, que é melhor do que config global.
    environment: 'node',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/unit/**/*.test.{ts,tsx}'],
  },
})
