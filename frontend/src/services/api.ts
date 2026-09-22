/**
 * Cliente da API — a única camada que fala com o servidor (`RF-51`, T-136).
 *
 * `.claude/instructions/react.instructions.md`: efeitos colaterais ficam em
 * services, nunca no corpo do render. Nenhum componente faz `fetch`.
 *
 * **`credentials: 'include'` em toda chamada.** O isolamento por `CASO_ID` é
 * verificado no servidor a cada requisição, a partir do cookie de sessão
 * (`piq_sessao`, `Secure`+`HttpOnly`). Sem o cookie a resposta é `401`, e é
 * assim que deve ser: o cliente nunca decide a quem um caso pertence.
 */
import type {
  ConfirmacaoDeResposta,
  Etapas,
  Ficha,
  Inicio,
  ItemDaFila,
  ListaDeFichas,
  Pergunta,
  Plano,
  RespostaPergunta,
  RespostaPlano,
  RespostasDoCaso,
} from '../tipos'

export class ErroHttp extends Error {
  // Campos declarados e atribuídos no corpo: `erasableSyntaxOnly` do
  // `tsconfig.app.json` proíbe parâmetro-propriedade (`readonly` no
  // construtor), porque aquilo emite código em vez de ser só tipo.
  readonly status: number
  readonly detalhe: string

  constructor(status: number, detalhe: string) {
    super(detalhe)
    this.name = 'ErroHttp'
    this.status = status
    this.detalhe = detalhe
  }
}

const CABECALHO_JSON: Readonly<Record<string, string>> = {
  Accept: 'application/json',
}

async function pedir<T>(url: string, init: RequestInit = {}): Promise<T> {
  const resposta = await fetch(url, {
    credentials: 'include',
    ...init,
    headers: { ...CABECALHO_JSON, ...(init.headers ?? {}) },
  })

  if (!resposta.ok) {
    // O servidor nomeia o motivo (`{"erro": ...}`); quando não houver corpo
    // legível, o status já é a informação — nunca inventamos uma mensagem.
    let detalhe = `HTTP ${resposta.status}`
    try {
      const corpo = (await resposta.json()) as { erro?: string }
      if (corpo?.erro) detalhe = corpo.erro
    } catch {
      /* corpo não-JSON: fica o status */
    }
    throw new ErroHttp(resposta.status, detalhe)
  }

  return (await resposta.json()) as T
}

/**
 * A próxima pergunta não respondida E exibível.
 *
 * Quem decide qual é, e se alguma condicional a fecha, é o servidor
 * (`RF-52`). O cliente só desenha o que recebe.
 */
export function obterProximaPergunta(casoId: string): Promise<RespostaPergunta> {
  return pedir<RespostaPergunta>(`/caso/${casoId}/pergunta`)
}

export function obterPergunta(
  casoId: string,
  idPergunta: string,
  itemId?: string,
): Promise<RespostaPergunta> {
  const busca = itemId ? `?item_id=${encodeURIComponent(itemId)}` : ''
  return pedir<RespostaPergunta>(`/caso/${casoId}/pergunta/${idPergunta}${busca}`)
}

/**
 * Grava uma resposta.
 *
 * O corpo vai como `application/x-www-form-urlencoded` — não é descuido: a
 * rota do servidor lê com `parse_qsl` (stdlib) porque `python-multipart`
 * está deliberadamente fora do plano, e `SELECAO_MULTIPLA` depende de
 * `valor` REPETIDO, que JSON não expressa da mesma forma.
 */
export function gravarResposta(
  casoId: string,
  entrada: {
    idPergunta: string
    valor?: string | string[]
    itemId?: string | null
    naoSei?: boolean
  },
): Promise<ConfirmacaoDeResposta> {
  const corpo = new URLSearchParams()
  corpo.append('ID_PERGUNTA', entrada.idPergunta)
  if (entrada.itemId) corpo.append('item_id', entrada.itemId)
  if (entrada.naoSei) {
    corpo.append('nao_sei', 'on')
  } else if (Array.isArray(entrada.valor)) {
    for (const um of entrada.valor) corpo.append('valor', um)
  } else if (entrada.valor !== undefined) {
    corpo.append('valor', entrada.valor)
  }

  return pedir<ConfirmacaoDeResposta>(`/caso/${casoId}/resposta`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: corpo.toString(),
  })
}

