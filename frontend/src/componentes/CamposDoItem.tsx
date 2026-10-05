/**
 * Os campos de um item de ficha curta — `T-307`, `T-314`, `T-319`, `T-320`.
 *
 * Um lugar só para o que o formulário do item (`TelaFormulario`) e a ficha
 * nova na tela da pergunta-gatilho (`TelaPergunta`, `T-319`) fazem igual:
 * desenhar as perguntas com a thread de `complementares`, achar o que está
 * em branco e gravar em sequência pela rota de `RF-69` (mãe antes das
 * filhas). Quais perguntas aparecem é sempre do servidor (`RF-45`).
 */
import { formatarTaxaDoServidor } from '../mascaras'
import { gravarResposta } from '../services/api'
import type { Pergunta } from '../tipos'
import CampoPergunta from './CampoPergunta'

/**
 * O valor com que a pergunta reabre (`AC-01`, `AC-102`).
 *
 * `T-204`: `ESCALA_0_10`/`NUMERO` chegam como `int` do servidor, apesar do
 * tipo; `String` normaliza, senão `"7" === 7` falha e a nota salva não
 * aparece marcada.
 */
export function valorInicial(pergunta: Pergunta): string | string[] {
  if (pergunta.valores_marcados.length > 0) return pergunta.valores_marcados
  const atual = pergunta.valor_atual
  if (atual === null) return ''
  // `T-335`: o servidor guarda a fração (`0.08`); o campo, que já tem o "%"
  // ao lado, reabre com o percentual (`8`).
  if (pergunta.tipo === 'TAXA' && !Array.isArray(atual)) return formatarTaxaDoServidor(String(atual))
  // `T-294`: opção com campo R$ em outra variável reabre com os dois.
  if (pergunta.valor_do_campo != null && !Array.isArray(atual)) {
    return [String(atual), pergunta.valor_do_campo]
  }
  return Array.isArray(atual) ? atual : String(atual)
}

/** O que o aluno preencheu numa pergunta da thread (`T-307`). */
export interface EstadoDaFilha {
  valor: string | string[]
  naoSei: boolean
  erro: string | null
  aviso: string | null
}

export function chaveDa(pergunta: Pergunta): string {
  return `${pergunta.ID}|${pergunta.item_id ?? ''}`
}

/**
 * As perguntas que a opção escolhida abre — `T-307`, `RF-99`.
 *
 * Consulta à tabela que o servidor montou, pelo valor escolhido: nenhuma
 * condição é avaliada aqui (`RF-45`). "Não sei" marcado não abre nada.
 */
export function filhasAbertas(
  pergunta: Pergunta,
  valor: string | string[],
  naoSei: boolean,
): Pergunta[] {
  if (naoSei || !pergunta.complementares) return []
  const escolhida = Array.isArray(valor) ? (valor[0] ?? '') : valor
  return pergunta.complementares[escolhida] ?? []
}

/** `T-320`: junto do campo que falta, o resumo e o nome — aprovados pelo produto. */
export const MENSAGEM_CAMPO_EM_BRANCO = 'Responda esta pergunta.'
export const MENSAGEM_FALTAM_CAMPOS = 'Responda as perguntas destacadas antes de salvar.'
export const MENSAGEM_SEM_NOME = 'Informe o nome da despesa.'

/**
 * `T-320` (`RF-107`): as perguntas na tela — e as filhas abertas — sem
 * resposta nem "Não sei". Todas são exigíveis: o servidor só manda as que a
 * retomada exige no item, e recusa a conclusão se faltar alguma.
 */
export function emBranco(
  perguntas: Pergunta[],
  estadoDe: (pergunta: Pergunta) => EstadoDaFilha,
): Pergunta[] {
  const vazio = ({ valor, naoSei }: EstadoDaFilha) =>
    !naoSei && (Array.isArray(valor) ? (valor[0] ?? '') === '' : valor.trim() === '')
  return perguntas.flatMap((pergunta) => {
    const estado = estadoDe(pergunta)
    return [
      ...(vazio(estado) ? [pergunta] : []),
      ...filhasAbertas(pergunta, estado.valor, estado.naoSei).filter((filha) =>
        vazio(estadoDe(filha)),
      ),
    ]
  })
}

