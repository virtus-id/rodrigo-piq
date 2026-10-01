/**
 * Fichas repetíveis — tela `fichas` do protótipo (`RF-04`, `RF-53`).
 *
 * 108 das 247 perguntas têm `escopo_repeticao != NENHUM`. Sem esta tela o
 * aluno não cadastra nem uma dívida, e o Bloco 5 — o núcleo do PIQ — fica
 * inalcançável.
 *
 * `completa` vem do servidor (`itens_em_aberto`, `T-201`), nunca é recontado
 * aqui: obrigatoriedade é regra, e regra mora num lugar só.
 *
 * `T-259` (`RF-90`): a margem nasce e aparece DENTRO do seu vínculo — nunca
 * um total entre vínculos (`AC-138`). Remover um item com dependentes lista
 * o que perde o vínculo antes de confirmar (`EC-35`).
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import TrilhaDaColeta from '../componentes/TrilhaDaColeta'
import {
  criarFicha,
  listarFichas,
  nomearFicha,
  obterProximaPergunta,
  removerFicha,
} from '../services/api'
import type { Ficha, ParteDaTrilha } from '../tipos'

/**
 * Os nomes de cada escopo que tem tela — `T-212`, títulos da §11. É o ÚNICO
 * lugar do frontend que os lista. Um escopo fora daqui não tem tela:
 * `ACAO_ID` é do acompanhamento (Bloco 11), não da coleta inicial.
 * `ITEM_DESPESA` (`T-217`): as fichas nascem do checklist; a lista serve
 * para dar nome a "Outro" e adicionar despesa não listada.
 */
export const TITULOS_POR_ESCOPO: Readonly<
  Record<
    string,
    { titulo: string; tituloPlural: string; possessivo?: string; feminino?: boolean }
  >
> = {
  DIVIDA_ID: { titulo: 'Dívida', tituloPlural: 'Dívidas', feminino: true },
  RENDA_ADICIONAL_ID: {
    titulo: 'Renda adicional',
    tituloPlural: 'Rendas adicionais',
    feminino: true,
  },
  DESPESA_NAO_MENSAL_ID: {
    titulo: 'Despesa não mensal',
    tituloPlural: 'Despesas não mensais',
    feminino: true,
  },
  // `T-270` (RF-98): redação aprovada pelo produto (`T-289`, 2026-09-30).
  RECURSO_EXTRAORDINARIO_ID: {
    titulo: 'Valor extraordinário',
    tituloPlural: 'Valores extraordinários',
  },
  VINCULO_ID: { titulo: 'Vínculo', tituloPlural: 'Vínculos', possessivo: 'Seus' },
  MARGEM_ID: { titulo: 'Margem', tituloPlural: 'Margens', feminino: true },
  ITEM_DESPESA: { titulo: 'Despesa', tituloPlural: 'Despesas', feminino: true },
}

interface TelaFichasProps {
  casoId: string
  escopo: string
  /** O nome de UM item — "Dívida". Compõe o rótulo de cada linha e do botão. */
  titulo: string
  /**
   * O plural de `titulo` — "Dívidas". Prop própria, e não `titulo + "s"`:
   * plural em português não é regular ("ação" → "ações", "margem" →
   * "margens"), e um `+ "s"` que hoje acerta por acaso (só existe o
   * escopo "Dívida") quebraria em silêncio no próximo escopo que usar
   * esta tela.
   */
  tituloPlural: string
  /** "Suas dívidas", mas "Seus vínculos". */
  possessivo?: string
  /** "Adicionar outra dívida", mas "Adicionar outro vínculo" (`T-311`). */
  feminino?: boolean
  voltar?: () => void
  /**
   * `idPergunta` é a pergunta em que a ficha abre — a próxima em branco
   * daquele item, decidida pelo servidor (`RF-45`, `T-203`).
   */
  onAbrirFicha: (itemId: string, idPergunta: string) => void
  /**
   * Segue a coleta — `T-212`. Não exige ficha: se criar ao menos uma é
   * obrigatório ainda é questão aberta para o especialista.
   */
  onContinuar?: () => void
}

