/**
 * A rede de segurança da aplicação — `T-169`.
 *
 * **Por que existe.** Sem ela, qualquer exceção não tratada dentro de um
 * componente derruba a árvore inteira: o React desmonta tudo e o aluno fica
 * com uma **tela branca**, sem mensagem, sem botão, sem caminho. Foi o que
 * uma revisão encontrou em `TelaInicio`, onde um `destino` desconhecido
 * vindo do servidor fazia `texto.rotulo` lançar.
 *
 * Aquele defeito específico está corrigido, mas a classe dele não: `app/`
 * tem dezenas de leituras de campo que dependem do payload do servidor, e
 * um servidor mais novo que este cliente é a situação normal durante um
 * deploy. Corrigir caso a caso é necessário; ter onde cair quando escapar
 * um é o que impede que o próximo vire tela branca.
 *
 * **Não substitui tratamento de erro.** As telas continuam tratando falha
 * de rede com `aviso-erro` e `role="alert"`, que é a mensagem certa para
 * "não consegui carregar". Este limite é para o que ninguém previu.
 *
 * **Por que classe.** `componentDidCatch`/`getDerivedStateFromError` não
 * têm equivalente em Hook — é a única parte do React que ainda exige
 * classe, e a própria documentação oficial diz isso.
 */
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface LimiteDeErroProps {
  children: ReactNode
}

interface LimiteDeErroState {
  falhou: boolean
}

export default class LimiteDeErro extends Component<LimiteDeErroProps, LimiteDeErroState> {
  state: LimiteDeErroState = { falhou: false }

  static getDerivedStateFromError(): LimiteDeErroState {
    return { falhou: true }
  }

  componentDidCatch(erro: Error, info: ErrorInfo): void {
    // O console é o único destino disponível: o projeto não tem coletor de
    // erro de cliente, e inventar um endpoint aqui seria infraestrutura que
    // ninguém pediu. O que importa é que o erro não desapareça em silêncio
    // — quem abrir o console durante o piloto encontra a pilha.
    console.error('[PIQ] erro não tratado na interface', erro, info.componentStack)
  }

  render(): ReactNode {
    if (!this.state.falhou) return this.props.children

    return (
      <div className="flex justify-center">
        <div className="flex min-h-screen w-full max-w-tela flex-col">
          <div className="top">
            <span />
            <span />
          </div>
          <div className="corpo">
            <h1>Algo deu errado por aqui</h1>
            {/*
              A redação é deliberada. O aluno não precisa saber o que
              quebrou — precisa saber que (a) o problema é nosso, (b) as
              respostas dele estão a salvo, e (c) há o que fazer agora.
              `RF-10` garante o (b): toda resposta é gravada antes da
              próxima pergunta aparecer.
            */}
            <p className="lead">
              O problema é do nosso lado, não do que você respondeu. Tudo o que
              você já preencheu continua guardado.
            </p>
            <p className="nota">
              Recarregue a página para continuar de onde parou. Se acontecer de
              novo, fale com a equipe.
            </p>
          </div>
          <div className="acoes">
            {/*
              `location.reload()` e não `setState({falhou:false})`: o estado
              que produziu a exceção continua na memória, e voltar a
              renderizar a mesma árvore reproduziria o mesmo erro. Recarregar
              refaz a sessão a partir do servidor, que é a fonte (`RF-67`).
            */}
            <button
              type="button"
              className="btn-primario"
              onClick={() => window.location.reload()}
            >
              Recarregar a página
            </button>
          </div>
        </div>
      </div>
    )
  }
}
