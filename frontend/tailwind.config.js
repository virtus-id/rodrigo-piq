/**
 * Tema do Tailwind — os tokens do protótipo validado `PIQ Meu Plano`
 * (`RF-50`, T-132).
 *
 * Os valores abaixo são os do protótipo, caractere por caractere. NÃO são
 * escolha de estilo desta tarefa: foram validados com stakeholders, e a
 * tipografia em particular é decisão de acessibilidade — `Atkinson
 * Hyperlegible` foi desenhada para baixa visão, e a persona é um servidor
 * público lendo o contracheque no celular.
 *
 * **`.claude/instructions/tailwind.instructions.md` NÃO se aplica aqui.**
 * Aquele arquivo descreve um app de previsão do tempo ("tema dark
 * glassmorphism", `text-sun`, "hero grande para temperatura", "previsão de 5
 * dias"): é de outro projeto. Seguir seu tema contrariaria `RF-50` e
 * reduziria o contraste que a persona precisa. Registrado em
 * `plans/app-aluno.plan.md` §2 (revisão de 2026-09-15).
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#FAFAF7',
        surface: '#FFFFFF',
        ink: '#1B2A2F',
        muted: '#5E6E72',
        line: '#D9E0DC',
        accent: {
          DEFAULT: '#0F6E56',
          ink: '#FFFFFF',
          soft: '#E3F1EB',
        },
        warn: {
          DEFAULT: '#8A5A00',
          soft: '#FFF4DC',
        },
        bad: {
          DEFAULT: '#A63A2C',
          soft: '#FBE8E4',
        },
      },
      fontFamily: {
        sans: ['"Atkinson Hyperlegible"', '"Segoe UI"', 'Arial', 'sans-serif'],
        serif: ['"Source Serif 4"', 'Georgia', '"Times New Roman"', 'serif'],
      },
      borderRadius: {
        piq: '14px',
      },
      minHeight: {
        // Alvos de toque do protótipo: botão 56px, opção 60px, botão
        // discreto 48px. São medidas de acessibilidade, não estética.
        botao: '56px',
        opcao: '60px',
        toque: '48px',
      },
      maxWidth: {
        // A coluna de leitura do protótipo.
        tela: '560px',
        equipe: '900px',
      },
    },
  },
  plugins: [],
}