export default function TelaFichas({
  casoId,
  escopo,
  titulo,
  tituloPlural,
  possessivo = 'Suas',
  feminino = false,
  voltar,
  onAbrirFicha,
  onContinuar,
}: TelaFichasProps) {
  const [fichas, setFichas] = useState<Ficha[]>([])
  const [escopoPai, setEscopoPai] = useState<string | null>(null)
  const [escoposFilhos, setEscoposFilhos] = useState<string[]>([])
  const [trilha, setTrilha] = useState<ParteDaTrilha[] | null>(null)
  const [aConfirmar, setAConfirmar] = useState<{ ficha: Ficha; escopo: string } | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const carregar = useCallback(async () => {
    setCarregando(true)
    setErro(null)
    try {
      const dados = await listarFichas(casoId, escopo)
      setFichas(dados.fichas)
      setEscopoPai(dados.escopo_pai ?? null)
      setEscoposFilhos(dados.escopos_filhos ?? [])
      setTrilha(dados.trilha ?? null)
    } catch {
      setErro('Não foi possível carregar as fichas.')
    } finally {
      setCarregando(false)
    }
  }, [casoId, escopo])

  useEffect(() => {
    void carregar()
  }, [carregar])

  async function aoAdicionar(escopoAlvo = escopo, itemPaiId?: string) {
    try {
      const { ficha } = await criarFicha(casoId, escopoAlvo, itemPaiId)
      // `T-311`: o item novo abre direto na primeira pergunta. A despesa
      // não listada fica na lista: ela pede nome antes (`T-217`).
      if (!ficha.pede_nome) {
        await aoAbrir(ficha.item_id)
        return
      }
      await carregar()
    } catch {
      setErro('Não foi possível adicionar.')
    }
  }

  async function aoAbrir(itemId: string) {
    try {
      const dados = await obterProximaPergunta(casoId, itemId)
      if (!dados.pergunta) throw new Error('ficha sem pergunta')
      onAbrirFicha(itemId, dados.pergunta.ID)
    } catch {
      setErro('Não foi possível abrir a ficha.')
    }
  }

  async function aoNomear(itemId: string, nome: string) {
    try {
      await nomearFicha(casoId, escopo, itemId, nome)
      await carregar()
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Não foi possível salvar o nome.')
    }
  }

  function pedirRemocao(ficha: Ficha, escopoDoItem = escopo) {
    const { margens = [], dividas = [] } = ficha.dependentes ?? {}
    if (margens.length + dividas.length > 0) setAConfirmar({ ficha, escopo: escopoDoItem })
    else void aoRemover(ficha.item_id, escopoDoItem)
  }

  async function aoRemover(itemId: string, escopoDoItem = escopo) {
    setAConfirmar(null)
    try {
      await removerFicha(casoId, escopoDoItem, itemId)
      await carregar()
    } catch {
      setErro('Não foi possível remover.')
    }
  }

  return (
    <Tela
      titulo={`${possessivo} ${tituloPlural.toLowerCase()}`}
      voltar={voltar}
      // `T-310` (RF-100): a trilha das cinco partes, do servidor.
      lateral={trilha ? <TrilhaDaColeta trilha={trilha} /> : undefined}
      onde={fichas.length > 0 ? `${fichas.length} cadastrada${fichas.length === 1 ? '' : 's'}` : undefined}
      acoes={
        <>
          {onContinuar && <Botao onClick={onContinuar}>Continuar</Botao>}
          {/* A ficha com pai (a margem) só nasce dentro dele (`AC-137`). */}
          {!escopoPai && (
            <Botao variante="secundario" onClick={() => void aoAdicionar()}>
              {/* `T-311`: com a primeira já criada, o convite é para outra. */}
              + Adicionar{' '}
              {fichas.length > 0 ? `${feminino ? 'outra' : 'outro'} ` : ''}
              {titulo.toLowerCase()}
            </Botao>
          )}
        </>
      }
    >
      <p className="lead">Uma ficha para cada item. Toque em uma para completar.</p>

      {/* Só na primeira carga — ver a nota em `TelaRevisao` (T-164). Aqui a
          recarga vem de adicionar ou remover ficha, e o esqueleto sobre a
          lista existente faria a tela piscar a cada operação. */}
      {carregando && fichas.length === 0 && (
        <Esqueleto forma="lista" anuncio="Carregando suas fichas" itens={3} />
      )}

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}

      {aConfirmar && (
        <ConfirmarRemocao
          nome={aConfirmar.ficha.rotulo ?? `${titulo} ${aConfirmar.ficha.item_id}`}
          dependentes={aConfirmar.ficha.dependentes ?? { margens: [], dividas: [] }}
          onConfirmar={() => void aoRemover(aConfirmar.ficha.item_id, aConfirmar.escopo)}
          onCancelar={() => setAConfirmar(null)}
        />
      )}

      {!carregando && fichas.length === 0 && (
        <p role="status" className="nota">
          Nenhuma ficha cadastrada ainda.
        </p>
      )}

      <ul className="lista list-none p-0">
        {fichas.map((ficha, indice) => (
          <li key={ficha.item_id} className="item">
            <span className="num">{indice + 1}</span>
            <div className="min-w-0 flex-1">
              <button
                type="button"
                className="text-left font-bold text-accent"
                onClick={() => void aoAbrir(ficha.item_id)}
              >
                {ficha.rotulo ?? `${titulo} ${ficha.item_id}`}
              </button>
              <small className="block text-muted">
                {ficha.campos.length} campo{ficha.campos.length === 1 ? '' : 's'}
              </small>
              {ficha.pede_nome && (
                <NomeDaFicha
                  itemId={ficha.item_id}
                  nomeAtual={ficha.rotulo}
                  onSalvar={(nome) => void aoNomear(ficha.item_id, nome)}
                />
              )}
              {escoposFilhos.map((filho) => {
                const nomes = TITULOS_POR_ESCOPO[filho]
                if (!nomes) return null
                return (
                  <div key={filho} className="mt-2">
                    <ul
                      className="list-none p-0"
                      aria-label={`${nomes.tituloPlural} de ${ficha.rotulo ?? `${titulo} ${ficha.item_id}`}`}
                    >
                      {(ficha.margens ?? []).map((margem) => (
                        <li key={margem.item_id} className="flex items-center gap-2">
                          <button
                            type="button"
                            className="text-left text-accent"
                            onClick={() => void aoAbrir(margem.item_id)}
                          >
                            {margem.rotulo ?? `${nomes.titulo} ${margem.item_id}`}
                          </button>
                          <span
                            className={`chip ${margem.completa ? 'bg-accent-soft text-accent' : 'bg-warn-soft text-warn'}`}
                          >
                            {margem.completa ? 'Completa' : 'Pendência'}
                          </span>
                          <button
                            type="button"
                            aria-label={`Remover ${margem.rotulo ?? `${nomes.titulo} ${margem.item_id}`}`}
                            className="min-h-toque px-3 text-muted"
                            onClick={() => pedirRemocao(margem, filho)}
                          >
                            ✕
                          </button>
                        </li>
                      ))}
                    </ul>
                    <Botao
                      variante="secundario"
                      onClick={() => void aoAdicionar(filho, ficha.item_id)}
                    >
                      + Adicionar {nomes.titulo.toLowerCase()}
                    </Botao>
                  </div>
                )
              })}
            </div>
            <span
              className={`chip ${ficha.completa ? 'bg-accent-soft text-accent' : 'bg-warn-soft text-warn'}`}
            >
              {ficha.completa ? 'Completa' : 'Pendência'}
            </span>
            <button
              type="button"
              aria-label={`Remover ${ficha.rotulo ?? `${titulo} ${ficha.item_id}`}`}
              className="min-h-toque px-3 text-muted"
              onClick={() => pedirRemocao(ficha)}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>
    </Tela>
  )
}

/**
 * `EC-35` — antes de remover, o que perde o pai: essas fichas voltam a ter
 * pendência (o servidor decide; aqui só se lista).
 */
function ConfirmarRemocao({
  nome,
  dependentes,
  onConfirmar,
  onCancelar,
}: {
  nome: string
  dependentes: { margens: string[]; dividas: string[] }
  onConfirmar: () => void
  onCancelar: () => void
}) {
  const itens = [
    ...dependentes.margens.map((id) => `${TITULOS_POR_ESCOPO.MARGEM_ID.titulo} ${id}`),
    ...dependentes.dividas.map((id) => `${TITULOS_POR_ESCOPO.DIVIDA_ID.titulo} ${id}`),
  ]
  return (
    <div role="alertdialog" aria-labelledby="confirmar-remocao" className="aviso-erro">
      <p id="confirmar-remocao">
        Remover {nome}? Estes itens ficam sem vínculo e voltam a ter pendência:
      </p>
      <ul>
        {itens.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Botao onClick={onConfirmar}>Remover assim mesmo</Botao>
        <Botao variante="secundario" onClick={onCancelar}>
          Cancelar
        </Botao>
      </div>
    </div>
  )
}

/**
 * O nome curto de "Outro" e da despesa não listada (`T-217`, §11: "texto
 * curto"). O servidor valida; aqui só o limite do campo, o mesmo dele.
 */
function NomeDaFicha({
  itemId,
  nomeAtual,
  onSalvar,
}: {
  itemId: string
  nomeAtual: string | null
  onSalvar: (nome: string) => void
}) {
  const [nome, setNome] = useState(nomeAtual ?? '')
  const id = `nome-${itemId}`
  return (
    <form
      className="mt-2 flex flex-wrap items-end gap-2"
      onSubmit={(evento) => {
        evento.preventDefault()
        if (nome.trim()) onSalvar(nome.trim())
      }}
    >
      <div className="min-w-0 flex-1">
        <label htmlFor={id}>Nome da despesa</label>
        <input
          id={id}
          className="campo-texto"
          maxLength={60}
          value={nome}
          onChange={(evento) => setNome(evento.target.value)}
        />
      </div>
      <Botao variante="secundario" type="submit">
        Salvar nome
      </Botao>
    </form>
  )
}
