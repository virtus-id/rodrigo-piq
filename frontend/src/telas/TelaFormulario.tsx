/**
 * Ficha curta em uma tela — `T-314` a `T-317` (`RF-102`–`RF-105`).
 *
 * Decisão do produto (2026-10-01): nas fichas curtas (despesa, renda
 * adicional, despesa não mensal, valor extraordinário, vínculo, margem) todas
 * as perguntas do item aparecem juntas, com um "Salvar". A dívida continua
 * pergunta a pergunta (`TelaPergunta`).
 *
 * **Quem decide o que aparece é o servidor** (`RF-45`): `GET /caso/{id}/formulario/{escopo}/{item_id}`
 * devolve as perguntas exibíveis do item e, em cada uma, as `complementares`
 * de `T-307` — trocar de opção só consulta essa tabela, como na thread da
 * pergunta. Gravar é pela rota de sempre (`RF-69`), uma a uma, mãe antes das
 * filhas; o erro de cada uma fica junto dela e as demais seguem gravadas.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import CampoPergunta from '../componentes/CampoPergunta'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import TrilhaDaColeta from '../componentes/TrilhaDaColeta'
import { gravarResposta, nomearFicha, obterFormulario } from '../services/api'
import type { FormularioDoItem, Pergunta } from '../tipos'
import { avisoDeUmPorVez, type TitulosDoEscopo } from './TelaFichas'
import { chaveDa, type EstadoDaFilha, filhasAbertas, valorInicial } from './TelaPergunta'

interface TelaFormularioProps {
  casoId: string
  escopo: string
  itemId: string
  titulos: TitulosDoEscopo
  voltar?: () => void
  /** Item concluído: volta à lista do escopo (o do pai, na margem). */
  onConcluir: (escopoDaLista: string) => void
}

function mensagem(falha: unknown): string {
  return falha instanceof Error ? falha.message : 'Não foi possível salvar.'
}

