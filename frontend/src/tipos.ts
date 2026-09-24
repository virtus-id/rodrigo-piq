/**
 * Os tipos da API — espelho de `app/http/serializacao.py` (`RF-51`, T-136).
 *
 * **O que NÃO existe aqui, e é deliberado.** Nenhum tipo para
 * `condicao_exibicao`, `validacoes_cruzadas` ou `obrigatoriedade`. O
 * servidor não os envia (`RF-52`), e não declará-los aqui é a segunda
 * trava: um dia em que alguém tentar ler `pergunta.condicao_exibicao`, o
 * TypeScript recusa antes de o código rodar.
 *
 * `valor_atual` é `string | string[] | null` — nunca `number`. Valor
 * monetário chega como string (`"1234.56"`) porque `JSON.parse`
 * transformaria um número em `double` silenciosamente, e `RF-13` proíbe que
 * dinheiro atravesse ponto flutuante. Quem interpreta continua sendo
 * `app/montagem/conversao.py`, no servidor.
 */

/** Os nove `TipoResposta` de `collection/registro.py`. */
export type TipoResposta =
  | 'SELECAO_UNICA'
  | 'SELECAO_MULTIPLA'
  | 'NUMERO'
  | 'MOEDA'
  | 'TAXA'
  | 'DATA'
  | 'TEXTO_CURTO'
  | 'SIM_NAO_TALVEZ'
  | 'ESCALA_0_10'

/** O sentinela de "não sei" na fronteira HTTP — nunca `null`, nunca `0`. */
export const VALOR_NAO_SEI = 'NAO_SEI'

export interface Opcao {
  rotulo: string
  valor_interno: string | null
  admite_nao_sei: boolean
}

export interface Pergunta {
  CASO_ID: string
  ID: string
  bloco: number
  tipo: TipoResposta
  enunciado: string
  opcoes: Opcao[]
  escopo_repeticao: string
  item_id: string | null
  /**
   * A posição da pergunta dentro da ficha, 1-indexada — `RF-63`, `AC-92`.
   * `null` fora de ficha repetível, e aí o localizador cai no rótulo do
   * bloco. Quem conta é o servidor: ele conhece o conjunto exibível, e o
   * cliente nunca soube quais perguntas existem (`RF-45`).
   */
  posicao: number | null
  total_na_ficha: number | null
  admite_nao_sei: boolean
  valor_atual: string | string[] | null
  respondida_como_nao_sei: boolean
  valores_marcados: string[]
  aviso: string | null
}

export interface RespostaPergunta {
  pergunta: Pergunta | null
  coleta_completa?: boolean
  avanco_permitido?: boolean
  total_pendencias?: number
  CASO_ID?: string
}

export interface Ficha {
  item_id: string
  completa: boolean
  campos: Pergunta[]
}

export interface ListaDeFichas {
  CASO_ID: string
  escopo: string
  fichas: Ficha[]
}

/**
 * A PRÓXIMA pergunta, já dentro da confirmação de gravação — `T-193`.
 *
 * Mesmo formato que `RespostaPergunta` devolveria num `GET /pergunta` à
 * parte, só que sem precisar dessa segunda viagem: o servidor já sabia a
 * resposta no mesmo instante em que confirmou a gravação.
 */
export interface ProximaPergunta {
  pergunta: Pergunta | null
  coleta_completa: boolean
}

/** O que `POST /caso/{id}/resposta` devolve quando se pede JSON. */
export interface ConfirmacaoDeResposta {
  ID_PERGUNTA: string
  aviso: string | null
  avanco_permitido: boolean
  total_pendencias: number
  proxima: ProximaPergunta
}

/** Erro tipado da API — o servidor sempre nomeia o motivo. */
export interface ErroDaApi {
  erro: string
}

// ---------------------------------------------------------------------------
// Plano, fila de revisão e etapas — espelho de `app/http/serializacao_plano.py`
// ---------------------------------------------------------------------------

export interface ValorDeApoio {
  rotulo: string
  valor: string
}

export interface PosicaoDaOrdem {
  posicao: number
  indice: number
  total: number
  DIVIDA_ID: string
  /**
   * O texto de AUDITORIA do motor — cita método, critério normativo e
   * regras de desempate (`O-04`/`O-05`). É o que o revisor precisa para
   * refazer a decisão (`AC-29`); `engine/ordem.py` o declara "não prosa de
   * usuário final".
   */
  JUSTIFICATIVA_POSICAO: string
  /**
   * O mesmo "porquê", dito ao ALUNO — `T-177`.
   *
   * Vem de `textos-canonicos.yaml` por método. Vazia quando o método não
   * tem redação cadastrada: aí a tela cai na justificativa técnica, que é
   * visível, em vez de não explicar nada.
   */
  explicacao: string
  valores_de_apoio: ValorDeApoio[]
}

export interface AcaoRequerida {
  DIVIDA_ID: string | null
  descricao: string
  prioridade_excepcional: boolean
}

export interface Pendencias {
  inventario_incompleto: boolean
  campos_faltantes_por_divida: { DIVIDA_ID: string; campos: string[] }[]
}

/** `AC-70`: reserva desconhecida é estado explícito, nunca `R$ 0,00`. */
export interface ReservaMobilizavel {
  pendente_de_decisao: boolean
  valor: string
}

