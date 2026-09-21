# Frontend — App do Aluno (PIQ)

A interface React do PIQ: coleta, plano, acompanhamento e as telas da equipe
(fila de conferência, conferência do caso, painel do operador).

Rastreia `RF-50` a `RF-78` de [`specs/app-aluno.spec.md`](../specs/app-aluno.spec.md).

## Comandos

```bash
npm run dev        # servidor de desenvolvimento (proxy para https://localhost:8443)
npm run build      # tsc -b && vite build
npm run typecheck  # tsc -b --noEmit
npm test           # vitest (unitários)
npm run test:e2e   # playwright (desktop + mobile-360)
```

O `dev` faz proxy de `/api`, `/caso`, `/conta`, `/revisao` e `/operador` para a
aplicação FastAPI servida por `scripts/subir_demo.py`. O certificado de
desenvolvimento é autoassinado (`secure: false` no proxy do Vite) — isso vale
**apenas** para o proxy local; a exigência de HTTPS da aplicação não é
afrouxada em lugar nenhum.

## Estrutura

| Caminho | Responsabilidade |
| --- | --- |
| `src/componentes/Tela.tsx` | A casca de três partes (`.top` / `.corpo` / `.acoes`) por onde passam **todas** as telas (`AC-82`) |
| `src/componentes/` | `Botao`, `CampoPergunta`, `Icone`, `Esqueleto`, `TrilhaDaJornada` |
| `src/telas/` | Uma tela por arquivo, nomeadas pelo que mostram |
| `src/services/api.ts` | A única porta para o servidor |
| `src/mascaras.ts` | Máscara de dinheiro — espelhada em `tests/app_aluno/test_mascaras.py` |
| `src/index.css` | Tokens, elevação e as classes de componente que se repetem |
| `tailwind.config.js` | Os tokens do protótipo validado — **não editar** (ver abaixo) |

## O que não se muda sem decisão registrada

Esta interface tem valores que são **contrato**, não escolha de implementação.
Vários estão verificados por teste, com erro explícito quando alguém os toca:

- **Os onze tokens de cor** (`tailwind.config.js`). Sete pares são auditados
  contra WCAG 2.1 AA em `tests/app_aluno/e2e/test_acessibilidade_coleta.py`, e
  os nomes e valores em `tests/app_aluno/estatica/test_tokens_intactos.py`.
- **Atkinson Hyperlegible** — desenhada para baixa visão. A persona é um
  servidor público lendo o contracheque no celular; trocá-la **não é neutro**.
- **Os alvos de toque** (56 / 60 / 48 px) e a base de 19 px.
- **As larguras** 560 px (aluno) e 900 px (equipe), verificadas por string
  exata em `tests/e2e/navegacao.spec.ts`.
- **Os nomes de classe** `.top`, `.corpo`, `.acoes`, `.back`, `.linha`,
  `.cartao-proximo`, `.item`, `.chip` — a suíte E2E os usa como seletor.
- **A ordem de foco da tela de pergunta**: do campo até "Continuar", no máximo
  **2 Tabs** (`tests/e2e/coleta.spec.ts`). Nenhum elemento focável novo entra
  nesse trecho — é por isso que `Icone` emite todo SVG como `aria-hidden` e
  `focusable="false"`, sem prop que permita o contrário.
- **A trilha da jornada é informativa, nunca navegável** (`AC-115`): tornar os
  degraus clicáveis restabeleceria a barra de abas que `RF-57`/`AC-83` mataram.

Para mudar qualquer um destes, a rota é `/sdd:spec` — não a edição direta.

## Acabamento visual (Rodada 8)

A camada de elevação, hierarquia tipográfica, ícones, esqueletos de
carregamento e micro-interação é **aditiva** (`RF-78`): nenhum token, nome de
classe ou largura validada foi alterado. Ver `plans/app-aluno.plan.md` §R8.

Duas convenções que vêm de lá:

- **Sombra deriva de `ink`**, nunca de preto neutro (`AC-108`). Preto puro
  sobre o fundo quente da paleta lê como sujeira cinza.
- **Regra de `prefers-reduced-motion` vai no fim de `@layer components`.** O
  Tailwind emite os componentes na ordem do arquivo, e uma regra só vence
  outra de mesma especificidade se vier depois — um bloco escrito no meio é
  sobrescrito pela base que vem abaixo, e o movimento continua rodando para
  quem pediu que não rodasse.
