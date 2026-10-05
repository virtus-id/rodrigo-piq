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
  /**
   * `T-213`: a opção pede um valor digitado. `DATA` grava no lugar do
   * código; `MOEDA` (`T-294`) grava o código e o R$ vai a outra variável.
   */
  abre_campo?: TipoResposta | null
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
  /**
   * `T-294`: o R$ gravado pela opção com `abre_campo: MOEDA` escolhida
   * (`null` sem valor). Ausente quando nenhuma opção do registro o pede.
   */
  valor_do_campo?: string | null
  /**
   * O painel da fotografia do mês (`RF-79`, `RF-80`, T-227) — só na pergunta
   * cujo registro o declara. Ausente em todas as outras.
   */
  painel?: PainelFotografia
  /**
   * `T-307` (`RF-99`): por `valor_interno` da opção, as perguntas que ela
   * abre — já decididas pelo servidor. O cliente só consulta pelo valor
   * escolhido (`RF-45`). Ausente quando nenhuma opção abre nada.
   */
  complementares?: Record<string, Pergunta[]>
  /**
   * `T-309` (`RF-70`): a pergunta respondida logo antes desta no percurso —
   * decidida pelo servidor. `null` na primeira; ausente fora da coleta.
   */
  anterior?: { ID: string; item_id: string | null } | null
  /**
   * `T-318` (`RF-70`): a pergunta logo depois desta no percurso, só quando
   * esta já está respondida — decidida pelo servidor. `null` na fronteira.
   */
  seguinte?: { ID: string; item_id: string | null } | null
  /** `T-310` (`RF-100`): as cinco partes e o estado de cada uma. */
  trilha?: ParteDaTrilha[] | null
  /**
   * `T-319` (`RF-106`): por `valor_interno` da opção que abre uma ficha curta
   * ainda sem item, as perguntas que o primeiro item exibiria — decididas
   * pelo servidor. Vêm com `item_id` provisório; gravam no item que a mãe
   * criar. Ausente quando nenhuma opção abre ficha nova.
   */
  ficha_nova?: Record<string, FichaNova>
}

/** O formulário do item que a pergunta-gatilho vai criar — `T-319`. */
export interface FichaNova {
  escopo: string
  pede_nome: boolean
  perguntas: Pergunta[]
}

/** Uma parte da trilha da coleta — `T-310`. O estado vem do servidor. */
export interface ParteDaTrilha {
  numero: number
  rotulo: string
  estado: 'concluida' | 'atual' | 'proxima'
}

/** Uma linha das decomposições da fotografia — valor e destino da correção. */
export interface LinhaDaFotografia {
  item_id: string
  rotulo: string | null
  /** String decimal; `null` = não informado. */
  valor_mensal: string | null
  corrigir: { ID_PERGUNTA: string | null; item_id: string }
}

/**
 * `B3.C00` — os três números, todos do servidor (`RF-79`). `null` = não
 * informado, nunca `0` (`EC-28`); `parcial` marca o total com item "não sei"
 * (decisão `R9-2`).
 */
export interface PainelFotografia {
  tipo: 'FOTOGRAFIA_DO_MES'
  renda_total: string | null
  despesas_totais: string | null
  sobra_antes_das_dividas: string | null
  parcial: { renda: boolean; despesas: boolean; sobra: boolean }
  despesas_por_item: LinhaDaFotografia[]
  nao_mensais_por_item: LinhaDaFotografia[]
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
  /** O nome do item para o aluno ("Aluguel"), ou `null` — `T-217`. */
  rotulo: string | null
  /** "Outro" e despesa não listada: a tela pede um nome curto (`T-217`). */
  pede_nome: boolean
  completa: boolean
  campos: Pergunta[]
  /** O item dentro do qual esta ficha foi criada — a margem no vínculo (`T-254`). */
  item_pai_id?: string | null
  /** As fichas criadas dentro desta, cada uma sob o seu pai — nunca somadas (`AC-138`). */
  margens?: Ficha[]
  /** O que perde o pai se esta ficha for removida (`EC-35`). */
  dependentes?: { margens: string[]; dividas: string[] }
}

