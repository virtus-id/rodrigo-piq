/**
 * Botão — as três variantes do protótipo validado (`RF-50`).
 *
 * Alvos de toque de 56px (primário/secundário) e 48px (discreto) vêm do
 * protótipo e são decisão de acessibilidade, não estética: a persona
 * responde no celular, com o contracheque ao lado.
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react'

export type VarianteBotao = 'primario' | 'secundario' | 'discreto'

interface BotaoProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: VarianteBotao
  children: ReactNode
}

const CLASSE_POR_VARIANTE: Record<VarianteBotao, string> = {
  primario: 'btn-primario',
  secundario: 'btn-secundario',
  discreto: 'btn-discreto',
}

export default function Botao({
  variante = 'primario',
  children,
  className = '',
  ...resto
}: BotaoProps) {
  return (
    <button className={`${CLASSE_POR_VARIANTE[variante]} ${className}`} {...resto}>
      {children}
    </button>
  )
}
