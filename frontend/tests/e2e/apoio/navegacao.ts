/**
 * Navegação dos E2E, em um lugar só — `RF-57`, `AC-84`, `AC-86` (T-152).
 *
 * **Por que este arquivo existe.** Até a Rodada 4 cada teste abria uma tela
 * com `page.goto('/?caso=X')` seguido de um clique num botão da barra de sete
 * abas. Quando a barra morreu (`T-149`), os 18 blocos `test` quebraram no
 * mesmo instante — 18 edições para uma mudança de navegação. O objetivo
 * declarado em `plans/app-aluno.plan.md` §R5.6 é que a **próxima** mudança de
 * navegação seja uma edição em UM arquivo, e este é o arquivo.
 *
 * Nenhum seletor de navegação vive fora daqui.
 */
import { expect, type Page } from '@playwright/test'

/**
 * O payload de `GET /caso/{id}/inicio` — forma EXATA de
 * `app/http/rotas_inicio.py::inicio_do_caso`, espelhado em
 * `frontend/src/tipos.ts::Inicio`.
 *
 * Todo valor monetário é `string` ou `null`, nunca `number`: `RF-13` proíbe
 * dinheiro em ponto flutuante, e `JSON.parse` faria a conversão em silêncio.
 */
export interface InicioDeTeste {
  CASO_ID: string
  estado: string
  fase: 'coleta' | 'revisao' | 'reprovado' | 'plano' | 'acompanhamento'
  mensagem: string
  proxima_etapa: {
    destino:
      | 'consentimento'
      | 'pergunta'
      | 'calculando'
      | 'aguardando'
      | 'progresso'
      | 'bloco10'
      | 'acoes'
      | 'plano'
    ID_PERGUNTA: string | null
    item_id: string | null
  }
  progresso: { respondidas: number; total: number }
  valor_em_destaque: string | null
  plano_liberado: boolean
  versao_do_plano: number | null
}

/** O caso em coleta — a fase de longe mais comum nos testes. */
export function inicioEmColeta(casoId: string): InicioDeTeste {
  return {
    CASO_ID: casoId,
    estado: 'COLETA_INICIAL',
    fase: 'coleta',
    mensagem: 'Sua coleta está em andamento.',
    proxima_etapa: { destino: 'pergunta', ID_PERGUNTA: 'B5.B03', item_id: 'D001' },
    progresso: { respondidas: 62, total: 195 },
    valor_em_destaque: null,
    plano_liberado: false,
    versao_do_plano: null,
  }
}

interface OpcoesDaBase {
  /** Sobrescreve campos do payload de `/inicio` — fase, destino, progresso. */
  inicio?: Partial<InicioDeTeste>
  /**
   * `true` faz `POST /api/conta/login` devolver `e_revisor: true` — `AC-80`,
   * `AC-87`. Sem isso a interface trata a conta como não-revisora, que é o
   * lado seguro de `App.tsx`.
   */
  eRevisor?: boolean
}

/**
 * Intercepta o que TODA tela do fluxo consulta.
 *
 * ⚠️ **`/caso/*\/inicio` é interceptada SEMPRE**, mesmo nos testes que não a
 * verificam — regra de §R5.6 do plano. Sem o intercept, o proxy do Vite tenta
 * alcançar o FastAPI em `https://localhost:8443` (que não está no ar durante
 * os E2E), falha, e o teste trava até o timeout em vez de falhar dizendo o
 * que faltou.
 *
 * O login também é interceptado: é o único lugar de onde o papel da conta
 * chega ao cliente (`RF-59`), e `App.tsx` o mantém em estado.
 */
export async function interceptarBase(
  page: Page,
  caso: string,
  opcoes: OpcoesDaBase = {},
): Promise<void> {
  const inicio: InicioDeTeste = { ...inicioEmColeta(caso), ...(opcoes.inicio ?? {}) }

  await page.route(`**/caso/${caso}/inicio`, async (rota) => {
    await rota.fulfill({ json: inicio })
  })

  await page.route('**/api/conta/login', async (rota) => {
    await rota.fulfill({
      json: {
        email: 'aluno@exemplo.gov.br',
        conta_id: 'CONTA-E2E',
        e_revisor: opcoes.eRevisor === true,
      },
    })
  })

  // `T-160`: a tela de pergunta consulta `/respostas` para saber se há
  // pergunta anterior (`RF-70`, `AC-105`), e a de revisão vive dela. Entra
  // aqui pela MESMA regra de §R5.6 que trouxe `/inicio` e `/api/conta/eu`:
  // toda rota que a carga de uma tela dispara é interceptada, verificada pelo
  // teste ou não — senão o proxy do Vite tenta o FastAPI que não está no ar e
  // o teste queima segundos até o timeout.
  //
  // O padrão são as cinco partes VAZIAS: é o estado que não oferece "anterior"
  // (`AC-105`, segundo pé) e portanto não muda nenhum teste que não pediu a
  // navegação para trás. Quem quer respostas chama `interceptarRespostas`
  // depois — a última rota registrada vence no Playwright.
  await page.route(`**/caso/${caso}/respostas`, async (rota) => {
    await rota.fulfill({ json: { CASO_ID: caso, partes: partesVazias() } })
  })

  // `T-154`: o `App` pergunta quem é a sessão na carga da página. Sem este
  // intercept, cada teste espera o proxy do Vite desistir de alcançar o
  // backend antes de seguir — o `.catch` degrada e o teste passa, mas gasta
  // segundos por caso e enche o log de `afterConnectMultiple`. É exatamente a
  // armadilha que `plans/app-aluno.plan.md` §R5.6 manda antecipar: toda rota
  // que a carga da tela dispara entra aqui, verificada pelo teste ou não.
  await page.route('**/api/conta/eu', async (rota) => {
    await rota.fulfill({
      json: {
        email: 'aluno@exemplo.gov.br',
        conta_id: 'CONTA-E2E',
        e_revisor: opcoes.eRevisor === true,
        CASO_ID: caso,
        casos: [caso],
      },
    })
  })
}