export interface ListaDeFichas {
  CASO_ID: string
  escopo: string
  /** O escopo dentro do qual este é criado, ou `null` (`T-254`). */
  escopo_pai?: string | null
  /** Os escopos criados dentro de cada ficha deste (`T-254`). */
  escopos_filhos?: string[]
  fichas: Ficha[]
  /** `T-310`: a trilha da coleta, na parte desta ficha. */
  trilha?: ParteDaTrilha[] | null
}

/**
 * `GET /caso/{id}/formulario/{escopo}/{item_id}` — a ficha curta inteira
 * numa tela (`T-314`). As perguntas e as `complementares` de cada uma vêm
 * decididas pelo servidor; a posição e os concluídos também (`T-317`).
 */
export interface FormularioDoItem {
  CASO_ID: string
  escopo: string
  escopo_pai: string | null
  item_id: string
  rotulo: string | null
  pede_nome: boolean
  completa: boolean
  perguntas: Pergunta[]
  posicao_do_item: number
  total_de_itens: number
  itens_concluidos: number
  trilha: ParteDaTrilha[] | null
}

/** `GET /caso/{id}/escopos` — se cada escopo está aberto para o caso (`T-212`). */
export interface EscoposDoCaso {
  CASO_ID: string
  escopos: { escopo: string; aberto: boolean }[]
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
  /**
   * Os escopos de ficha que esta resposta abriu e que ainda não têm item
   * (`T-212`) — ex.: "Sim" em `B3.03` → `['RENDA_ADICIONAL_ID']`. Vazio na
   * resposta comum. Quem decide é o servidor (`RF-52`).
   */
  abrir_fichas: string[]
  /**
   * Avisos da gravação (`RF-84`, T-240) — a resposta JÁ foi gravada; o
   * aviso só sinaliza algo a conferir (ex.: desconto em R$ e em % que não
   * batem). Vazio na resposta comum.
   */
  avisos?: AvisoDeGravacao[]
}

export interface AvisoDeGravacao {
  codigo: string
  mensagem: string
  ID_PERGUNTA: string
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
  /** Identificador — chave da lista; ao revisor, detalhe discreto. */
  DIVIDA_ID: string
  /**
   * A dívida como o aluno a reconhece — "Cheque especial — CAIXA ECONOMICA
   * FEDERAL" (`RF-111`, `T-326`). Montado pelo servidor; nunca o código.
   */
  nome: string
  /**
   * O texto de AUDITORIA do motor — cita método, critério normativo e
   * regras de desempate (`O-04`/`O-05`). É o que o revisor precisa para
   * refazer a decisão (`AC-29`); `engine/ordem.py` o declara "não prosa de
   * usuário final". Só vem no payload do REVISOR (`T-305`).
   */
  JUSTIFICATIVA_POSICAO?: string
  /**
   * O mesmo "porquê", dito ao ALUNO — `T-177`. Vem de
   * `textos-canonicos.yaml` por método; todo método tem redação.
   */
  explicacao: string
  /**
   * Mês previsto de quitação, lido do cronograma gravado — `T-304`
   * (`DE-08`). `null`: não disponível. Opcional só para os planos montados
   * à mão nos testes de outras telas.
   */
  mes_de_quitacao?: number | null
  /**
   * Fonte de comprovação dos dados desta dívida — `RF-92`, `T-267`. O
   * rótulo do nível vem pronto do servidor (`textos-canonicos.yaml`);
   * `null` quando a dívida não tem ficha ativa.
   */
  fonte?: string | null
  /**
   * Orientação sobre o seguro prestamista — `RF-82`, `T-245`. Texto pronto
   * do servidor (`textos-canonicos.yaml`); `null` na dívida sem seguro.
   */
  orientacao_seguro?: string | null
  valores_de_apoio: ValorDeApoio[]
  /**
   * Revisão de design (2026-10-03) — os números fixos de toda dívida,
   * qualquer que seja o método: quanto deve hoje, a parcela que paga hoje
   * e a taxa de juros. Já formatados; "Não informado" quando o dado falta.
   */
  fatos?: ValorDeApoio[]
}

