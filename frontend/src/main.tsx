import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App.tsx'
import LimiteDeErro from './componentes/LimiteDeErro'
import './index.css'

const raiz = document.getElementById('root')
if (!raiz) throw new Error('elemento #root ausente')

createRoot(raiz).render(
  <StrictMode>
    {/*
      `T-169` — o limite fica FORA do `App`, envolvendo-o: um erro lançado
      durante a renderização do próprio `App` (decisão de rota, leitura da
      sessão) precisa ser pego também. Dentro dele, o limite desmontaria
      junto com o que falhou.
    */}
    <LimiteDeErro>
      <App />
    </LimiteDeErro>
  </StrictMode>,
)
