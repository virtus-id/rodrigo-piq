/**
 * A casca da aplicação — `RF-57`, `RF-58`, `RF-59` (T-149).
 *
 * **A barra de sete abas morreu aqui.** Até T-145 esta casca oferecia
 * Coleta · Dívidas · Plano · Ataque · Ações · Fila · Painel, todas ao mesmo
 * tempo, e deixava o aluno escolher. Parecia navegação inocente, mas era
 * decisão de fluxo no cliente: quem decidia se o caso ia para "Ataque" ou
 * "Ações" era um servidor público endividado, diante de sete botões, sem
 * saber qual se aplicava ao seu caso — e vários não se aplicavam.
 *
 * O que substitui a barra é a **tela Início** (`RF-58`): ela pergunta ao
 * servidor qual é a fase do caso e oferece **uma** próxima etapa. Toda outra
 * tela do aluno é alcançada por uma ação explícita da tela anterior
 * (`AC-83`), dentro da casca de três partes de `componentes/Tela.tsx`.
 *
 * O `switch` abaixo é **exaustivo por tipo**: `Rota` é união discriminada, e
 * uma tela nova sem caso aqui não compila. É a mesma trava que
 * `app/casos/fases.py::fase_do_estado` tem no servidor.
 *
 * O `CASO_ID` vem da URL (`?caso=...`). Não é decisão do cliente: o servidor
 * reverifica, a cada requisição, se a sessão possui aquele caso — informar um
 * `CASO_ID` alheio devolve `404`, indistinguível de inexistente.
 */
import { useCallback, useEffect, useState } from 'react'

import { eTelaDaEquipe, type Rota, substituirRota, useRota } from './navegacao'
import { obterInicio, obterSessao } from './services/api'
import type { Inicio } from './tipos'
import TelaAcao from './telas/TelaAcao'
import TelaAcoes from './telas/TelaAcoes'
import TelaAguardando from './telas/TelaAguardando'
import TelaCalculando from './telas/TelaCalculando'
import TelaBloco10 from './telas/TelaBloco10'
import TelaBoasVindas from './telas/TelaBoasVindas'
import TelaColetaDirigida from './telas/TelaColetaDirigida'
import TelaConsentimento from './telas/TelaConsentimento'
import TelaDefinirSenha from './telas/TelaDefinirSenha'
import TelaEquipeCaso from './telas/TelaEquipeCaso'
import TelaFichas from './telas/TelaFichas'
import TelaInicio from './telas/TelaInicio'
import TelaLogin from './telas/TelaLogin'
import TelaOperador from './telas/TelaOperador'
import TelaPergunta from './telas/TelaPergunta'
import TelaPlano from './telas/TelaPlano'
import TelaProgresso from './telas/TelaProgresso'
import TelaRecalculo from './telas/TelaRecalculo'
import TelaRespostas from './telas/TelaRespostas'
import TelaRevisao from './telas/TelaRevisao'

function casoDaUrl(): string {
  const busca = new URLSearchParams(window.location.search)
  return busca.get('caso') ?? ''
}

/**
 * Manda ao Início uma conta que não é revisora — `AC-80`, `T-170`.
 *
 * **Por que um componente, e não duas linhas no corpo de `App`.** Ali a
 * chamada a `substituirRota` acontecia DURANTE a renderização: ela muta o
 * histórico do navegador e dispara um evento que faz `useRota` chamar
 * `setState` — efeito colateral no meio do render, que o React avisa em
 * desenvolvimento e cuja ordem não é garantida.
 *
 * `useEffect` é o lugar de efeito colateral. O Início aparece no mesmo
 * quadro; o que muda é que a troca de URL acontece depois da renderização,
 * não no meio dela.
 */
function RedirecionarAoInicio({
  casoId,
  irPara,
}: {
  casoId: string
  irPara: (rota: Rota) => void
}) {
  useEffect(() => {
    // `substituirRota` em vez de `irPara`: não deixa no histórico um passo
    // que o "voltar" reapresentaria.
    substituirRota({ tela: 'inicio' })
  }, [])

  return <TelaInicio casoId={casoId} irPara={irPara} />
}