export interface AcaoRequerida {
  DIVIDA_ID: string | null
  /** "tipo — credor" (`T-326`); `null` na ação sem dívida (economia). */
  nome_divida: string | null
  /** O que fazer, em português, por `TIPO_ACAO` (`T-306`). */
  descricao: string
  prioridade_excepcional: boolean
  /** O motivo técnico do gate — só no payload do REVISOR (`T-306`). */
  motivo?: string
}

export interface Pendencias {
  inventario_incompleto: boolean
  campos_faltantes_por_divida: { DIVIDA_ID: string; nome: string; campos: string[] }[]
}

/** `AC-70`: reserva desconhecida é estado explícito, nunca `R$ 0,00`. */
export interface ReservaMobilizavel {
  pendente_de_decisao: boolean
  valor: string
}

export interface Plano {
  /** Redação vigente de `textos-canonicos.yaml` — vem do servidor, nunca reescrita aqui. */
  titulo: string
  corpo: string
  ordem: PosicaoDaOrdem[]
  PRAZO_TOTAL: string
  /**
   * Plano amigável (2026-10-03) — o mesmo prazo, como inteiro cru. Serve só
   * à GEOMETRIA dos gráficos (posição relativa de uma barra/marca na linha
   * do tempo e no mapa da jornada) — nunca exibido como número; o texto
   * que o aluno lê continua sendo `PRAZO_TOTAL`, já formatado.
   */
  PRAZO_TOTAL_INT: number
  CUSTO_FUTURO_TOTAL: string
  /** `T-304` (`DE-08`): valor por mês destinado ao ataque, já formatado. */
  valor_mensal_destinado?: string
  ENGINE_VERSION: string
  PARAMETROS_VERSION: string
  /** Rótulo do método recomendado ("Híbrido") — `T-326`. */
  metodo: string
  /** Rótulo do cenário de apresentação — `T-326`; nunca o código. */
  cenario: string
  acoes: AcaoRequerida[]
  pendencias: Pendencias | null
  MODO_ESTABILIZACAO: boolean
  RESULTADO_CAIXA_OBSERVADO: string
  reserva_mobilizavel: ReservaMobilizavel
  /**
   * `RF-98`, `AC-152` (`T-276`): a segunda projeção do motor, com os
   * recursos extraordinários prováveis e possíveis. Seção À PARTE — nenhum
   * número daqui entra no plano acima. `null` quando o motor não a projetou;
   * opcional só para os planos montados à mão nos testes de outras telas.
   */
  cenario_adicional?: CenarioAdicional | null
  /** Itens que a projeção-base deixou de fora, com o motivo do motor. */
  nao_projetados?: { ITEM_ID: string; motivo: string }[]
  /**
   * Plano amigável — "Seu primeiro passo" (Mês 1). `null` em ordem vazia
   * ou sem mês simulado (estabilização).
   */
  passo_atual?: PassoAtual | null
  /** Plano amigável — "Sua primeira vitória". `null` sem primeira quitação. */
  primeira_vitoria?: PrimeiraVitoria | null
  /** Plano amigável — "Sua jornada mês a mês". Vazia sem mês simulado. */
  jornada?: EtapaJornada[]
  /**
   * Redesenho (2026-10-03) — a MESMA jornada, em grade por mês individual
   * ("bater o olho e entender", sem frase corrida). Substitui `jornada` na
   * exibição; `jornada` continua existindo para o mapa SVG da trilha.
   */
  grade_meses?: MesDaGrade[]
  /**
   * A mesma grade em calendário por ano (12 meses por linha). Vazia em
   * plano de até 12 meses, que fica com os cartões grandes.
   */
  grade_anos?: AnoDaGrade[]
  /** Plano amigável — "Como o seu plano funciona", passos em português. */
  como_funciona?: string[]
  /** Plano amigável — pendências com "onde achar" e o ID da pergunta. */
  pendencias_acionaveis?: PendenciaAcionavel[]
  /** Plano amigável — textos fixos que não variam por caso. */
  explicacao_mes_1?: string
  como_funciona_titulo?: string
  jornada_titulo?: string
  /**
   * Modelos de frase por tipo de etapa da jornada ("fase_um_mes",
   * "quitacao", "aporte", "chegada"…), com `{placeholders}` — o cliente
   * interpola com os campos já formatados de cada `EtapaJornada`
   * (`jornada.ts::textoDaEtapa`). A fonte da redação continua
   * `textos-canonicos.yaml`.
   */
  jornada_modelos?: Record<string, string>
  /** Redesenho — rótulos curtos da grade por mês ("Mês", "a mais"…). */
  grade_meses_textos?: Record<string, string>
  /**
   * Revisão de design (2026-10-03) — personalização: o primeiro nome do
   * aluno (`null` sem nome na conta) e os números do mês dele.
   */
  nome_do_aluno?: string | null
  ponto_de_partida?: PontoDePartida | null
  /** Textos do cabeçalho ("Plano preparado para {nome}"). */
  cabecalho_textos?: Record<string, string>
  /** Títulos das seções, na ordem do documento. */
  secoes?: Record<string, string>
  /** Rótulos e explicações dos três números do resumo. */
  resumo_textos?: Record<string, string>
  /** Rótulos da seção "Seu ponto de partida". */
  ponto_de_partida_textos?: Record<string, string>
  /** Títulos e textos dos três passos do Mês 1. */
  primeiro_passo_textos?: Record<string, string>
  /** Títulos curtos dos quadros de "Como o seu plano funciona". */
  como_funciona_rotulos?: string[]
  /** Textos do cartão de cada dívida ("Termina no", "Por que…"). */
  dividas_textos?: Record<string, string>
  /** Redesenho — título e legenda da linha do tempo. */
  linha_do_tempo_textos?: Record<string, string>
  primeiro_passo_titulo?: string
  como_pagar_a_mais?: string
  primeira_vitoria_titulo?: string
  primeira_vitoria_complemento?: string
  reserva_explicacao?: string
  duvidas?: { pergunta: string; resposta: string }[]
  sobre_este_plano?: string
}

