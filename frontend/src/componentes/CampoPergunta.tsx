/**
 * O campo de UMA pergunta — os nove `TipoResposta` (`RF-50`, T-137).
 *
 * Um componente com um ramo por tipo, pelo mesmo motivo de
 * `report/templates/coleta/pergunta.html`: o enunciado, o "não sei" e o
 * aviso de materialidade são comuns aos nove; só o CAMPO muda.
 *
 * **Este componente nunca decide se a pergunta aparece.** Ele recebe uma
 * pergunta que o servidor já decidiu ser exibível (`RF-52`) — não existe
 * `condicao_exibicao` no tipo `Pergunta`, então nem há o que avaliar.
 *
 * Rótulo associado ao campo em todos os ramos: campos de valor único usam
 * `<label for>`, grupos usam `<fieldset>/<legend>` — semântica nativa, que
 * é o que dá WCAG 2.1 AA de graça.
 */
import { aplicarMascara, temMascara } from '../mascaras'
import type { Pergunta } from '../tipos'

interface CampoPerguntaProps {
  pergunta: Pergunta
  valor: string | string[]
  naoSei: boolean
  onValor: (valor: string | string[]) => void
  onNaoSei: (marcado: boolean) => void
}

function idDoCampo(pergunta: Pergunta): string {
  return `campo-${pergunta.ID}`
}

export default function CampoPergunta({
  pergunta,
  valor,
  naoSei,
  onValor,
  onNaoSei,
}: CampoPerguntaProps) {
  const id = idDoCampo(pergunta)
  const idAviso = pergunta.aviso ? `aviso-${pergunta.ID}` : undefined
  const texto = Array.isArray(valor) ? '' : valor
  const marcados = Array.isArray(valor) ? valor : []

  // `RF-48`/`AC-78`: com "não sei" marcado, o campo fica inerte. A máscara
  // não roda e nada digitado antes é submetido como se fosse valor.
  const inerte = naoSei

  function aoDigitar(bruto: string) {
    onValor(temMascara(pergunta.tipo) ? aplicarMascara(pergunta.tipo, bruto) : bruto)
  }

  function alternarMarcado(valorInterno: string) {
    const jaTem = marcados.includes(valorInterno)
    onValor(
      jaTem ? marcados.filter((v) => v !== valorInterno) : [...marcados, valorInterno],
    )
  }

  const grupo = pergunta.tipo === 'SELECAO_UNICA' || pergunta.tipo === 'SIM_NAO_TALVEZ'

  return (
    <div className="flex flex-col gap-3">
      {grupo ? (
        <fieldset className="flex flex-col gap-2 border-0 p-0" disabled={inerte}>
          <legend className="mb-2 font-serif text-[1.35rem] font-semibold">
            {pergunta.enunciado}
          </legend>
          {pergunta.opcoes.map((opcao) => {
            const marcado = texto === opcao.valor_interno
            return (
              <button
                key={opcao.valor_interno ?? opcao.rotulo}
                type="button"
                role="radio"
                aria-checked={marcado}
                aria-describedby={idAviso}
                className="opt"
                onClick={() => onValor(opcao.valor_interno ?? '')}
              >
                <span
                  aria-hidden="true"
                  className={`grid h-[26px] w-[26px] shrink-0 place-items-center rounded-full border-2 ${
                    marcado ? 'border-accent' : 'border-muted'
                  }`}
                >
                  {marcado && <span className="h-[14px] w-[14px] rounded-full bg-accent" />}
                </span>
                <span>{opcao.rotulo}</span>
              </button>
            )
          })}
        </fieldset>
      ) : pergunta.tipo === 'SELECAO_MULTIPLA' ? (
        <fieldset className="flex flex-col gap-2 border-0 p-0" disabled={inerte}>
          <legend className="mb-2 font-serif text-[1.35rem] font-semibold">
            {pergunta.enunciado}
          </legend>
          {pergunta.opcoes.map((opcao) => {
            const valorInterno = opcao.valor_interno ?? ''
            const marcado = marcados.includes(valorInterno)
            return (
              <label key={valorInterno || opcao.rotulo} className="opt">
                <input
                  type="checkbox"
                  className="h-[26px] w-[26px] accent-accent"
                  checked={marcado}
                  aria-describedby={idAviso}
                  onChange={() => alternarMarcado(valorInterno)}
                />
                <span>{opcao.rotulo}</span>
              </label>
            )
          })}
        </fieldset>
      ) : pergunta.tipo === 'ESCALA_0_10' ? (
        <fieldset className="flex flex-col gap-2 border-0 p-0" disabled={inerte}>
          <legend className="mb-2 font-serif text-[1.35rem] font-semibold">
            {pergunta.enunciado}
          </legend>
          <div className="grid grid-cols-6 gap-2">
            {Array.from({ length: 11 }, (_, n) => String(n)).map((n) => (
              <button
                key={n}
                type="button"
                role="radio"
                aria-checked={texto === n}
                aria-label={n}
                className="opt justify-center text-[1.2rem] font-bold"
                onClick={() => onValor(n)}
              >
                {n}
              </button>
            ))}
          </div>
        </fieldset>
      ) : (
        <div className="field flex flex-col gap-2">
          <label htmlFor={id} className="font-serif text-[1.35rem] font-semibold">
            {pergunta.enunciado}
          </label>

          {pergunta.tipo === 'MOEDA' ? (
            // O "R$" é prefixo VISUAL, fora do <input>: `_CARACTERES_ACEITOS`
            // recusa o caractere, e mandá-lo junto daria 400.
            <div className="money">
              <span aria-hidden="true">R$</span>
              <input
                id={id}
                inputMode="decimal"
                value={texto}
                disabled={inerte}
                aria-describedby={idAviso}
                onChange={(e) => aoDigitar(e.target.value)}
              />
            </div>
          ) : pergunta.tipo === 'TAXA' ? (
            // `AC-76`: o "%" também fica fora — o servidor recebe "4,5" e
            // divide por 100.
            <div className="flex items-center gap-2">
              <div className="money flex-1">
                <input
                  id={id}
                  inputMode="decimal"
                  value={texto}
                  disabled={inerte}
                  aria-describedby={idAviso}
                  onChange={(e) => aoDigitar(e.target.value)}
                />
              </div>
              <span className="text-muted" aria-hidden="true">
                %
              </span>
            </div>
          ) : (
            <input
              id={id}
              type={pergunta.tipo === 'DATA' ? 'date' : 'text'}
              inputMode={pergunta.tipo === 'NUMERO' ? 'numeric' : undefined}
              className="campo-texto"
              value={texto}
              disabled={inerte}
              aria-describedby={idAviso}
              onChange={(e) => aoDigitar(e.target.value)}
            />
          )}
        </div>
      )}

      {pergunta.admite_nao_sei && (
        <label className="flex min-h-toque items-center gap-3">
          <input
            type="checkbox"
            className="h-[26px] w-[26px] accent-accent"
            checked={naoSei}
            onChange={(e) => onNaoSei(e.target.checked)}
          />
          <span>Não sei</span>
        </label>
      )}

      {pergunta.aviso && (
        <p id={idAviso} role="status" className="aviso-atencao">
          {pergunta.aviso}
        </p>
      )}
    </div>
  )
}