export default function App() {
  /**
   * O caso da sessão — `T-154`.
   *
   * `?caso=` na URL continua funcionando (link profundo), mas deixou de ser
   * a ÚNICA fonte: `GET /api/conta/eu` responde quem é a sessão e qual é o
   * caso dela. Sem isso, recarregar a página perdia o caso — e quem entrasse
   * sem o parâmetro ficava preso na tela de login com a sessão instalada.
   *
   * Não é decisão do cliente: o servidor reverifica a posse a cada
   * requisição (`404` para caso alheio, indistinguível de inexistente).
   */
  const [casoId, setCasoId] = useState(casoDaUrl)
  const [rota, irPara] = useRota()
  /**
   * O papel da conta — `RF-59`, `AC-80`.
   *
   * **Não é autorização.** Serve para a interface não oferecer ao aluno o
   * caminho para a fila e o painel: quem vê "Fila", clica e recebe `403`
   * conclui que o sistema está quebrado, ou que há algo seu que não consegue
   * ver. Quem autoriza é o servidor, que reconsulta o banco a cada
   * requisição — forjar isto aqui não dá acesso a nada.
   *
   * `null` = ainda perguntando ao servidor; `true`/`false` = a resposta de
   * `/api/conta/eu`.
   *
   * **`null` NÃO conta como não-revisor — `T-170`.** Contava, e o efeito
   * era um revisor de verdade sendo expulso de `#equipe-fila` ao recarregar
   * a página: o redirecionamento acontecia antes de a resposta chegar, e o
   * `replaceState` destruía a URL. Enquanto é `null`, o redirecionamento
   * não decide nada — quem nega acesso é o servidor, que reconsulta o banco
   * a cada requisição.
   */
  const [eRevisor, setERevisor] = useState<boolean | null>(null)

  /**
   * Há sessão? — `T-174`.
   *
   * `null` = ainda perguntando ao servidor; `false` = `GET /api/conta/eu`
   * respondeu `401`, ou seja, não há sessão nenhuma.
   *
   * **Por que não bastava o `casoId`.** A tela de entrada era decidida por
   * `!casoId`, e o `?caso=` da URL preenche `casoId` antes de qualquer
   * pergunta ao servidor. Quem abrisse o link `?caso=<id>` sem estar
   * autenticado — o link que `subir_demo.py` imprime, e o que chegaria a um
   * aluno por e-mail — caía no Início com "Não foi possível carregar a sua
   * próxima etapa" e **nenhum caminho para entrar**: sem formulário, sem
   * botão. A única saída era apagar o `?caso=` da barra de endereços.
   *
   * O caso do link não se perde: `casoId` continua no estado, e depois do
   * login o aluno chega nele.
   */
  const [temSessao, setTemSessao] = useState<boolean | null>(null)

  /**
   * Pergunta ao servidor quem é a sessão — uma vez, na carga da página.
   *
   * **É o que faz o papel sobreviver a um F5** (`T-153`). Antes, `e_revisor`
   * só chegava na resposta do login: o revisor recarregava e perdia acesso às
   * próprias telas. Guardar em `localStorage` foi recusado — seria estado de
   * autorização cacheado no cliente, o oposto do que `isolamento.py` faz ao
   * reconsultar o banco a cada requisição.
   *
   * `401` é o caminho normal de quem não entrou ainda: cai em não-revisor e
   * sem caso, que é exatamente o estado da tela de entrada.
   */
  useEffect(() => {
    let ativo = true
    obterSessao()
      .then((sessao) => {
        if (!ativo) return
        setERevisor(sessao.e_revisor)
        setTemSessao(true)
        // O `?caso=` da URL tem precedência: é um link profundo deliberado,
        // e o servidor recusa se não for da conta.
        if (!casoDaUrl() && sessao.CASO_ID) setCasoId(sessao.CASO_ID)
      })
      .catch(() => {
        if (!ativo) return
        setERevisor(false)
        // `401` — não há sessão. `T-174`: é isto que leva à tela de entrada,
        // mesmo com `?caso=` na URL.
        setTemSessao(false)
      })
    return () => {
      ativo = false
    }
  }, [])

  /**
   * O payload de `/inicio`, elevado — `RF-58`.
   *
   * Quatro telas (Início, Progresso, Aguardando, Recálculo) leem o MESMO
   * payload: fase, mensagem, progresso e versão do plano. Uma requisição por
   * tela faria quatro chamadas para o mesmo dado e, pior, abriria a janela
   * para duas telas discordarem sobre a fase do caso — que é exatamente o
   * tipo de divergência que `RF-58` existe para fechar.
   *
   * `TelaInicio` continua buscando por conta própria: ela é o ponto de
   * entrada e precisa do dado fresco a cada visita.
   */
  const [inicio, setInicio] = useState<Inicio | null>(null)

  /**
   * As boas-vindas já foram dispensadas nesta visita? — `RF-66`, `AC-98`.
   *
   * O gatilho para MOSTRAR é o estado do caso (zero respostas gravadas), não
   * uma marca no cliente (`RF-67`): quem começa no computador e segue no
   * celular não vê a apresentação de novo. Este booleano só registra o
   * "Começar" **desta sessão de tela**, para que o aluno não volte à
   * apresentação ao navegar para o Início — e ele é deliberadamente efêmero:
   * recarregar a página com zero respostas mostra de novo, que é o certo,
   * porque nada foi respondido ainda.
   */
  const [boasVindasVistas, setBoasVindasVistas] = useState(false)

  useEffect(() => {
    if (!casoId) return
    let ativo = true
    obterInicio(casoId)
      .then((dados) => {
        if (ativo) setInicio(dados)
      })
      // Falha aqui degrada, não quebra: as telas que o consomem tratam
      // `null` mostrando o essencial sem o localizador nem o histórico.
      .catch(() => undefined)
    return () => {
      ativo = false
    }
  }, [casoId, rota.tela])

  /**
   * Depois de entrar: descobre o caso pelo servidor e vai ao Início.
   *
   * **`POST /api/conta/login` não devolve `CASO_ID`** — só o cadastro devolve.
   * Sem esta reconsulta, quem entrasse sem `?caso=` na URL ficava preso na
   * tela de login com a sessão já instalada: credencial aceita, aplicação
   * inalcançável. Era o beco sem saída de `T-154`.
   *
   * Quem responde é `GET /api/conta/eu`, que lê o caso e o papel do banco.
   * Se a consulta falhar, o Início ainda é o destino: ele próprio pede
   * `/inicio` e mostra o erro se não houver caso — melhor que travar o aluno
   * numa tela de login que já aceitou a senha dele.
   */
  const aoEntrar = useCallback(async () => {
    try {
      const sessao = await obterSessao()
      setERevisor(sessao.e_revisor)
      if (sessao.CASO_ID) setCasoId(sessao.CASO_ID)
    } catch {
      /* segue para o Início de qualquer forma — ver a nota acima */
    }
    irPara({ tela: 'inicio' })
  }, [irPara])

  const voltarAoInicio = useCallback(() => irPara({ tela: 'inicio' }), [irPara])

  // Sem caso na URL, a única tela possível é a de entrada — e ela não
  // depende de `CASO_ID`. `RF-58` diz que Início é o ponto de entrada do
  // aluno AUTENTICADO; antes disso, é o login.
  // `T-174`: sem sessão, a tela é a de entrada — **mesmo com `?caso=` na
  // URL**. Antes a condição era só `!casoId`, e o link profundo preenchia o
  // caso antes de qualquer pergunta ao servidor: quem abrisse o link sem
  // estar autenticado ficava preso numa mensagem de falha de carga, sem
  // nenhum caminho para entrar.
  //
  // `temSessao === null` é "ainda perguntando": não decide nada, para que a
  // tela de entrada não pisque na frente de quem já está autenticado.
  // `T-179`: a tela de definir senha vem ANTES do portão de login, e é a
  // única além da entrada que dispensa sessão.
  //
  // **Este `if` é o que faz o `switch` abaixo continuar exaustivo sem um
  // `case 'definir-senha'`.** O TypeScript estreita `Rota` depois do
  // `return`, então `definir-senha` já não é possível lá. Mover este bloco
  // para depois do `switch` faria a compilação falhar — que é o
  // comportamento desejado, não um acidente a corrigir.
  //
  // **Sem esta exceção o link do e-mail não funcionaria.** Quem clica nele
  // não tem sessão (acabou de comprar) e não consegue fazer login (a conta
  // existe, mas sem senha — `autenticar` recusa). Cairia na tela de entrada
  // e ficaria preso lá, exatamente como o `T-174` descreveu para o
  // `?caso=`.
  if (rota.tela === 'definir-senha') {
    return (
      <TelaDefinirSenha
        token={rota.token}
        // Vai para o login, onde ele usa a senha recém-criada. `irPara` e
        // não `substituirRota`: o "voltar" do navegador levaria de volta a
        // um token já consumido, e a tela diria "link inválido" — correto,
        // porém confuso. Empilhar mantém o histórico honesto.
        aoDefinir={() => irPara({ tela: 'entrada' })}
      />
    )
  }

  if ((!casoId || temSessao === false) && rota.tela !== 'entrada') {
    return (
      <TelaLogin
        onEntrou={(sessao) => {
          setERevisor(sessao?.e_revisor ?? false)
          setTemSessao(true)
          void aoEntrar()
        }}
      />
    )
  }

  // `AC-80`: uma conta que não é revisora não alcança tela de equipe nem
  // digitando o hash. A interface a manda ao Início em vez de deixá-la numa
  // tela que o servidor vai recusar.
  //
  // **`=== false`, não `!== true` — `T-170`.** `eRevisor` nasce `null`
  // ("ainda perguntando ao servidor") e só vira `true`/`false` quando
  // `/api/conta/eu` responde. Com `!== true`, o `null` contava como
  // não-revisor: um revisor de verdade que recarregasse a página em
  // `#equipe-fila` era expulso para o Início ANTES de a resposta chegar —
  // e o `replaceState` destruía a URL, de modo que nem o "voltar" do
  // navegador o trazia de volta.
  //
  // Enquanto é `null`, nada se decide: a tela de equipe renderiza, e o
  // servidor — que é quem autoriza, a cada requisição — recusa com `403`
  // se a conta não puder. Negar por omissão era o lado seguro para o
  // ACESSO; mas quem nega acesso é o servidor, não esta linha.
  if (eTelaDaEquipe(rota) && eRevisor === false) {
    return <RedirecionarAoInicio casoId={casoId} irPara={irPara} />
  }

  switch (rota.tela) {
    case 'entrada':
      return (
        <TelaLogin
          onEntrou={(sessao) => {
            setERevisor(sessao?.e_revisor ?? false)
            setTemSessao(true)
            void aoEntrar()
          }}
        />
      )

    case 'consentimento':
      return (
        <TelaConsentimento
          casoId={casoId}
          voltar={voltarAoInicio}
          onAceito={voltarAoInicio}
        />
      )

    case 'inicio': {
      // `AC-97`: quem ainda não respondeu nada vê primeiro o que é isto.
      // Pedir cem perguntas sobre o dinheiro de alguém sem dizer para quê é
      // pedir uma confiança que ainda não foi merecida.
      const naoComecou = inicio !== null && inicio.progresso.respondidas === 0
      if (naoComecou && !boasVindasVistas) {
        return <TelaBoasVindas comecar={() => setBoasVindasVistas(true)} />
      }
      return (
        <TelaInicio casoId={casoId} irPara={irPara} eRevisor={eRevisor === true} />
      )
    }

    case 'progresso':
      return (
        <TelaProgresso
          inicio={inicio}
          voltar={voltarAoInicio}
          continuar={() => irPara({ tela: 'pergunta' })}
          // `#fichas` é o CRUD de dívidas (`RF-53`, `AC-04`). No protótipo
          // o acesso vinha de "Continuar de onde parei" (linha 285); aqui é
          // um segundo caminho explícito, porque "continuar" agora vai para
          // a próxima pergunta. Sem isto o aluno não tem como cadastrar nem
          // remover dívida — regressão que a morte da barra de abas criou.
          verFichas={() => irPara({ tela: 'fichas' })}
        />
      )

    case 'fichas':
      return (
        <TelaFichas
          casoId={casoId}
          escopo="DIVIDA_ID"
          titulo="Dívida"
          voltar={voltarAoInicio}
          onAbrirFicha={(itemId) => irPara({ tela: 'pergunta', itemId })}
        />
      )

    /**
     * `RF-68`/`RF-69` (T-160) — a revisão, e a correção de uma resposta.
     *
     * **Uma rota, dois estados, a MESMA tela de pergunta.** Sem `idPergunta`
     * é a lista; com ele é a correção daquela resposta. A correção reusa
     * `TelaPergunta` inteira: ela já monta todo tipo de campo e já grava pela
     * rota única (`RF-69`). Uma tela de edição própria seria uma segunda
     * montagem de campo e uma segunda chamada de gravação — duas chances de
     * divergir da coleta sobre a mesma pergunta.
     *
     * O que muda entre os dois usos de `TelaPergunta` é só o DESTINO depois
     * de gravar: daqui volta-se à lista (o aluno veio dela); de `#pergunta`
     * segue-se para a próxima pendente, que é a coleta.
     */
    case 'respostas': {
      if (rota.idPergunta) {
        const voltarARevisao = () => irPara({ tela: 'respostas' })
        return (
          <TelaPergunta
            casoId={casoId}
            voltar={voltarARevisao}
            onColetaCompleta={voltarARevisao}
            idPergunta={rota.idPergunta}
            itemId={rota.itemId}
            // `AC-103`: gravada a correção, a revisão reabre — com o valor
            // novo, porque ela relê o servidor a cada visita.
            aoCorrigir={voltarARevisao}
          />
        )
      }
      return (
        <TelaRespostas
          casoId={casoId}
          voltar={voltarAoInicio}
          editar={(id, item) =>
            irPara({ tela: 'respostas', idPergunta: id, itemId: item ?? undefined })
          }
        />
      )
    }

    case 'pergunta':
      return (
        <TelaPergunta
          casoId={casoId}
          voltar={voltarAoInicio}
          onColetaCompleta={() => irPara({ tela: 'calculando' })}
          // `AC-102`: a rota já carregava estes dois desde `T-149`; a tela é
          // que os ignorava, pedindo sempre a PRÓXIMA pergunta. Passá-los é o
          // conserto do defeito — `#pergunta/{ID}` volta a significar o que a
          // URL diz.
          idPergunta={rota.idPergunta}
          itemId={rota.itemId}
          // `RF-70`, `AC-105`: o caminho para trás durante a coleta. Ele leva
          // para `#pergunta/{ID}`, não para a revisão: o aluno não saiu da
          // coleta, só andou um passo nela.
          abrirPergunta={(id, item) =>
            irPara({ tela: 'pergunta', idPergunta: id, itemId: item ?? undefined })
          }
        />
      )

    case 'calculando':
      return (
        <TelaCalculando
          casoId={casoId}
          voltar={voltarAoInicio}
          onTerminou={voltarAoInicio}
        />
      )

    case 'aguardando':
      return <TelaAguardando inicio={inicio} voltar={voltarAoInicio} />

    case 'plano':
      return <TelaPlano casoId={casoId} voltar={voltarAoInicio} />

    case 'bloco10':
      return <TelaBloco10 casoId={casoId} voltar={voltarAoInicio} />

    case 'coleta-dirigida':
      return (
        <TelaColetaDirigida casoId={casoId} bloco={rota.bloco} voltar={voltarAoInicio} />
      )

    case 'acoes':
      return (
        <TelaAcoes
          casoId={casoId}
          voltar={voltarAoInicio}
          abrirAcao={(id) => irPara({ tela: 'acao', acaoId: id })}
        />
      )

    case 'acao':
      return (
        <TelaAcao
          casoId={casoId}
          acaoId={rota.acaoId}
          voltar={() => irPara({ tela: 'acoes' })}
        />
      )

    case 'recalculo':
      return <TelaRecalculo inicio={inicio} voltar={voltarAoInicio} />

    case 'equipe-fila':
      return (
        <TelaRevisao
          voltar={voltarAoInicio}
          abrirCaso={(id) => irPara({ tela: 'equipe-caso', casoId: id })}
        />
      )

    case 'equipe-caso':
      return (
        <TelaEquipeCaso
          casoId={rota.casoId}
          voltar={() => irPara({ tela: 'equipe-fila' })}
        />
      )

    case 'equipe-painel':
      return <TelaOperador voltar={() => irPara({ tela: 'equipe-fila' })} />
  }
}