/**
 * Abre uma tela direto pelo hash e espera a casca estar montada.
 *
 * O hash É a rota (`frontend/src/navegacao.ts::hashParaRota`), então não há
 * clique de navegação a dar: o estado inicial de `useRota` já lê
 * `window.location.hash`. A espera pelo `<h1>` é o que separa "a página
 * carregou" de "a tela renderizou" — sem ela a asserção seguinte corre contra
 * o primeiro paint.
 */
export async function abrirTela(page: Page, caso: string, rota: string): Promise<void> {
  await page.goto(`/?caso=${caso}#${rota}`)
  await expect(page.locator('h1')).toBeAttached()
}

/**
 * A ação principal da tela — o rodapé `.acoes` da casca, nunca o corpo.
 *
 * Buscar por papel na página inteira acharia um botão homônimo do conteúdo;
 * o que `AC-85` promete é o botão DO RODAPÉ, e é ele que os testes acionam.
 */
export function acaoPrincipal(page: Page, rotulo: string | RegExp) {
  return page.locator('.acoes').getByRole('button', { name: rotulo })
}

/** O "‹ Voltar" do topo da casca — o único caminho de volta que o aluno tem. */
export function voltarDaTela(page: Page) {
  return page.locator('.top button.back')
}

// ---------------------------------------------------------------------------
// A revisão das respostas — `RF-68`, `AC-100`..`AC-105` (T-160)
// ---------------------------------------------------------------------------

/**
 * O payload de `GET /caso/{id}/respostas` — forma EXATA de
 * `app/http/rotas_respostas.py::respostas_do_caso`, espelhada em
 * `frontend/src/tipos.ts::RespostasDoCaso`.
 *
 * Os `enunciado` e `valores` daqui são INVENTADOS de propósito: copiar a
 * redação real do questionário para um arquivo de teste criaria a segunda
 * fonte de verdade que `AC-37`/`AC-73` existem para impedir. O que o teste
 * prova é a estrutura — pergunta ao lado do valor —, não o texto.
 */
export interface RespostaDadaDeTeste {
  ID: string
  item_id: string | null
  enunciado: string
  respondida_como_nao_sei: boolean
  valores: string[]
}

export interface ParteDeTeste {
  bloco: number
  rotulo: string
  total_de_perguntas: number
  respondidas: RespostaDadaDeTeste[]
}

/**
 * Os cinco rótulos que o SERVIDOR devolve (`_PARTES` de `rotas_respostas.py`),
 * na ordem dos blocos. Vivem aqui porque são payload de teste, não redação do
 * cliente: a tela os desenha, nunca os escolhe.
 */
export const ROTULOS_DAS_PARTES: readonly string[] = [
  'Seu compromisso',
  'Como você controla os gastos',
  'O que entra e o que sai por mês',
  'Salário, margem e o que você tem',
  'Suas dívidas, uma por uma',
]

/**
 * As cinco partes, todas vazias — o esqueleto de `AC-101`.
 *
 * **As cinco vêm SEMPRE**, é contrato da rota. Um helper que devolvesse só as
 * preenchidas faria os testes concordarem com um servidor que não existe.
 */
export function partesVazias(): ParteDeTeste[] {
  return ROTULOS_DAS_PARTES.map((rotulo, indice) => ({
    bloco: indice + 1,
    rotulo,
    total_de_perguntas: 10,
    respondidas: [],
  }))
}

/** Intercepta `GET /caso/{id}/respostas` com as partes dadas. */
export async function interceptarRespostas(
  page: Page,
  caso: string,
  partes: ParteDeTeste[],
): Promise<void> {
  await page.route(`**/caso/${caso}/respostas`, async (rota) => {
    await rota.fulfill({ json: { CASO_ID: caso, partes } })
  })
}

/**
 * Entra como revisor e cai no Início — `RF-59`, `AC-80`, `AC-87`.
 *
 * `#entrada` com `?caso=` na URL é o único caminho: `App.tsx` lê o `CASO_ID`
 * da busca UMA vez, na montagem, então logar sem caso na URL deixaria o caso
 * vazio para todas as telas seguintes. Depois do login a rota vira `#inicio`,
 * e daí o teste navega para onde quiser.
 */
export async function entrarComoRevisor(page: Page, caso: string): Promise<void> {
  await abrirTela(page, caso, 'entrada')
  await page.getByLabel('Seu e-mail').fill('revisor@exemplo.gov.br')
  await page.getByLabel('Sua senha').fill('senha-de-teste')
  await acaoPrincipal(page, 'Entrar').click()
  await expect(page.getByRole('heading', { name: 'Início' })).toBeVisible()
}