/**
 * Tudo o que o aluno já respondeu, agrupado pelas cinco partes — `RF-68`,
 * `AC-100`, `AC-101` (T-160).
 *
 * **As cinco partes vêm SEMPRE**, mesmo as vazias: `AC-101` é do servidor, não
 * uma decisão que a tela toma ao filtrar. O cliente nunca soube quais
 * perguntas existem (`RF-45`) e continua não sabendo — ele desenha o que veio.
 *
 * É também a fonte da navegação para a pergunta anterior (`RF-70`): a ordem
 * das partes e das linhas dentro delas é a ordem dos registros no servidor, a
 * mesma que a coleta percorre. Ver a nota de `perguntaAnterior`.
 */
export function obterRespostasDoCaso(casoId: string): Promise<RespostasDoCaso> {
  return pedir<RespostasDoCaso>(`/caso/${casoId}/respostas`)
}

export function listarFichas(casoId: string, escopo: string): Promise<ListaDeFichas> {
  return pedir<ListaDeFichas>(`/caso/${casoId}/fichas/${escopo}`)
}

export function criarFicha(
  casoId: string,
  escopo: string,
): Promise<{ CASO_ID: string; escopo: string; ficha: Ficha }> {
  return pedir(`/caso/${casoId}/fichas/${escopo}`, { method: 'POST' })
}

export function removerFicha(
  casoId: string,
  escopo: string,
  itemId: string,
): Promise<{ removido: string }> {
  return pedir(`/caso/${casoId}/fichas/${escopo}/${itemId}`, { method: 'DELETE' })
}

/**
 * A fase do caso e a ÚNICA próxima etapa — `RF-58`, `RF-60` (T-147).
 *
 * Quem decide o que vem a seguir é o servidor. Esta função não interpreta a
 * fase para escolher destino: ela entrega o que veio, e `TelaInicio` desenha.
 */
export function obterInicio(casoId: string): Promise<Inicio> {
  return pedir<Inicio>(`/caso/${casoId}/inicio`)
}

/**
 * O papel da conta, devolvido pelo login — `RF-59`, `AC-80`.
 *
 * **É dica de interface, não autorização.** Serve para a interface não
 * oferecer ao aluno o caminho para a fila e o painel. Quem autoriza é o
 * servidor, que reconsulta o banco a cada requisição: forjar `e_revisor`
 * aqui não dá acesso a nada, só a telas que o servidor recusa.
 */
export interface SessaoDaConta {
  email: string
  conta_id: string
  e_revisor: boolean
  /** `null` para conta sem caso — nunca string vazia. */
  CASO_ID?: string | null
  casos?: string[]
}

/**
 * Quem é a sessão, e qual é o caso dela — `RF-02`, `RF-59` (T-154).
 *
 * **É o que faz a aplicação sobreviver a um F5.** Antes disso o `CASO_ID` só
 * existia na resposta do cadastro e no `?caso=` da URL: recarregar a página
 * perdia o caso, e o papel do revisor junto — o aluno voltava à tela de login
 * com a sessão já instalada. Agora a sessão responde as duas coisas, e o
 * servidor as lê do banco a cada chamada.
 *
 * `401` quando não há sessão: é o caminho normal de quem ainda não entrou,
 * não uma falha.
 */
export function obterSessao(): Promise<SessaoDaConta> {
  return pedir<SessaoDaConta>('/api/conta/eu')
}

export function entrar(email: string, senha: string): Promise<Response> {
  const corpo = new URLSearchParams({ email, senha })
  // `/api/conta/login`, não `/conta/login`: a rota JSON é a do frontend.
  // A HTML existia para o formulário Jinja2, que deixou de existir.
  return fetch('/api/conta/login', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: corpo.toString(),
  })
}

/**
 * Define a senha a partir do token do link — `T-179`.
 *
 * Serve ao PRIMEIRO ACESSO (o aluno comprou, a conta nasceu sem senha) e à
 * RECUPERAÇÃO. Os dois terminam na mesma rota: o fato é o mesmo — "provei
 * que sou dono deste e-mail, quero definir a senha".
 *
 * **Não instala sessão.** Depois disso o aluno entra pelo login normal, e a
 * senha que acabou de escolher é exercitada na hora.
 *
 * Devolve `Response` cru (como `entrar`) porque a tela precisa distinguir
 * `400` de senha curta de `400` de token inválido pela mensagem do corpo.
 */