/** Os números do mês do aluno — todos lidos do cálculo e já formatados. */
export interface PontoDePartida {
  renda: string
  gastos: string
  gastos_ocasionais: string
  parcelas: string
  valor_extra: string
  quantidade_de_dividas: number
}

export interface ParcelaDoPasso {
  nome: string
  valor: string
}

export interface PassoAtual {
  /** Nome da dívida-alvo ("tipo — credor"); `null` sem dívida-alvo. */
  alvo: string | null
  valor_extra: string
  parcelas: ParcelaDoPasso[]
}

export interface PrimeiraVitoria {
  mes: number
  divida: string
}

/**
 * Uma etapa de "Sua jornada mês a mês" — `tipo` decide quais campos usar.
 * `FASE`: meses consecutivos com o mesmo alvo e valor extra (`alvo`,
 * `valor`). `QUITACAO`: marco de dívida quitada (`divida_quitada`,
 * `parcela_liberada`, `destino`, `sobra?`). `APORTE`: recurso extraordinário
 * que chegou (`alvo`, `valor`). `CHEGADA`: fim do cronograma (só meses).
 */
export interface EtapaJornada {
  tipo: 'FASE' | 'QUITACAO' | 'APORTE' | 'CHEGADA'
  mes_inicio: number
  mes_fim: number
  alvo: string | null
  valor: string | null
  /**
   * String decimal crua (plano amigável) — só para a altura do degrau em
   * "Bola de neve em degraus" (geometria de desenho); nunca exibida como
   * número. `null` fora de uma etapa `FASE`.
   */
  valor_bruto: string | null
  divida_quitada: string | null
  parcela_liberada: string | null
  destino: string | null
  sobra: string | null
}

/**
 * Redesenho (2026-10-03) — um cartão de grade por mês INDIVIDUAL. `tipo`
 * decide o ícone/cor do cartão: `ATAQUE` (mês comum, pagando o extra),
 * `QUITACAO` (uma ou mais dívidas acabaram), `APORTE` (chegou um valor
 * extraordinário) ou `CHEGADA` (fim do plano). Rótulos sempre curtos —
 * nunca frase corrida.
 */