export interface Plano {
  /** Redação canônica de `Q-03` — vem do servidor, nunca reescrita aqui. */
  titulo: string
  corpo: string
  ordem: PosicaoDaOrdem[]
  PRAZO_TOTAL: string
  CUSTO_FUTURO_TOTAL: string
  ENGINE_VERSION: string
  PARAMETROS_VERSION: string
  cenario: string
  acoes: AcaoRequerida[]
  pendencias: Pendencias | null
  MODO_ESTABILIZACAO: boolean
  RESULTADO_CAIXA_OBSERVADO: string
  reserva_mobilizavel: ReservaMobilizavel
}

export interface RespostaPlano {
  CASO_ID: string
  estado: string
  plano: Plano | null
  mensagem?: string
}

export interface ItemDaFila {
  CASO_ID: string
  SNAPSHOT_ID: string
  versao: number
  DATA_REFERENCIA: string
  MOTIVO_RECALCULO: string | null
  EVENTO_RECALCULO: string | null
  METODO_RECOMENDADO_PIQ: string
  STATUS_METODO: string
  /** Os dois sinais seguem SEPARADOS — política do piloto × sinal do motor. */
  entra_por_politica: boolean
  e_metodologico: boolean
  ENGINE_VERSION: string
  PARAMETROS_VERSION: string
}

export interface Etapas {
  CASO_ID: string
  blocos_7_8: boolean
  bloco_10: boolean
  bloco_11: boolean
  ATAQUE_IMEDIATO_RECOMENDADO?: string
}

// ---------------------------------------------------------------------------
// A tela Início — espelho de `app/http/rotas_inicio.py` (T-147)
// ---------------------------------------------------------------------------

/** As cinco fases de `app/casos/fases.py::FASE_INICIO`. */
export type Fase = 'coleta' | 'revisao' | 'reprovado' | 'plano' | 'acompanhamento'

/**
 * Para onde a próxima etapa leva — espelho de
 * `app/casos/../rotas_inicio.py::DESTINO_DA_ETAPA`.
 *
 * **O servidor manda o destino, não o texto.** `AC-37` proíbe redação longa
 * no código da aplicação, e a divisão é a certa: o servidor decide QUAL é a
 * próxima etapa (depende do estado do caso, que só ele conhece); a interface
 * decide COMO dizer. Como união fechada, um destino novo sem texto em
 * `TelaInicio` não compila.
 */
export type DestinoDaEtapa =
  | 'consentimento'
  | 'pergunta'
  | 'calculando'
  | 'aguardando'
  | 'progresso'
  | 'bloco10'
  | 'acoes'
  | 'plano'

/**
 * A ÚNICA próxima etapa do aluno — `RF-58`.
 *
 * Não é uma lista com um item: é o contrato. Oferecer duas já seria pedir ao
 * aluno que escolhesse, que é exatamente o que a barra de sete abas fazia.
 */
export interface ProximaEtapa {
  destino: DestinoDaEtapa
  ID_PERGUNTA: string | null
  item_id: string | null
}

export interface ProgressoDaColeta {
  respondidas: number
  total: number
}

// ---------------------------------------------------------------------------
// A revisão das respostas — espelho de `app/http/rotas_respostas.py` (T-160)
// ---------------------------------------------------------------------------

/**
 * Uma resposta já dada, como o aluno a lerá — `RF-68`, `AC-100`.
 *
 * `valores` é LISTA, não string: `SELECAO_MULTIPLA` tem várias, e o servidor
 * se recusa a juntá-las porque o separador é decisão de apresentação. Quem
 * escolhe a vírgula é esta camada.
 *
 * O que vem aqui é o RÓTULO escolhido, nunca o valor interno — quem respondeu
 * "Empréstimo consignado" precisa reler "Empréstimo consignado".
 */
export interface RespostaDada {
  ID: string
  item_id: string | null
  enunciado: string
  respondida_como_nao_sei: boolean
  valores: string[]
}

/**
 * Uma das cinco partes da coleta, com o que foi respondido nela.
 *
 * **`respondidas` vazia é estado legítimo** (`AC-101`): a parte vem assim
 * mesmo, com `total_de_perguntas`, e a tela diz que ela ainda não foi
 * respondida. Sumir da lista faria o aluno procurar onde ela foi parar.
 */
export interface ParteDasRespostas {
  bloco: number
  rotulo: string
  total_de_perguntas: number
  respondidas: RespostaDada[]
}

export interface RespostasDoCaso {
  CASO_ID: string
  partes: ParteDasRespostas[]
}

export interface Inicio {
  CASO_ID: string
  estado: string
  fase: Fase
  mensagem: string
  proxima_etapa: ProximaEtapa
  progresso: ProgressoDaColeta
  /**
   * String ou `null` — nunca `number`. `RF-13`: dinheiro não atravessa ponto
   * flutuante, e `JSON.parse` faria isso silenciosamente.
   *
   * Vem SEPARADO do `rotulo` de propósito (`AC-88`): o servidor manda o
   * rótulo genérico e o número; quem compõe a frase é esta camada.
   */
  valor_em_destaque: string | null
  plano_liberado: boolean
  versao_do_plano: number | null
}
