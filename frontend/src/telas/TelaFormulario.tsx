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
 *
 * `T-320` (`RF-107`): nada em branco — o campo sem resposta nem "Não sei" é
 * destacado e nada é gravado; o servidor confirma ao concluir
 * (`POST /caso/{id}/concluir/{escopo}/{item_id}`, `400` com o que falta).
 * `T-321` (`RF-108`): concluído, o servidor nomeia o próximo item pendente
 * do escopo, que abre em seguida; só sem nenhum a lista reabre.
 */
import { useCallback, useEffect, useState } from 'react'

import Botao from '../componentes/Botao'
import CamposDoItem, {
  CampoNome,
  chaveDa,
  emBranco,
  type EstadoDaFilha,
  gravarEmSequencia,
  MENSAGEM_CAMPO_EM_BRANCO,
  MENSAGEM_FALTAM_CAMPOS,
  MENSAGEM_SEM_NOME,
  valorInicial,
} from '../componentes/CamposDoItem'
import Esqueleto from '../componentes/Esqueleto'
import Tela from '../componentes/Tela'
import TrilhaDaColeta from '../componentes/TrilhaDaColeta'
import { concluirItem, ErroHttp, nomearFicha, obterFormulario } from '../services/api'
import type { FormularioDoItem, Pergunta } from '../tipos'
import { avisoDeUmPorVez, type TitulosDoEscopo } from './TelaFichas'

interface TelaFormularioProps {
  casoId: string
  escopo: string
  itemId: string
  titulos: TitulosDoEscopo
  voltar?: () => void
  /** Item concluído: volta à lista do escopo (o do pai, na margem). */
  onConcluir: (escopoDaLista: string) => void
  /** `T-321`: concluído, abre o próximo item pendente do mesmo escopo. */
  onAbrirItem?: (itemId: string) => void
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
  onAbrirItem,
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

  /**
   * `T-320`/`T-321`: o servidor confirma que nada falta e nomeia o próximo
   * item pendente. Faltando algo (uma pergunta que a resposta abriu e ainda
   * não estava na tela), relê o item e destaca o que falta.
   */
  async function concluir(dados: FormularioDoItem) {
    try {
      const { proximo_item: proximo } = await concluirItem(casoId, escopo, itemId)
      if (proximo && onAbrirItem) onAbrirItem(proximo)
      else onConcluir(dados.escopo_pai ?? escopo)
    } catch (falha) {
      if (!(falha instanceof ErroHttp) || falha.status !== 400) throw falha
      const visiveis = new Set(dados.perguntas.map(chaveDa))
      const novo = await obterFormulario(casoId, escopo, itemId)
      mostrar(novo)
      setEstados(
        Object.fromEntries(
          falha.pendencias
            .filter((pendencia) => pendencia.ID)
            .map((pendencia) => [
              `${pendencia.ID}|${pendencia.item_id ?? ''}`,
              {
                valor: '',
                naoSei: false,
                aviso: null,
                erro: MENSAGEM_CAMPO_EM_BRANCO,
              },
            ]),
        ),
      )
      setAbriuMais(
        falha.pendencias.some((p) => p.ID && !visiveis.has(`${p.ID}|${p.item_id ?? ''}`)),
      )
      if (!falha.pendencias.every((p) => p.ID)) setErroNome(MENSAGEM_SEM_NOME)
      setErro(falha.detalhe)
    }
  }

  async function salvar() {
    if (!formulario) return
    setErro(null)
    setAbriuMais(false)
    // `T-320`: nada em branco. Destaca e não grava nada.
    const faltam = emBranco(formulario.perguntas, estadoDe)
    const semNome = formulario.pede_nome && !nome.trim()
    if (faltam.length || semNome) {
      setEstados((atual) => ({
        ...atual,
        ...Object.fromEntries(
          faltam.map((p) => [chaveDa(p), { ...estadoDe(p), erro: MENSAGEM_CAMPO_EM_BRANCO }]),
        ),
      }))
      setErroNome(semNome ? MENSAGEM_SEM_NOME : null)
      setErro(MENSAGEM_FALTAM_CAMPOS)
      return
    }
    setGravando(true)
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
      const gravacao = await gravarEmSequencia(casoId, formulario.perguntas, estadoDe)
      setEstados((atual) => ({ ...atual, ...gravacao.estados }))
      if (falhou || gravacao.falhou) return
      if (gravacao.avisou) {
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
        <CampoNome
          id={`nome-${itemId}`}
          valor={nome}
          erro={erroNome}
          onMudar={(novo) => {
            setComAviso(false)
            setNome(novo)
          }}
        />
      )}

      <CamposDoItem perguntas={formulario.perguntas} estadoDe={estadoDe} mudar={mudar} />

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