export interface MesDaGrade {
  mes: number
  tipo: 'ATAQUE' | 'QUITACAO' | 'APORTE' | 'CHEGADA'
  alvo: string | null
  valor_extra: string | null
  dividas_quitadas: string[]
  eh_primeira_vitoria: boolean
  tem_aporte: boolean
}

export interface AnoDaGrade {
  numero: number
  mes_inicio: number
  mes_fim: number
  meses: MesDaGrade[]
  /** Valores extras distintos do ano, na ordem em que aparecem. */
  valores_extras: string[]
  quitacoes: { mes: number; nome: string }[]
}

export interface PendenciaAcionavel {
  DIVIDA_ID: string
  nome_divida: string
  rotulo: string
  onde_achar: string
  /** ID da pergunta do Bloco 5 que grava o campo — alimenta o botão
   * "Responder agora" (`navegacao.ts`, rota `respostas`). `null` sem
   * pergunta mapeada. */
  ID_PERGUNTA: string | null
}

export interface CenarioAdicional {
  /** Rótulo e explicação de `textos-canonicos.yaml` — verbatim. */
  rotulo: string
  explicacao: string
  PRAZO_TOTAL: string
  CUSTO_FUTURO_TOTAL: string
  ordem: string[]
  /** `ITEM_ID` só no payload do REVISOR (`T-306`/plano amigável). */
  itens: { ITEM_ID?: string; mes: number; valor: string }[]
}

export interface RespostaPlano {
  CASO_ID: string
  estado: string
  plano: Plano | null
  mensagem?: string
}

export interface ItemDaFila {
  CASO_ID: string
  /** `T-327` (`RF-111` e): a identificação para a equipe; `null` cai no `CASO_ID`. */
  email_do_aluno?: string | null
  SNAPSHOT_ID: string
  versao: number
  DATA_REFERENCIA: string
  MOTIVO_RECALCULO: string | null
  EVENTO_RECALCULO: string | null
  METODO_RECOMENDADO_PIQ: string
  STATUS_METODO: string
  /**
   * Rótulos do servidor (`RF-111`, `T-326`): o que a tela mostra. Os
   * códigos acima e o `MOTIVO_RECALCULO` do motor ficam como detalhe.
   */
  metodo: string
  status_metodo: string
  /** `T-330`: o critério do método, uma frase — vale para o caso inteiro. */
  criterio_metodo: string
  motivo: string
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
  | 'inventario'
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
  /** `T-301`: listas de fichas a abrir antes da coleta (sinal de `T-291`). */
  abrir_fichas?: string[]
}

export interface ProgressoDaColeta {
  respondidas: number
  total: number
  /**
   * `T-293`: há ficha com pergunta em branco ou ainda por cadastrar — o
   * `total` vai crescer. A tela mostra só as respondidas, que nunca regridem.
   */
  fichas_abertas?: boolean
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
  /** `T-335`: como exibir `valores` — `TAXA` e `MOEDA` chegam crus do servidor. */
  tipo?: TipoResposta
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
  /** `RF-114`: em cálculo ou conferência as respostas só se leem. Ausente ⇒ editável. */
  editavel?: boolean
  /** `RF-115`: só a conferência permite retirar o plano para editar. */
  pode_retomar_edicao?: boolean
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
  /**
   * `T-333` (`RF-113`): a conferência pediu correção e o aluno ainda não
   * reenviou. `null` fora disso. Só a mensagem ao aluno — a observação
   * interna do revisor nunca vem para cá.
   */
  correcao_pedida?: CorrecaoPedida | null
}

/** Um dado a conferir — pendência de homologação (`RF-93`), por nome. */
export interface DadoAConferir {
  /** O nome da dívida ("Cheque especial — CAIXA"); `null` fora de ficha. */
  nome: string | null
  enunciado: string
  /** Só para o link de correção (`RF-69`) — nunca exibidos. */
  ID_PERGUNTA: string
  item_id: string | null
}

export interface CorrecaoPedida {
  mensagem: string | null
  dados_a_conferir: DadoAConferir[]
}