export function definirSenha(token: string, senha: string): Promise<Response> {
  const corpo = new URLSearchParams({ token, senha })
  return fetch('/api/provisionamento/senha', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: corpo.toString(),
  })
}

// ---------------------------------------------------------------------------
// Plano, fila de revisão e etapas (T-140)
// ---------------------------------------------------------------------------

export function obterPlano(casoId: string): Promise<RespostaPlano> {
  return pedir<RespostaPlano>(`/caso/${casoId}/api/plano`)
}

export function obterEtapas(casoId: string): Promise<Etapas> {
  return pedir<Etapas>(`/caso/${casoId}/etapas`)
}

/** Abre uma etapa pós-plano. `409` quando a guarda do servidor a fecha —
 *  o cliente nunca decide se pode abrir. */
export function abrirEtapa(
  casoId: string,
  etapa: 'blocos-7-8' | 'bloco-10' | 'bloco-11',
): Promise<{ CASO_ID: string; estado: string }> {
  return pedir(`/caso/${casoId}/etapas/${etapa}`, { method: 'POST' })
}

export function obterFilaDeRevisao(): Promise<{ itens: ItemDaFila[] }> {
  return pedir<{ itens: ItemDaFila[] }>('/api/revisao/fila')
}

// ---------------------------------------------------------------------------
// Conferência de um caso — `RF-26`, `AC-27`, `AC-29` (T-150)
// ---------------------------------------------------------------------------

export interface CampoDeEntrada {
  nome: string
  valor: string
}

export interface EstadoInputs {
  campos: CampoDeEntrada[]
  perfil_comportamental: CampoDeEntrada[]
  sinais_comportamentais: CampoDeEntrada[]
  dividas: { DIVIDA_ID: string; campos: CampoDeEntrada[] }[]
}

export interface CasoParaRevisao {
  CASO_ID: string
  plano: Plano
  /** `AC-29`: vem na MESMA resposta do plano — ver a nota de `TelaEquipeCaso`. */
  estado_inputs: EstadoInputs
  fila: ItemDaFila
}

export function obterCasoParaRevisao(casoId: string): Promise<CasoParaRevisao> {
  return pedir<CasoParaRevisao>(`/api/revisao/caso/${casoId}`)
}

/**
 * As seis classificações de erro — `RF-26`, `OQ-12`.
 *
 * Vêm do servidor de propósito: `CLASSIFICACAO_ERRO` é enum fechado, e um
 * sétimo rótulo só pode nascer lá. Codificá-los aqui criaria uma segunda
 * lista, que divergiria no dia em que a primeira mudasse.
 */
export function obterOpcoesDeDecisao(
  casoId: string,
): Promise<{ classificacoes_erro: string[] }> {
  return pedir(`/revisao/caso/${casoId}/decisao`)
}

/**
 * Registra a decisão do revisor — `AC-27`, `EC-12`.
 *
 * **O autor NÃO vai no corpo.** Ele vem da sessão do revisor no servidor
 * (`exigir_papel_revisor`), e é essa origem que torna `AC-27` real: um campo
 * de formulário poderia ser preenchido com qualquer nome por quem envia a
 * requisição.
 *
 * `409` quando o caso já saiu de `AGUARDANDO_REVISAO` — alguém decidiu antes,
 * e uma segunda gravação silenciosa violaria a imutabilidade do registro.
 */
export function decidirRevisao(
  casoId: string,
  entrada: {
    decisao: 'LIBERAR' | 'REPROVAR'
    classificacaoErro?: string
    observacao?: string
  },
): Promise<unknown> {
  const corpo = new URLSearchParams({ decisao: entrada.decisao })
  if (entrada.classificacaoErro) {
    corpo.append('classificacao_erro', entrada.classificacaoErro)
  }
  if (entrada.observacao) corpo.append('observacao', entrada.observacao)

  return pedir(`/revisao/caso/${casoId}/decisao`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: corpo.toString(),
  })
}

// ---------------------------------------------------------------------------
// Consentimento, progresso e painel (T-141)
// ---------------------------------------------------------------------------

export function obterTextoDoConsentimento(
  casoId: string,
): Promise<{ CASO_ID: string; QUESTIONARIO_VERSION: string; titulo: string; corpo: string }> {
  return pedir(`/api/caso/${casoId}/consentimento`)
}

/** O aceite vai `form-urlencoded` para a rota que já existe e já dispara a
 *  transição `registra_consentimento` — não há segunda via de gravação. */
