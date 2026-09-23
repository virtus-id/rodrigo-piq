/**
 * A redação da tela de entrada — `RF-50`.
 *
 * **Separado do componente de propósito.** `TelaLogin.tsx` sabe autenticar;
 * este arquivo sabe o que a tela diz. Quem revisa a redação é o
 * especialista, não quem escreve React: um arquivo só de texto é editável
 * sem ler JSX, sem risco de quebrar um `onSubmit` por engano, e o diff de
 * uma revisão de copy fica legível.
 *
 * Mesma disciplina de `app/notificacao/textos/emails.yaml` e de
 * `report/templates/plano/textos-canonicos.yaml`. Aqui é `.ts` e não YAML
 * porque o frontend não tem carregador de YAML — montar um só para este
 * arquivo seria custo sem ganho, e o objetivo (texto fora do componente,
 * num lugar óbvio) já está atendido.
 *
 * **Esta é a primeira tela que quem comprou vê.** O texto não anuncia o
 * sistema — nem quantas perguntas existem, nem quantos métodos são
 * comparados. Isso é o preço que a pessoa paga, não o que ela ganha, e
 * anunciá-lo antes do benefício é o caminho mais curto para o
 * arrependimento da compra. O que a tela afirma é o resultado: por onde
 * começar, quantos meses faltam, quanto do salário volta a ser dela.
 */

/** O selo acima do título, no painel de marca. */
export const SELO = 'Seu plano de quitação'

/**
 * O título. `destaque` sai em itálico e na cor de realce — é a promessa
 * dentro da frase, não um efeito decorativo.
 */
export const TITULO = {
  antes: 'Suas dívidas têm uma ',
  destaque: 'data para acabar',
  depois: '.',
}

export const SUBTITULO =
  'Nós calculamos qual é. Você descobre por qual dívida começar, quantos meses ' +
  'faltam e quanto do seu salário volta a ser seu.'

/**
 * As três respostas aos "e daí?" de quem está decidindo se preenche.
 *
 * Nenhuma é um número do sistema. Cada uma responde a uma pergunta que a
 * pessoa realmente faz — e a terceira é o mecanismo do plano dito em
 * dinheiro: a parcela liberada a cada dívida quitada é o que reforça o
 * ataque à próxima (ver `report/templates/plano/textos-canonicos.yaml`).
 */
export const PROVAS: ReadonlyArray<{ titulo: string; detalhe: string }> = [
  {
    titulo: 'Por onde começar',
    detalhe: 'a ordem que encurta o caminho inteiro',
  },
  {
    titulo: 'Quantos meses',
    detalhe: 'o mês em que você paga a última parcela',
  },
  {
    titulo: 'Quanto sobra',
    detalhe: 'o que cada dívida quitada devolve ao seu mês',
  },
]

/** O lado do formulário. */
export const FORMULARIO = {
  titulo: 'Continue de onde parou',
  lead: 'Suas respostas estão guardadas. Falta pouco para o seu plano ficar pronto.',
  rotuloEmail: 'Seu e-mail',
  rotuloSenha: 'Sua senha',
  entrar: 'Entrar',
  entrando: 'Entrando…',
}

/**
 * **Diz a verdade sobre quem vê os dados.** A versão anterior dizia
 * "ninguém mais vê o que você respondeu", o que é falso: o plano é
 * conferido por uma pessoa da equipe antes de ser liberado (`RF-23`). Uma
 * promessa de sigilo que o próprio produto quebra é pior que nenhuma — e
 * estaria na tela onde a confiança começa.
 */
export const RODAPE_SEGURANCA = 'O que você responde fica entre você e a nossa equipe.'

/** Mensagens de erro. Ver a nota sobre não vazar existência de e-mail. */
export const ERROS = {
  credenciais: 'E-mail ou senha não conferem.',
  indisponivel: 'Não foi possível entrar agora.',
}