/**
 * Grava as perguntas na ordem, mãe antes das filhas (`T-307`): é a mãe
 * gravada que abre cada filha no servidor. Um erro não interrompe as outras.
 * `itemId` substitui o das perguntas — a ficha nova (`T-319`) chega com um
 * provisório e grava no item que a mãe criou.
 */
export async function gravarEmSequencia(
  casoId: string,
  perguntas: Pergunta[],
  estadoDe: (pergunta: Pergunta) => EstadoDaFilha,
  itemId?: string,
): Promise<{ estados: Record<string, EstadoDaFilha>; falhou: boolean; avisou: boolean }> {
  const estados: Record<string, EstadoDaFilha> = {}
  let falhou = false
  let avisou = false
  async function gravar(pergunta: Pergunta): Promise<boolean> {
    const estado: EstadoDaFilha = { ...estadoDe(pergunta), erro: null, aviso: null }
    estados[chaveDa(pergunta)] = estado
    try {
      const confirmacao = await gravarResposta(casoId, {
        idPergunta: pergunta.ID,
        valor: estado.naoSei ? undefined : estado.valor,
        itemId: itemId ?? pergunta.item_id,
        naoSei: estado.naoSei,
      })
      const avisos = confirmacao.avisos ?? []
      if (avisos.length) {
        estado.aviso = avisos.map((aviso) => aviso.mensagem).join(' ')
        avisou = true
      }
      return true
    } catch (falha) {
      estado.erro = falha instanceof Error ? falha.message : 'Não foi possível salvar.'
      falhou = true
      return false
    }
  }
  for (const pergunta of perguntas) {
    const estado = estadoDe(pergunta)
    if (!(await gravar(pergunta))) continue
    for (const filha of filhasAbertas(pergunta, estado.valor, estado.naoSei)) {
      await gravar(filha)
    }
  }
  return { estados, falhou, avisou }
}

/** O nome da despesa que pede nome (`T-217`, `T-316`); o servidor valida. */
export function CampoNome({
  id,
  valor,
  erro,
  onMudar,
}: {
  id: string
  valor: string
  erro: string | null
  onMudar: (nome: string) => void
}) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id}>Nome da despesa</label>
      <input
        id={id}
        className="campo-texto"
        maxLength={60}
        value={valor}
        aria-invalid={erro ? true : undefined}
        onChange={(evento) => onMudar(evento.target.value)}
      />
      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}
    </div>
  )
}

/** As perguntas do item, cada uma com a thread das que a opção abre. */
export default function CamposDoItem({
  perguntas,
  estadoDe,
  mudar,
}: {
  perguntas: Pergunta[]
  estadoDe: (pergunta: Pergunta) => EstadoDaFilha
  mudar: (pergunta: Pergunta, mudanca: Partial<EstadoDaFilha>) => void
}) {
  return (
    <>
      {perguntas.map((pergunta) => {
        const estado = estadoDe(pergunta)
        const filhas = filhasAbertas(pergunta, estado.valor, estado.naoSei)
        return (
          <div key={chaveDa(pergunta)} className="flex flex-col gap-2">
            <Campo pergunta={pergunta} estado={estado} mudar={mudar} />
            {filhas.length > 0 && (
              <div
                key={Array.isArray(estado.valor) ? estado.valor[0] : estado.valor}
                role="group"
                aria-label="Perguntas abertas pela sua resposta"
                className="thread"
              >
                {filhas.map((filha) => (
                  <Campo
                    key={chaveDa(filha)}
                    pergunta={filha}
                    estado={estadoDe(filha)}
                    mudar={mudar}
                  />
                ))}
              </div>
            )}
          </div>
        )
      })}
    </>
  )
}

function Campo({
  pergunta,
  estado,
  mudar,
}: {
  pergunta: Pergunta
  estado: EstadoDaFilha
  mudar: (pergunta: Pergunta, mudanca: Partial<EstadoDaFilha>) => void
}) {
  return (
    <div className="flex flex-col gap-2">
      <CampoPergunta
        pergunta={{ ...pergunta, aviso: estado.aviso ?? pergunta.aviso }}
        valor={estado.valor}
        naoSei={estado.naoSei}
        onValor={(novo) => mudar(pergunta, { valor: novo })}
        onNaoSei={(marcado) => mudar(pergunta, { naoSei: marcado })}
      />
      {estado.erro && (
        <p role="alert" className="aviso-erro">
          {estado.erro}
        </p>
      )}
    </div>
  )
}