export function registrarConsentimento(casoId: string, aceite: boolean): Promise<unknown> {
  const corpo = new URLSearchParams()
  if (aceite) corpo.append('aceite', 'on')
  return fetch(`/caso/${casoId}/consentimento`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: corpo.toString(),
  }).then((r) => {
    if (!r.ok) throw new ErroHttp(r.status, `HTTP ${r.status}`)
    return r
  })
}

export function obterProgressoDoCalculo(
  casoId: string,
): Promise<{ CASO_ID: string; estado: string; calculando: boolean; erro_de_calculo: boolean }> {
  // Sem `/api`: esta é a URL canônica do progresso, documentada em
  // `app/http/aplicacao.py` e usada pelos testes de ponta a ponta. A rota
  // vive em `rotas_calculo.py` (prefixo `/caso`), junto do POST que dispara
  // o cálculo — as duas são a mesma etapa.
  return pedir(`/caso/${casoId}/calculo/progresso`)
}

export interface LinhaDoPainel {
  CASO_ID: string
  estado: string
  aguardando_revisao: boolean
  tempo_desde_ultima_atividade: string
}

export function obterPainelDoOperador(): Promise<{ linhas: LinhaDoPainel[] }> {
  return pedir<{ linhas: LinhaDoPainel[] }>('/api/operador/painel')
}

// ---------------------------------------------------------------------------
// Coleta dirigida (Blocos 7 e 8) e Bloco 10 (T-142)
// ---------------------------------------------------------------------------

export interface FichaDirigida {
  item_id: string
  campos: Pergunta[]
}

export interface ColetaDirigida {
  CASO_ID: string
  dividas: string[]
  perguntas: string[]
  fichas: FichaDirigida[]
}

export function obterColetaDirigida(
  casoId: string,
  bloco: 7 | 8,
): Promise<ColetaDirigida> {
  return pedir<ColetaDirigida>(`/caso/${casoId}/coleta-dirigida/bloco-${bloco}`)
}

export interface Bloco10 {
  CASO_ID: string
  ATAQUE_IMEDIATO_RECOMENDADO: string
  campos: Pergunta[]
}

export function obterBloco10(casoId: string): Promise<Bloco10> {
  return pedir<Bloco10>(`/caso/${casoId}/bloco-10`)
}

/** O Bloco 10 grava pela rota própria, que valida `0 ≤ APROVADO ≤
 *  RECOMENDADO` no servidor — o cliente nunca decide esse limite. */
export function responderBloco10(
  casoId: string,
  idPergunta: string,
  valor: string,
): Promise<unknown> {
  const corpo = new URLSearchParams({ ID_PERGUNTA: idPergunta, valor })
  return pedir(`/caso/${casoId}/bloco-10/resposta`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: corpo.toString(),
  })
}

// ---------------------------------------------------------------------------
// Bloco 11 — ações e seu andamento (T-143)
// ---------------------------------------------------------------------------

export interface Acao {
  ACAO_ID: string
  TIPO_ACAO: string
  /** `AC-50`: ação de economia não tem dívida — por isso pode ser `null`. */
  DIVIDA_ID: string | null
  descricao: string
  prioridade_excepcional: boolean
  CAMPO_PENDENTE: string | null
  /** String ou `null` — nunca `number`: `RF-13` proíbe dinheiro em float, e
   *  desconhecido nunca vira zero. */
  VALOR_ACAO_FINANCEIRA_IMEDIATA: string | null
  campos: Pergunta[]
}

export function obterAcoes(casoId: string): Promise<{ CASO_ID: string; acoes: Acao[] }> {
  return pedir<{ CASO_ID: string; acoes: Acao[] }>(`/caso/${casoId}/acoes`)
}

export function responderAcao(
  casoId: string,
  entrada: {
    idPergunta: string
    itemId: string
    valor?: string | string[]
    naoSei?: boolean
  },
): Promise<unknown> {
  const corpo = new URLSearchParams()
  corpo.append('ID_PERGUNTA', entrada.idPergunta)
  corpo.append('item_id', entrada.itemId)
  if (entrada.naoSei) {
    corpo.append('nao_sei', 'on')
  } else if (typeof entrada.valor === 'string') {
    corpo.append('valor', entrada.valor)
  }
  return pedir(`/caso/${casoId}/acoes/resposta`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: corpo.toString(),
  })
}