export default function TelaFormulario({
  casoId,
  escopo,
  itemId,
  titulos,
  voltar,
  onConcluir,
}: TelaFormularioProps) {
  const [formulario, setFormulario] = useState<FormularioDoItem | null>(null)
  const [estados, setEstados] = useState<Record<string, EstadoDaFilha>>({})
  const [nome, setNome] = useState('')
  const [erroNome, setErroNome] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [gravando, setGravando] = useState(false)
  /** Gravado com aviso (`T-240`): o próximo "Salvar" segue sem regravar. */
  const [comAviso, setComAviso] = useState(false)
  /** Salvo, mas a resposta abriu perguntas que ainda não estavam na tela. */
  const [abriuMais, setAbriuMais] = useState(false)

  const mostrar = useCallback((dados: FormularioDoItem) => {
    setFormulario(dados)
    setEstados({})
    setNome(dados.rotulo ?? '')
  }, [])

  useEffect(() => {
    let ativo = true
    setCarregando(true)
    obterFormulario(casoId, escopo, itemId)
      .then((dados) => {
        if (ativo) mostrar(dados)
      })
      .catch(() => {
        if (ativo) setErro('Não foi possível carregar a ficha.')
      })
      .finally(() => {
        if (ativo) setCarregando(false)
      })
    return () => {
      ativo = false
    }
  }, [casoId, escopo, itemId, mostrar])

  function estadoDe(pergunta: Pergunta): EstadoDaFilha {
    return (
      estados[chaveDa(pergunta)] ?? {
        valor: valorInicial(pergunta),
        naoSei: pergunta.respondida_como_nao_sei,
        erro: null,
        aviso: null,
      }
    )
  }

  function mudar(pergunta: Pergunta, mudanca: Partial<EstadoDaFilha>) {
    setComAviso(false)
    setEstados((atual) => ({
      ...atual,
      [chaveDa(pergunta)]: {
        ...estadoDe(pergunta),
        aviso: null,
        erro: null,
        ...mudanca,
      },
    }))
  }

  /** Relê o item: concluído volta à lista; senão mostra o que abriu. */
  async function concluir(dados: FormularioDoItem) {
    const novo = await obterFormulario(casoId, escopo, itemId)
    if (novo.completa) {
      onConcluir(dados.escopo_pai ?? escopo)
      return
    }
    mostrar(novo)
    setAbriuMais(true)
  }

  async function salvar() {
    if (!formulario) return
    setGravando(true)
    setErro(null)
    setAbriuMais(false)
    try {
      if (comAviso) {
        setComAviso(false)
        await concluir(formulario)
        return
      }
      let falhou = false
      if (formulario.pede_nome && nome.trim() !== (formulario.rotulo ?? '')) {
        try {
          await nomearFicha(casoId, escopo, itemId, nome.trim())
          setErroNome(null)
        } catch (falha) {
          setErroNome(mensagem(falha))
          falhou = true
        }
      }
      // Mãe antes das filhas (`T-307`): é a mãe gravada que abre cada filha
      // no servidor. Um erro não interrompe as outras perguntas.
      const novos: Record<string, EstadoDaFilha> = {}
      let avisou = false
      async function gravar(pergunta: Pergunta): Promise<boolean> {
        const estado: EstadoDaFilha = {
          ...estadoDe(pergunta),
          erro: null,
          aviso: null,
        }
        novos[chaveDa(pergunta)] = estado
        try {
          const confirmacao = await gravarResposta(casoId, {
            idPergunta: pergunta.ID,
            valor: estado.naoSei ? undefined : estado.valor,
            itemId: pergunta.item_id,
            naoSei: estado.naoSei,
          })
          const avisos = confirmacao.avisos ?? []
          if (avisos.length) {
            estado.aviso = avisos.map((aviso) => aviso.mensagem).join(' ')
            avisou = true
          }
          return true
        } catch (falha) {
          estado.erro = mensagem(falha)
          falhou = true
          return false
        }
      }
      for (const pergunta of formulario.perguntas) {
        const estado = estadoDe(pergunta)
        if (!(await gravar(pergunta))) continue
        for (const filha of filhasAbertas(pergunta, estado.valor, estado.naoSei)) {
          await gravar(filha)
        }
      }
      setEstados((atual) => ({ ...atual, ...novos }))
      if (falhou) return
      if (avisou) {
        setComAviso(true)
        return
      }
      await concluir(formulario)
    } catch {
      setErro('Não foi possível salvar.')
    } finally {
      setGravando(false)
    }
  }

  if (carregando || !formulario) {
    return (
      <Tela titulo={titulos.titulo} voltar={voltar}>
        {erro ? (
          <p role="alert" className="aviso-erro">
            {erro}
          </p>
        ) : (
          <Esqueleto forma="pergunta" anuncio="Carregando a ficha" />
        )}
      </Tela>
    )
  }

  const {
    posicao_do_item: posicao,
    total_de_itens: total,
    itens_concluidos: concluidos,
  } = formulario
  const pct = total > 0 ? Math.round((concluidos / total) * 100) : 0
  const concluidosTexto = `${concluidos} de ${total} ${titulos.feminino ? 'concluídas' : 'concluídos'}`

  return (
    <Tela
      titulo={formulario.rotulo ?? `${titulos.titulo} ${posicao}`}
      chave={`${escopo}/${itemId}`}
      voltar={voltar}
      // `T-317` (RF-105): "Despesa 2 de 4" — a posição vem do servidor.
      onde={`${titulos.titulo} ${posicao} de ${total}`}
      lateral={formulario.trilha ? <TrilhaDaColeta trilha={formulario.trilha} /> : undefined}
      acoes={
        <Botao onClick={() => void salvar()} disabled={gravando}>
          {gravando ? 'Salvando…' : 'Salvar'}
        </Botao>
      }
    >
      {/* `T-317`: a barra conta itens concluídos do escopo, não perguntas. */}
      <div
        className="bar"
        role="progressbar"
        aria-label={`${titulos.tituloPlural} concluíd${titulos.feminino ? 'as' : 'os'}`}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={concluidos}
        aria-valuetext={concluidosTexto}
      >
        <i style={{ width: `${pct}%` }} />
      </div>

      {/* `T-315` (RF-103) */}
      <p className="nota">{avisoDeUmPorVez(titulos)}</p>

      {formulario.pede_nome && (
        <div className="flex flex-col gap-2">
          <label htmlFor={`nome-${itemId}`}>Nome da despesa</label>
          <input
            id={`nome-${itemId}`}
            className="campo-texto"
            maxLength={60}
            value={nome}
            aria-invalid={erroNome ? true : undefined}
            onChange={(evento) => {
              setComAviso(false)
              setNome(evento.target.value)
            }}
          />
          {erroNome && (
            <p role="alert" className="aviso-erro">
              {erroNome}
            </p>
          )}
        </div>
      )}

      {formulario.perguntas.map((pergunta) => {
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

      {abriuMais && (
        <p role="status" className="nota">
          Sua resposta abriu outras perguntas. Responda e salve de novo.
        </p>
      )}

      {erro && (
        <p role="alert" className="aviso-erro">
          {erro}
        </p>
      )}
    </Tela>
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
