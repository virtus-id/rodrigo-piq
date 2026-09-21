# Plano Técnico — App do Aluno (coleta, plano e acompanhamento)

| Campo | Valor                                                            |
| ----- | ---------------------------------------------------------------- |
| Slug  | `app-aluno`                                                      |
| Spec  | [`specs/app-aluno.spec.md`](../specs/app-aluno.spec.md)          |
| Fonte | [`specs/piq-app-spec.md`](../specs/piq-app-spec.md) v1.0.1 — canônica |
| Fonte | [`plans/motor-calculo.plan.md`](motor-calculo.plan.md) — Lei nº 1 |
| Status| `rascunho`                                                       |
| Autor | virtushold@gmail.com                                             |
| Data  | 2026-09-03                                                       |

> **Precedência.** Canônica > spec do slug + contrato real de `engine/` > este
> plano. Este plano decide **como construir**, nunca **o que a regra diz**.
>
> **Três decisões de produto incorporadas aqui e ainda ausentes da spec:**
> `OQ-06` (piloto de 1 a 3 alunos, em série), `OQ-08` (aviso de "não sei" **na
> hora**) e `OQ-09` (entrega em **tela + PDF exportável**). Elas mudam o desenho
> e estão marcadas no texto. As demais abertas (`OQ-07`, `OQ-11`, `OQ-12`,
> `OQ-13`, `OQ-15`) **não** são decididas aqui: cada uma vira **ponto de
> variação** isolado, desenhado para que a resposta futura não force retrabalho
> estrutural.

---

## 1. Architecture Overview

Três camadas acima de duas que já existem e **não** são tocadas. A regra que
governa o desenho inteiro é a **Lei nº 1** herdada de
`plans/motor-calculo.plan.md` §1: *"`engine/` não conhece persistência nem
Supabase"*. Este plano acrescenta sua consequência simétrica, que é a
**Lei nº 3** deste slug:

> **Lei nº 3 — a aplicação não calcula.** Todo número, status ou prazo exibido
> ao aluno ou ao revisor é a **leitura de um campo de `SnapshotOrdem`**. A
> camada de aplicação monta a entrada, invoca `calcular_plano`, guarda o que ele
> devolveu e apresenta. Se uma tela precisa de um número que não é campo do
> snapshot, a resposta é Open Question ao especialista — nunca um cálculo novo.
> Verificável em `AC-41` e `AC-42`, e por teste estático de import (§9).

```text
┌─ NOVO (este slug) ──────────────────────────────────────────────────────────┐
│                                                                             │
│  navegador ──HTTP──► app/http/ (FastAPI)                                    │
│  (aluno /            │  autenticação por sessão · isolamento por CASO_ID    │
│   revisor)           │  RF-02 · AC-03                                       │
│                      ▼                                                      │
│   collection/  ◄──── app/casos/ (máquina de estados do caso — RF-01)        │
│   ├─ registros/  registros das 291 perguntas — DADO, não código (RF-03)     │
│   ├─ gerador     grafo condicional · REP · texto dinâmico (RF-04..RF-08)    │
│   └─ respostas   grava a cada resposta (RF-10 · AC-02)                      │
│                      │                                                      │
│                      ▼                                                      │
│              app/montagem/  ◄── FRONTEIRA DECIMAL ÚNICA (RF-13)             │
│              respostas ──► EstadoFinanceiro/Divida (RF-11, RF-12, RF-14)    │
│                      │      "não sei" ──► DESCONHECIDO, nunca 0             │
│                      ▼                                                      │
│              app/motor/executor.py — invoca em processo (§5)                │
│                      │                                                      │
│  report/  ◄──────────┴──► app/revisao/ (fila — RF-23..RF-26)                │
│  ├─ tela (principal)      libera UMA versão; o PDF deriva dela (OQ-09)      │
│  └─ pdf (sob demanda)                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
        │ import: só calcular_plano, tipos de E/S e portas (AC-41)
        ▼
┌─ CONGELADO ─────────────────┐   ┌─ EXISTENTE, consumido ───────────────────┐
│ engine/                     │◄──│ persistencia/supabase/                   │
│ calcular_plano(...) puro    │   │ FonteParametros · RepositorioSnapshots   │
│ 78/78 · 3 gabaritos · 5 inv.│   │ append-only: REVOKE + trigger            │
└─────────────────────────────┘   └──────────────────────────────────────────┘
```

**Direção de dependência, sem exceção.** `app/` e `collection/` importam de
`engine/` e de `persistencia/`. Nada em `engine/` ou `persistencia/` importa de
`app/`, `collection/` ou `report/`. `engine/` continua executável sem processo
externo — é isso que mantém os gabaritos reproduzíveis bit a bit.

**A unidade é o caso, não o formulário.** As 291 perguntas são cinco superfícies
em momentos distintos (§1 da spec). Um wizard linear não comporta Bloco 7/8
dirigido pelo motor nem Bloco 11 longitudinal — por isso a máquina de estados
(§7) é estrutura de primeira classe, não adendo.

---

## 2. Tech Stack

**Critério eliminatório herdado.** O motor é Python 3.12+ e recusa `float` em
construção (`engine/estado.py::_recusar_float`). Qualquer stack que colocasse um
processo de outra linguagem entre o formulário e `calcular_plano` reintroduziria
uma serialização numérica na fronteira mais frágil do sistema (`RF-13`), onde a
canônica não pode ceder. Isso eliminou "front em outra linguagem falando com o
motor por HTTP/JSON" antes de qualquer consideração de conforto.

| Escolha | Uso | Justificativa (ancorada em `RF-NN`) |
| --- | --- | --- |
| **Python 3.12+** (o do projeto — `.python-version`, `pyproject.toml`) | linguagem da camada de aplicação e da coleta | `RF-13`, `RF-14`, `RF-34`. Manter a linguagem do motor é o que permite **invocar `calcular_plano` em processo**, passando objetos `Decimal` nativos: o valor monetário nunca é serializado entre a fronteira de conversão e o motor. Descartado **Node/TypeScript no back**: exigiria serviço HTTP para o motor e uma travessia JSON de todo `EstadoFinanceiro` — reintroduzindo em `RF-13` exatamente o risco que a spec §8 nomeia como alto. A decisão é *manter a stack existente*, e isso também se justifica. |
| **FastAPI + uvicorn** | camada HTTP: rotas do aluno, do revisor, sessão | `RF-02`, `RF-16`, `RF-23`. O plano do motor (§2) já registrou FastAPI como a fronteira prevista para este slug — adotá-la é continuidade, não dependência nova. Tipagem por anotação integra com `mypy --strict`, já no `build` do config §2. Descartado **Django**: ORM, admin e migrações próprias colidiriam com a persistência já existente (psycopg + SQL versionado) e criariam segunda via de acesso ao banco. Descartado **Flask**: sem validação tipada de entrada, o que empurraria a conversão de `RF-13` para código manual em cada rota. |
| **Jinja2 + HTML server-side, progressive enhancement** | renderização da coleta e do plano | `RF-03`, NFR de acessibilidade e responsividade. A coleta é **gerada a partir de registros**: o servidor já tem o registro da pergunta em Python, e renderizá-lo direto elimina uma duplicação do modelo de pergunta em JS. Formulário HTML nativo dá WCAG 2.1 AA e navegação por teclado por padrão, e funciona a 360 px. Descartado **SPA (React/Vue)**: duplicaria o grafo condicional (`RF-05`) no cliente — dois lugares onde a regra de exibição pode divergir —, e o volume do piloto (`OQ-06`: 1 a 3 alunos) não paga esse custo. **Revisto em 2026-09-14 — ver a nota abaixo:** a recusa vale para o SPA que **avalia condicional no cliente**, não para o desenho de `RF-45`. |
| **HTMX** (~14 KB, sem build) | avaliação incremental sem recarregar página | `RF-10`, `OQ-08`. Salvar a cada resposta (`AC-02`) e avisar **na hora** sobre "não sei" (`OQ-08`) exigem uma requisição por resposta. HTMX faz isso com atributo no HTML gerado, mantendo **o servidor como única autoridade** sobre condicional e materialidade. Descartado **JS manual**: reintroduziria lógica de exibição no cliente. Descartado **recarga de página inteira**: violaria o p95 < 500 ms por transição. |
| **`decimal` (stdlib) via `engine/precisao.dinheiro()`** | fronteira de conversão formulário → motor | `RF-13`, `AC-09`, `AC-10`. A função de recusa de `float` **já existe e é testada** no motor; a fronteira desta feature a reusa em vez de escrever uma segunda. Zero dependência nova. Descartado qualquer parser monetário de terceiro: introduziria `float` no caminho (`EC-01`). |
| **Postgres/Supabase via psycopg 3** — schema **`app_aluno`** | respostas, contas, estado do caso, fila de revisão, consentimento | `RF-10`, `RF-19`, `RF-23`, `RF-30`, NFR de segurança. Reusa `persistencia/supabase/conexao.py`. `numeric` ↔ `Decimal` nativo em psycopg mantém `RF-13` de ponta a ponta. **Schema dedicado `app_aluno`**, separado de `motor_calculo`, exatamente como a NFR de segurança manda: os snapshots continuam sendo escritos **só** por `RepositorioSnapshots`, e nenhuma tabela desta feature duplica `motor_calculo.snapshots`. Descartado **SQLite local**: perderia o `REVOKE`+trigger de `V-01` e exigiria migração depois. |
| **Argon2id** (`argon2-cffi`) | hash de senha | `RF-02`, NFR de segurança ("senha nunca armazenada em texto claro"). Vencedor do Password Hashing Competition e recomendação OWASP corrente. Dependência nova, uma linha de justificativa: escrever hash de senha à mão é o erro clássico desta camada. Descartado **bcrypt** (limite de 72 bytes, sem resistência a GPU comparável) e **Supabase Auth** (ver §6: acoplaria autenticação ao fornecedor e a `RF-02` exige apenas login/senha próprio). |
| **`itsdangerous`** (via `SessionMiddleware` do Starlette) | sessão assinada em cookie | `RF-02`, `AC-03`. Cookie assinado, `HttpOnly`+`Secure`+`SameSite=Lax`. A 1–3 alunos em série (`OQ-06`), sessão em cookie assinado dispensa Redis. Isolamento é verificado **no servidor a cada requisição** (§5), nunca no cookie. |
| **WeasyPrint** | PDF exportável sob demanda | `RF-20`, `RF-21`, `OQ-09`. Renderiza o **mesmo HTML/CSS da tela** — a redação canônica de `Q-03` e o carimbo `V-03` existem em **um só template**, então `AC-14`/`AC-16` valem para tela e PDF sem duplicar texto normativo. Descartado **ReportLab** (layout imperativo: segunda redação do texto canônico, risco direto a `AC-14`) e **wkhtmltopdf** (binário externo descontinuado). |
| **pytest + Hypothesis** | suíte | `sdd.config.md` §5. Já no projeto; nenhuma dependência nova. |
| **mypy (strict) + ruff** | verificação estática | `AC-41`. Já no `build`/`lint` do config §2. `mypy --strict` obriga tratar `DinheiroTalvez` — esquecer `DESCONHECIDO` na montagem **não compila** (`RF-12`). Ruff hospeda a proibição de import indevido de `engine/` (§9). |


> **Revisão de 2026-09-17 (`T-145`) — a interface não é mais server-side.**
> As duas linhas acima (`Jinja2 + HTML server-side` e `HTMX`) descrevem a
> escolha original e **não são mais o estado do código**. A interface é
> React + TypeScript consumindo API JSON; o backend serve JSON e o PDF, e
> nenhum template Jinja2 renderiza tela.
>
> **O que motivou a troca, e o que a justificativa original acertava.** A
> recusa de SPA dizia que ela "duplicaria o grafo condicional (`RF-05`) no
> cliente". Essa preocupação era correta e continua endereçada: `RF-52` faz
> o servidor entregar **uma pergunta já decidida por vez**, e
> `tests/app_aluno/estatica/test_sem_condicional_no_javascript.py` audita
> `frontend/src/` para garantir que `condicao_exibicao` nunca atravesse a
> fronteira. A regra de exibição segue existindo num lugar só.
>
> **O que se perdeu, sem maquiagem.** O progressive enhancement acabou:
> sem JavaScript a coleta não abre (`RF-49`/`EC-21`, revogados por
> `OQ-29`, respondida em 2026-09-17 — a coleta é preenchida
> majoritariamente no computador). E a acessibilidade que vinha de graça do
> formulário nativo passou a ser responsabilidade do componente React:
> rótulo associado, foco e contraste agora são verificados em
> `frontend/tests/e2e/` (navegador real) e pela auditoria de contraste
> sobre `frontend/tailwind.config.js`, não mais herdados do HTML.
>
> **HTMX saiu do projeto**; o arquivo estático foi removido junto com a
> montagem `/estaticos`.

**Dependências novas, total: 4** — `fastapi`, `uvicorn`, `jinja2` (transitiva de
FastAPI), `argon2-cffi`, `weasyprint`. HTMX é um arquivo estático servido, não
um pacote. Nenhuma delas entra em `engine/`; todas ficam num extra
`app` do `pyproject.toml`, para que a suíte do motor continue rodando sem elas.

> **Adendo de 2026-09-14 (T-129) — a quinta dependência.** `playwright`
> (com `pytest-playwright`) foi acrescentada **a pedido explícito do
> especialista**, para verificar em navegador real o que a suíte sem browser
> não alcançava: a execução de `app/http/estaticos/mascaras.js`. Fica num
> extra **próprio** (`browser`), nunca em `app` nem em `dev` — produção não a
> instala, e `pytest -q` continua verde numa máquina que nunca a viu (o
> marcador `navegador` é pulado sem ela).
>
> Duas consequências que valem registro, porque custaram trabalho e podem
> voltar a morder:
>
> 1. **O PLUGIN pytest do Playwright é desligado** (`addopts = "-p
>    no:playwright"`). Ele instala um wrapper global de `pytest_runtest_call`
>    que abre escopo de *soft assertion* em todo teste da suíte e quebrava 16
>    testes de `test_reabertura.py`/`integracao/test_bloco11.py` com *"nested
>    soft assertion scopes are not supported"*. Nenhum teste deste projeto usa
>    as fixtures do plugin. A biblioteca segue em uso pleno.
> 2. **`https_only=True` não foi afrouxado.** Como o cookie de sessão é
>    `Secure`, o navegador não o envia sobre `http://localhost`; a resposta foi
>    servir o teste por HTTPS com certificado efêmero (OpenSSL do sistema, sem
>    acrescentar `cryptography`/`trustme`), nunca enfraquecer o middleware para
>    o teste passar.

### Revisão de 2026-09-15 (Rodada 4) — a recusa de SPA é REVOGADA

**O especialista decidiu adotar React + TypeScript.** A recusa registrada na
tabela acima, e a delimitação de 2026-09-14 logo abaixo, ficam **superadas**
a partir desta data. Registro o que isso custa, porque a decisão merece ser
lida com o preço à vista — e porque a recusa original não estava errada; ela
foi sobreposta por uma decisão de produto, que é prerrogativa de quem decide
o produto.

**O que se perde, concretamente:**

1. **O caminho sem JavaScript** (`RF-49`, `EC-21`). Um `<form method="post">`
   nativo funciona com JS desabilitado, em rede ruim e em leitor de tela
   antigo. Uma SPA não. Isso é regressão de acessibilidade real para a
   persona (servidor público, celular, rede instável), não detalhe técnico —
   está aberto como `OQ-29`.
2. **A garantia estrutural de `RF-05`.** Antes, duplicar o grafo condicional
   no cliente era *impossível*: não havia cliente. Agora é apenas
   *proibido* — `RF-52` mais a auditoria de `AC-73` estendida a `.ts`/`.tsx`.
   Proibição é mais fraca que impossibilidade; é a diferença entre uma trava
   e uma regra.
3. **Zero dependência nova** deixa de valer. Entram Node, npm, Vite, React,
   TypeScript, Tailwind e Vitest — mais `node_modules`, ~53 MB.

**O que NÃO muda, e é inegociável:**

- **Lei nº 3.** Todo número exibido continua sendo leitura de campo de
  `SnapshotOrdem`. O cliente React monta tela; não calcula plano.
- **A fronteira `Decimal` única.** `app/montagem/conversao.py` continua sendo
  o único lugar que interpreta entrada monetária. O TypeScript formata para
  exibição e **nunca** decide se um valor é válido.
- **O isolamento por `CASO_ID`** continua verificado no servidor a cada
  requisição, nunca no cliente.

**Sobre as instruções em `.claude/instructions/`:** `tailwind.instructions.md`
e `testing.instructions.md` descrevem um aplicativo de **previsão do tempo**
(tema dark glassmorphism, `text-sun`, "hero grande para temperatura",
"buscar cidade → ver clima"). São de outro projeto e **não se aplicam** —
seguir seu tema contrariaria `RF-50`, que fixa o design do protótipo
validado, claro e de alto contraste, com Atkinson Hyperlegible escolhida
para baixa visão. `react.instructions.md` é genérico e **é seguido**:
componentes funcionais, tipagem explícita, um componente por arquivo,
extração acima de ~150 linhas.

### Revisão de 2026-09-14 — página única, e por que a recusa acima continua de pé

O protótipo `PIQ Meu Plano` foi validado com stakeholders e passa a ser o
template da coleta (`RF-45` a `RF-49`). Isso exige revisitar a recusa de SPA
registrada na tabela — **sem revogá-la**, porque o que ela protege continua
valendo.

A recusa tinha um motivo único e nomeado: *"duplicaria o grafo condicional
(`RF-05`) no cliente — dois lugares onde a regra de exibição pode divergir"*.
Esse motivo é sobre **avaliar `condicao_exibicao` em JavaScript**, não sobre
renderizar no cliente. O desenho de `RF-45` não faz isso:

> **O servidor entrega uma pergunta já decidida exibível por vez.** O cliente
> não recebe `condicao_exibicao`, não recebe o grafo, e não tem meio de
> percorrê-lo. Quando a condição de uma pergunta é falsa, quem avança até a
> próxima é o servidor (`EC-24`), reusando `montar_contexto_pergunta`, que já
> levanta `ErroPerguntaNaoExibivel` — a mesma função que o Jinja2 usa hoje.

Logo `RF-05` continua existindo em **um lugar só**, que é o que a recusa
original protegia. O que muda é apenas **quem monta o HTML** a partir de uma
decisão que o servidor já tomou. `AC-73` transforma isso em trava executável:
uma auditoria estática falha se qualquer `.js` contiver enunciado, rótulo de
opção ou avaliação de condicional — o espelho de `AC-37` do lado do cliente.

**A Lei nº 3 não é afetada.** Nenhum número exibido passa a ser calculado no
cliente: continuam sendo leitura de campo de `SnapshotOrdem`. A máscara de
entrada (`RF-47`) formata **entrada**, nunca resultado, e não decide valor —
`AC-77` fixa que entrada ambígua segue para o servidor e é recusada lá, com a
regra de parsing viva num lugar só (`app/montagem/conversao.py`).

**Duas restrições herdadas continuam obrigatórias**, e é o que impede esta
revisão de virar porta aberta:

1. **Progressive enhancement permanece** (`RF-49`, `EC-21`). O `<form
   method="post">` nativo continua gravando pela mesma rota. A variante de
   resposta para a página única é **aditiva**, nunca substitutiva — o caminho
   sem JavaScript é requisito de acessibilidade, não fallback cortesia.
2. **Zero dependência nova.** Sem framework de SPA, sem build, sem bundler,
   sem biblioteca de máscara: JavaScript baunilha servido de
   `app/http/estaticos/`, mesma disciplina do HTMX. O total de dependências
   desta feature continua **4**.

---

## 3. Project Structure

Respeita `sdd.config.md` §3 e o precedente de `plans/motor-calculo.plan.md` §3.
`collection/` e `report/` já estão previstos no config e hoje existem vazios.
**Uma divergência declarada:** `app/`.

| Caminho | Responsabilidade | Novo? |
| --- | --- | --- |
| `collection/registros/*.yaml` | Os registros das 291 perguntas — **dado, não código** (`RF-03`, `AC-36`, `AC-37`). Um arquivo por bloco. Versionado com `QUESTIONARIO_VERSION` | sim |
| `collection/registro.py` | `RegistroPergunta` e domínios (`Obrigatoriedade`, `TipoResposta`) — o **esquema** do registro, sem nenhum enunciado (`RF-03`) | sim |
| `collection/carga.py` | Lê e valida os YAML contra o esquema; recusa carga incompleta; verifica unicidade e não-reaproveitamento de `ID` (`AC-38`) | sim |
| `collection/condicoes.py` | Avaliador do **grafo condicional** — expressão declarativa do registro → booleano (`RF-05`, `AC-21`) | sim |
| `collection/repeticao.py` | Fichas repetíveis por `DIVIDA_ID`/`VINCULO_ID`/`MARGEM_ID`/item (`RF-04`, `AC-04`) | sim |
| `collection/interpolacao.py` | Texto dinâmico: `[Dxxx]`, valores já coletados (`RF-06`, `AC-05`) | sim |
| `collection/validacao.py` | Validação cruzada por item repetido (`RF-07`, `AC-06`, `EC-02`) | sim |
| `collection/opcoes_do_motor.py` | Opções produzidas em runtime: `B12.15`, `B12.16` (`RF-08`, `AC-20`) | sim |
| `collection/materialidade.py` | **`OQ-08`** — deriva materialidade do contrato de entrada; avisa na hora (`RF-11`) | sim |
| `app/http/` | Rotas, sessão, autenticação, isolamento por caso (`RF-02`, `AC-03`) | sim |
| `app/casos/maquina.py` | Máquina de estados do caso: estados, transições nomeadas, guardas (`RF-01`) | sim |
| `app/casos/progresso.py` | Trilha de progresso; abandono observável (`RF-31`, `AC-40`) | sim |
| `app/montagem/conversao.py` | **Fronteira `Decimal` única** — o único lugar que converte string de formulário em `Dinheiro`/`Taxa` (`RF-13`, `AC-09`, `AC-10`, `EC-01`) | sim |
| `app/montagem/estado.py` | Respostas → `EstadoFinanceiro`/`Divida`/`PerfilComportamental`/`SinaisComportamentais` (`RF-11`, `RF-12`, `RF-14`, `RF-15`) | sim |
| `app/motor/executor.py` | Invoca `calcular_plano` **em processo**; carrega parâmetros pela `FonteParametros`; persiste por `RepositorioSnapshots.anexar` (`RF-16`, `RF-19`, `RF-32`) | sim |
| `app/motor/acoes.py` | Lê `ORDEM_ACOES` e dirige Blocos 7/8/11 por `ACAO_ID`/`TIPO_ACAO` (`RF-17`, `RF-27`, `RF-33`) | sim |
| `app/eventos/mapeamento.py` | Resposta do Bloco 11 → membro de `EVENTO_RECALCULO` (`RF-28`, `RF-29`) | sim |
| `app/revisao/fila.py` | Fila única; `POLITICA_REVISAO_INTEGRAL_PILOTO`; liberação/reprovação (`RF-23`, `RF-24`, `RF-25`) | sim |
| `app/consentimento/` | Pontos de encaixe de `PEND-01` — textos são insumo externo (`RF-30`) | sim |
| `report/templates/` | Templates Jinja2 do plano; a redação canônica de `Q-03` vive **aqui**, uma vez (`RF-20`, `RF-21`, `RF-22`) | sim |
| `report/pdf.py` | Exporta o **mesmo** template para PDF sob demanda (`OQ-09`) | sim |
| `persistencia/supabase/migracoes/002_app_aluno.sql` | Schema `app_aluno`: respostas, contas, casos, fila, consentimento | sim |
| `persistencia/app_aluno/` | Adaptadores das tabelas **desta** feature. Não toca snapshots nem parâmetros | sim |
| `engine/`, `persistencia/supabase/{conexao,fonte_parametros,repositorio_snapshots}.py` | **Não modificados** (`AC-44`) | não |
| `tests/app_aluno/` | Suíte desta feature (§9) | sim |

**Justificativa de `app/`.** O config §3 prevê `collection/` (questionário) e
`report/` (relatório e fila). A camada de aplicação — sessão, autenticação,
máquina de estados, montagem do estado, invocação do motor — não é nenhuma das
duas: se entrasse em `collection/`, o Bloco 11 (que não é questionário inicial)
e a fila ficariam presos no módulo errado; se fosse duplicada nos dois, haveria
duas máquinas de estado. **Requer atualização da §3 do `sdd.config.md` via
`/sdd:config` antes da implementação** — mesmo procedimento que
`plans/motor-calculo.plan.md` §3 adotou para `persistencia/`.

---

## 4. Data Model

Contratos e assinaturas. Nomes idênticos aos da canônica, caractere por
caractere (`sdd.config.md` §7). Corpo de função é escopo de `/sdd:implement`.

### 4.1. O registro de pergunta — o núcleo do gerador (`RF-03`..`RF-08`)

Os cinco casos difíceis da §15.1 da canônica cabem no registro **sem atalho
codificado à mão**. Cada campo abaixo existe porque um caso difícil o exige.

```python
# collection/registro.py — RF-03 · AC-36, AC-37, AC-38
# NENHUM enunciado, opção ou condição das 291 perguntas aparece neste arquivo:
# ele define o ESQUEMA; o conteúdo vive em collection/registros/*.yaml.

class Obrigatoriedade(Enum):          # §11, coluna de obrigatoriedade
    OBR = "OBR"; COND = "COND"; OPT = "OPT"; REP = "REP"

class TipoResposta(Enum):             # §11, tipo de cada registro
    SELECAO_UNICA = "SELECAO_UNICA"; SELECAO_MULTIPLA = "SELECAO_MULTIPLA"
    NUMERO = "NUMERO"; MOEDA = "MOEDA"; TAXA = "TAXA"; DATA = "DATA"
    TEXTO_CURTO = "TEXTO_CURTO"; SIM_NAO_TALVEZ = "SIM_NAO_TALVEZ"
    ESCALA_0_10 = "ESCALA_0_10"

class EscopoRepeticao(Enum):          # RF-04 — 115 das 291 são REP
    NENHUM = "NENHUM"; DIVIDA_ID = "DIVIDA_ID"; VINCULO_ID = "VINCULO_ID"
    MARGEM_ID = "MARGEM_ID"; ITEM_DESPESA = "ITEM_DESPESA"; ACAO_ID = "ACAO_ID"

@dataclass(frozen=True, slots=True)
class OpcaoRegistro:
    """Uma opção. `rotulo` é a redação canônica ao usuário; `valor_interno`
    é a coluna "Valor interno / mapeamento" da §11 (ex.: B5.A02 →
    CONSIGNADO · PESSOAL · ...). Traduzir qualquer um dos dois é proibido."""
    rotulo: str
    valor_interno: str | None          # None = domínio é o próprio rótulo
    admite_nao_sei: bool = False       # RF-11: "não sei" é opção de 1ª classe

@dataclass(frozen=True, slots=True)
class RegistroPergunta:
    """RF-03 — uma pergunta da §11, como DADO. Editar o YAML e reiniciar
    troca o enunciado sem tocar em código (AC-36)."""
    ID: str                            # B5.A02 — estável, nunca reaproveitado (AC-38)
    bloco: int
    enunciado: str                     # pode conter marcadores de RF-06
    tipo: TipoResposta
    obrigatoriedade: frozenset[Obrigatoriedade]   # COND+REP coexistem (B5.A05A)
    escopo_repeticao: EscopoRepeticao             # RF-04
    opcoes: tuple[OpcaoRegistro, ...]
    VARIAVEL_GRAVADA: str | None       # "Variável gravada" da §11
    condicao_exibicao: "Condicao | None"          # RF-05
    interpolacoes: tuple["Marcador", ...]         # RF-06
    validacoes_cruzadas: tuple["ValidacaoCruzada", ...]   # RF-07
    origem_opcoes: "OrigemOpcoes"                 # RF-08
    admite_nao_sei: bool               # RF-11 · AC-11
    salto_consequencia: str | None     # "Salto / consequência" da §11
```

**Como cada caso difícil cabe — a prova exigida pela spec (§8, risco do
"renderizador quase gerado"):**

```python
# collection/condicoes.py — RF-05 · AC-21
# Condição é ÁRVORE DECLARATIVA no YAML, avaliada por um interpretador
# genérico. Não há `if pergunta.ID == "B12.08"` em lugar nenhum.

type Condicao = (
    CondicaoIgual | CondicaoContem | CondicaoExisteItem | CondicaoE | CondicaoOu | CondicaoNao
)

@dataclass(frozen=True, slots=True)
class CondicaoIgual:
    variavel: str                      # qualquer VARIAVEL_GRAVADA, de QUALQUER bloco
    valor: str
@dataclass(frozen=True, slots=True)
class CondicaoContem:                  # checklist múltipla (MECANISMO_DEFICIT)
    variavel: str
    valor: str
@dataclass(frozen=True, slots=True)
class CondicaoExisteItem:              # "existe dívida de cartão no B5"
    escopo: EscopoRepeticao
    variavel: str
    valor_em: frozenset[str]
@dataclass(frozen=True, slots=True)
class CondicaoOu:
    termos: tuple[Condicao, ...]

def avaliar(c: Condicao, respostas: "Respostas") -> bool: ...
    # RF-05: percorre a árvore. Como CondicaoIgual referencia a variável por
    # NOME (não por bloco), a condicional ENTRE blocos é o caso comum, não
    # uma exceção. B12.08 é literalmente um CondicaoOu de quatro termos no
    # YAML — nenhuma linha de código é específica dele (AC-21, AC-37).
```

```python
# collection/interpolacao.py — RF-06 · AC-05
@dataclass(frozen=True, slots=True)
class Marcador:
    """`[Dxxx]` em B11.Q01 → o DIVIDA_ID da ficha corrente.
    `PAGAMENTO_MENSAL_EFETIVO` em B11.Q06 → valor já coletado."""
    marcador: str                      # texto literal a substituir
    origem: Literal["ID_DO_ITEM", "VARIAVEL_COLETADA", "CAMPO_DO_SNAPSHOT"]
    referencia: str

def interpolar(enunciado: str, marcadores, ctx: "ContextoItem") -> str: ...
    # RF-34: origem CAMPO_DO_SNAPSHOT LÊ um campo de SnapshotOrdem — nunca
    # recalcula (AC-42). Valor monetário passa por quantizar_exibicao (G-01).
```

```python
# collection/validacao.py — RF-07 · AC-06 · EC-02
@dataclass(frozen=True, slots=True)
class ValidacaoCruzada:
    """VALOR_UTILIZADO_MARGEM <= VALOR_TOTAL_MARGEM, por MARGEM_ID.
    Declarada no YAML; o comparador é genérico."""
    variavel_esquerda: str
    operador: Literal["<=", ">=", "<", ">", "=="]
    variavel_direita: str
    escopo: EscopoRepeticao            # compara DENTRO do mesmo item
    mensagem: str                      # redação ao usuário, do registro

def validar_cruzada(v, item, respostas) -> "ResultadoValidacao": ...
    # EC-02: recusa e NENHUM dos dois campos é gravado com o par inconsistente.
    # A mensagem aponta os DOIS campos e é vinculada ao campo de origem (NFR
    # de acessibilidade: anunciada a leitor de tela).
```

```python
# collection/opcoes_do_motor.py — RF-08 · AC-20
@dataclass(frozen=True, slots=True)
class OrigemOpcoes:
    """RF-08 — de onde vêm as opções da pergunta."""
    fonte: Literal["REGISTRO", "SNAPSHOT"]
    campo_do_snapshot: str | None      # ex.: regras propostas para B12.16

def opcoes_efetivas(r: RegistroPergunta, s: SnapshotOrdem | None
                    ) -> tuple[OpcaoRegistro, ...]: ...
    # AC-20: fonte=SNAPSHOT ⇒ as opções são as que o motor produziu; nenhuma
    # opção fixa em código aparece fora dessa lista. B12.15 é uma pergunta
    # POR REGRA proposta — repetição com escopo dirigido pelo motor, mesmo
    # mecanismo de RF-04, sem código específico de B12.15.
```

> **Ponto de variação `OQ-12`.** `B12.15`/`B12.16` são **casos de prova** do
> gerador; sua coleta efetiva está fora de escopo (spec §9). O contrato acima
> existe para provar que cabem — não se implementa o Bloco 12 agora.

### 4.2. Respostas, "não sei" e materialidade

```python
# collection/respostas.py — RF-10, RF-11 · AC-02, AC-08
class NaoSei(Enum):
    """RF-11 — "não sei" é resposta de PRIMEIRA CLASSE, distinguível de
    "não respondido" (ausência da linha) e de qualquer valor. Espelha
    `engine.tipos.Desconhecido` sem importá-lo para dentro do registro:
    a tradução para DESCONHECIDO acontece só em app/montagem/ (RF-12)."""
    NAO_SEI = "NAO_SEI"

NAO_SEI: Final = NaoSei.NAO_SEI

type ValorResposta = str | int | Decimal | date | frozenset[str] | NaoSei
# NUNCA float. NUNCA None para "não sei" — None significaria "não perguntado".

@dataclass(frozen=True, slots=True)
class Resposta:
    CASO_ID: str
    ID_PERGUNTA: str
    item_id: str | None                # DIVIDA_ID/MARGEM_ID/... quando REP
    valor: ValorResposta
    QUESTIONARIO_VERSION: str
    respondida_em: datetime            # auditoria, não entrada do motor
```

```python
# collection/materialidade.py — OQ-08 (decidida: aviso NA HORA) · RF-11
# ---------------------------------------------------------------------------
# O PONTO MAIS DELICADO DO PLANO. Avisar na hora exige saber, DURANTE o
# preenchimento, se um "não sei" é material — antes de o motor rodar. A
# aplicação NÃO PODE reimplementar a lógica de INFORMACAO_PENDENTE (RF-34).
#
# Caminho limpo adotado: derivar materialidade do PRÓPRIO CONTRATO DE ENTRADA,
# não da regra do motor. O critério é ESTRUTURAL e verificável por introspecção
# de `engine.estado`:
#
#   um campo é MATERIAL  <=>  ele é anotado `DinheiroTalvez`/`TaxaTalvez`/
#                             `int | Desconhecido` em `Divida`/`EstadoFinanceiro`
#
# Ou seja: material é exatamente o campo que o motor **admite** receber como
# DESCONHECIDO — e que por isso pode propagar INFORMACAO_PENDENTE. Um campo
# tipado `Dinheiro` puro nem sequer aceita "não sei"; um campo que não vai ao
# motor não afeta o plano. A derivação é por `typing.get_type_hints` sobre as
# dataclasses congeladas, executada uma vez na carga.
#
# O QUE ISSO NÃO É, e a honestidade importa: NÃO é uma previsão do que o motor
# fará. O aviso diz "esta informação pode deixar seu plano provisório", e nunca
# "seu plano SERÁ provisório" — porque decidir isso é do motor (Gate 1,
# fallback de taxa da §11.1, ORDEM_STATUS). A aplicação sinaliza uma
# POSSIBILIDADE derivada do contrato; o motor decide o fato. Ver §10.
# ---------------------------------------------------------------------------

def campos_materiais() -> frozenset[str]: ...
    # Introspecção de engine.estado — ZERO regra de negócio transcrita.

@dataclass(frozen=True, slots=True)
class AvisoMaterialidade:
    VARIAVEL_GRAVADA: str
    texto: str                         # redação: insumo do registro, não do dev

def avaliar_ao_responder(r: Resposta, reg: RegistroPergunta
                         ) -> AvisoMaterialidade | None: ...
```

### 4.3. Caso, contas, revisão

```python
# app/casos/maquina.py — RF-01
class ESTADO_CASO(Enum):
    CADASTRADO = "CADASTRADO"                     # antes do consentimento
    CONSENTIMENTO_REGISTRADO = "CONSENTIMENTO_REGISTRADO"   # RF-30 · AC-39
    COLETA_INICIAL = "COLETA_INICIAL"             # Blocos 1–5
    CALCULANDO = "CALCULANDO"                     # Bloco 6 · RF-16
    ERRO_DE_CALCULO = "ERRO_DE_CALCULO"           # EC-03, EC-04 — visível ao operador
    AGUARDANDO_REVISAO = "AGUARDANDO_REVISAO"     # RF-23 · AC-25
    REPROVADO_EM_REVISAO = "REPROVADO_EM_REVISAO" # EC-12
    PLANO_LIBERADO = "PLANO_LIBERADO"             # tela + PDF (OQ-09)
    COLETA_DIRIGIDA = "COLETA_DIRIGIDA"           # Blocos 7/8 · RF-17 · AC-19
    CONFIRMACAO_ATAQUE = "CONFIRMACAO_ATAQUE"     # Bloco 10 · RF-18
    ACOMPANHAMENTO = "ACOMPANHAMENTO"             # Bloco 11 · RF-27
    ENCERRADO = "ENCERRADO"

@dataclass(frozen=True, slots=True)
class Caso:
    CASO_ID: str                       # identidade PRÓPRIA — ver OQ-11 abaixo
    conta_id: str
    estado: ESTADO_CASO
    DATA_REFERENCIA: date              # RF-14 · AC-18 — entrada explícita, nunca relógio
    QUESTIONARIO_VERSION: str
    snapshot_corrente_id: str | None   # último snapshot LIBERADO (OQ-09)
    ultima_interacao_em: datetime      # RF-31 · AC-40 · EC-14

@dataclass(frozen=True, slots=True)
class Transicao:
    de: ESTADO_CASO
    para: ESTADO_CASO
    gatilho: str                       # nomeada, nunca implícita
    guarda: str | None
```

> **Ponto de variação `OQ-11` (`CASO_ID`).** `RepositorioSnapshots.historico`
> usa o `SNAPSHOT_ID` da **raiz da cadeia** como identificador do caso, e o
> aluno existe semanas antes do primeiro snapshot. Desenho adotado: `CASO_ID` é
> identidade própria de `app_aluno`, gerada no cadastro; a tabela `casos` guarda
> `snapshot_raiz_id`, preenchido quando o primeiro snapshot nasce. As duas
> identidades coexistem, com o mapeamento em **um único lugar**. Nenhuma
> assinatura de `engine/` muda. Se `OQ-11` for respondida com "`CASO_ID` vira
> campo do motor", muda-se o preenchimento de uma coluna — não a estrutura.

```python
# app/revisao/fila.py — RF-23, RF-24, RF-25 · AC-25..AC-29
POLITICA_REVISAO_INTEGRAL_PILOTO: Final[bool] = True
# RF-25 — POLÍTICA DE PROCESSO, distinta do campo do motor. Todo snapshot
# entra na fila mesmo com REVISAO_HUMANA_OBRIGATORIA=False (AC-25). O campo
# do motor (S-04) é MOTIVO ADICIONAL sinalizado ao revisor (AC-28), nunca a
# condição de entrada. Os dois nunca são lidos pela mesma expressão.

class DECISAO_REVISAO(Enum):
    LIBERADO = "LIBERADO"; REPROVADO = "REPROVADO"

class CLASSIFICACAO_ERRO(Enum):
    """§25 da canônica — RF-26. ⚠ OQ-12 ABERTA: o texto normativo da §25 não
    consta de piq-app-spec.md. Os seis rótulos vêm da §15.3; a DEFINIÇÃO de
    cada um não existe para transcrever. Modelado como enum de seis membros,
    SEM glosa inventada — a tela exibe o rótulo e um campo livre até OQ-12
    ser respondida. Ver §10."""
    TEXTO = "TEXTO"; PARAMETRO = "PARAMETRO"; DADO = "DADO"
    REGRA = "REGRA"; CALCULO = "CALCULO"; UX = "UX"

@dataclass(frozen=True, slots=True)
class RegistroRevisao:
    """RF-24 · AC-27 — imutável: sem UPDATE/DELETE por nenhuma rota,
    mesmo padrão estrutural de RepositorioSnapshots."""
    SNAPSHOT_ID: str
    CASO_ID: str
    decisao: DECISAO_REVISAO
    autor: str
    decidido_em: datetime
    classificacao_erro: CLASSIFICACAO_ERRO | None
    observacao: str
```

### 4.4. Ações — a dependência de `RF-33`

```python
# app/motor/acoes.py — RF-17, RF-27, RF-33 · AC-45..AC-50
# DEPENDÊNCIA DECLARADA, NÃO IMPLEMENTADA AQUI. As três mudanças em
# engine/gates.py::AcaoRequerida (ACAO_ID, TIPO_ACAO; Gate 1 emitindo ação;
# economia fora do fluxo de gates) são trabalho do slug `motor-calculo`.
# Esta feature CONSOME o resultado.

def acoes_em_acompanhamento(s: SnapshotOrdem) -> tuple[AcaoRequerida, ...]: ...
    # RF-33: LÊ s.ORDEM_ACOES. Não deriva tipo, não infere identidade,
    # não faz parsing da `descricao` em prosa (AC-41).

def perguntas_do_bloco_11(a: AcaoRequerida) -> tuple[str, ...]: ...
    # AC-46: ramifica por TIPO_ACAO — B11.03-INF/-REN/-TRO/-ECO, uma só.
    # ⚠ OQ-13 ABERTA: o identificador exato de TIPO_ACAO não tem linha no
    # dicionário da canônica. O mapeamento TIPO_ACAO → pergunta vive num
    # REGISTRO (collection/registros/), não em código — quando OQ-13 for
    # respondida, edita-se o registro. Nenhum literal de TIPO_ACAO é escrito
    # nesta feature; o domínio é o que `engine/` publicar.
    # ⚠ OQ-15 ABERTA: ação sem dívida (economia). AC-50 exige que B11.01 e
    # B11.03-ECO funcionem sem DIVIDA_ID — por isso a chave de vínculo da
    # resposta é ACAO_ID, NUNCA DIVIDA_ID. Isso já satisfaz AC-50 qualquer
    # que seja a resposta de OQ-15.
```

### 4.5. Persistência desta feature — schema `app_aluno`

```sql
-- persistencia/supabase/migracoes/002_app_aluno.sql
-- Schema SEPARADO de motor_calculo (NFR de segurança). NENHUMA tabela de
-- snapshot aqui: RF-19/AC-43 — snapshot só entra por RepositorioSnapshots.anexar.
CREATE SCHEMA IF NOT EXISTS app_aluno;

-- contas          (RF-02): senha_hash argon2id — nunca texto claro
-- casos           (RF-01, OQ-11): CASO_ID, estado, DATA_REFERENCIA,
--                 snapshot_raiz_id, snapshot_liberado_id, ultima_interacao_em
-- respostas       (RF-10, RF-11): PK (CASO_ID, ID_PERGUNTA, item_id);
--                 valor_texto/valor_numerico numeric/valor_nao_sei boolean —
--                 numeric, NUNCA double precision (RF-13)
-- itens_repetidos (RF-04): DIVIDA_ID/MARGEM_ID/VINCULO_ID estáveis por caso
-- revisoes        (RF-24): append-only — REVOKE UPDATE, DELETE + trigger,
--                 mesmo padrão de motor_calculo.snapshots (AC-27)
-- consentimentos  (RF-30): versão do texto, aceite, data (AC-39)
-- eventos_caso    (RF-31): trilha de progresso e transições (AC-40)
```

---

## 5. Data Flow

### 5.1. Uma resposta (`RF-10`, `RF-11`, `RF-13`, `AC-02`)

```text
campo HTML (string) ──► app/http/ rota de resposta
   │ 1. isolamento: a sessão possui este CASO_ID? não ⇒ 404 (AC-03)
   │ 2. registro carregado por ID; a pergunta está de fato aberta? (RF-05)
   │ 3. "não sei" marcado ⇒ grava NAO_SEI e PULA a conversão (RF-11)
   ▼
app/montagem/conversao.py ── FRONTEIRA DECIMAL ÚNICA (RF-13)
   │ "1234,56" → normaliza separadores → Decimal("1234.56") via
   │ engine.precisao.dinheiro() — str direto para Decimal, jamais float
   │ falha ⇒ EC-01: recusa, não avança, nada é gravado, nunca coage a 0
   ▼
collection/validacao.py ── validação cruzada por item (RF-07)
   │ falha ⇒ EC-02: recusa apontando os DOIS campos; nenhum é gravado
   ▼
persistencia/app_aluno ── INSERT/UPDATE da resposta, transação confirmada
   │ falha ⇒ EC-05: NÃO reporta como salva; o aluno vê e repete
   ▼
collection/materialidade.py ── OQ-08: aviso NA HORA, se material
   ▼
resposta HTTP: próximo campo + aviso. Só então a próxima pergunta aparece (AC-02).
```

**A fronteira `Decimal` vive em um só lugar:** `app/montagem/conversao.py`. É o
único módulo desta feature autorizado a construir `Dinheiro`/`Taxa`, e o teste
estático de §9 falha se qualquer outro arquivo chamar `Decimal(...)` sobre
entrada de usuário. `_recusar_float` do motor é a **última** linha de defesa,
não a primeira.

### 5.2. Bloco 6 — o cálculo (`RF-14`, `RF-16`, `RF-19`, `RF-32`)

```text
Etapa B completa ──► CALCULANDO
   │ 1. FonteParametros.carregar(versao)  ← RF-32, a JÁ EXISTENTE
   │    falha ⇒ EC-04: não tenta calcular, estado anterior preservado,
   │    ErroParametros reportado ao operador. Nunca parâmetro default.
   │ 2. app/montagem/estado.py: respostas → EstadoFinanceiro
   │    • NAO_SEI ──► DESCONHECIDO, nunca 0/None/média (RF-12 · AC-08)
   │    • B5.FIM02 ≠ SIM ──► INVENTARIO_COMPLETO=False (RF-15 · AC-07)
   │    • DATA_REFERENCIA vem do Caso, nunca de date.today() (AC-18)
   │    • 8 vars de PerfilComportamental + 10 de SinaisComportamentais
   │      + AUTOPERCEPCAO_CONTROLE (AC-13)
   │ 3. calcular_plano(estado, parametros, anterior, evento, motivo)
   │    EM PROCESSO — uma única vez (AC-12)
   │    ErroInvariante ⇒ EC-03: ERRO_DE_CALCULO, hash_inputs registrado,
   │    NENHUM plano parcial ao aluno. Bug, não situação de negócio.
   │ 4. RepositorioSnapshots.anexar(snapshot)  ← RF-19 · AC-43
   │    ANTES de qualquer exibição (AC-12)
   ▼
AGUARDANDO_REVISAO — sempre, sem exceção (RF-23 · AC-25, AC-26)
```

**Decisão: o motor é invocado em processo, não por HTTP.** O plano do motor
deixou isso em aberto para este slug (*"em processo, ou via FastAPI — a definir
no slug"*). **Decidido: em processo**, por três razões ancoradas em requisito:

1. **`RF-13`/`AC-09`.** Em processo, o `EstadoFinanceiro` chega ao motor como
   objeto Python com `Decimal` nativo. Via HTTP, todo valor monetário
   atravessaria JSON — a serialização é exatamente onde `float` se infiltra, e
   `RF-13` não pode ceder aí.
2. **`RF-34`/`AC-41`.** Em processo, a fronteira é auditável por análise
   estática de imports: dá para **provar** que a aplicação só importa
   `calcular_plano`, os tipos de E/S e as portas. Um serviço HTTP tornaria a
   fronteira uma convenção de rede, não uma propriedade verificável.
3. **`OQ-06` (1 a 3 alunos, em série).** Um segundo processo, com seu deploy,
   sua saúde e seu timeout, é infraestrutura que ninguém pediu. A NFR (p95 < 10 s
   para 20 dívidas) é folgada para execução local.

**Custo assumido:** o cálculo ocupa um worker. Mitigação proporcional ao volume:
executar em `run_in_executor` para não bloquear o loop de eventos, com o caso em
`CALCULANDO` e progresso visível (NFR). Se o volume crescer, `calcular_plano`
continua sendo função pura — envolvê-la num serviço depois é aditivo, não
retrabalho estrutural.

### 5.3. Do snapshot à tela e ao PDF (`RF-20`..`RF-22`, `OQ-09`)

```text
snapshot LIBERADO ──► report/templates/ (Jinja2)
   │ • título "Sua ordem projetada de quitação" e o texto de Q-03,
   │   caractere por caractere, em UM template (AC-14)
   │ • "projetada" sempre; nunca "definitiva"/"final"/"fixa" (AC-15 · Q-02)
   │ • ENGINE_VERSION + PARAMETROS_VERSION em toda saída (AC-16 · V-03)
   │ • JUSTIFICATIVA_POSICAO por posição (AC-17 · Q-05)
   │ • todo valor: LEITURA de campo do snapshot + quantizar_exibicao (AC-42)
   ├──► TELA (principal): sempre o snapshot liberado mais recente
   └──► PDF sob demanda: MESMO template, mesmo snapshot (WeasyPrint)
```

**`OQ-09` decidida — um objeto revisado, duas apresentações.** A fila libera uma
**versão do snapshot**, não uma página nem um arquivo. Tela e PDF derivam da
mesma versão liberada e do mesmo template — não são dois objetos revisados
separadamente. O PDF carrega o mesmo carimbo `V-03` (`AC-16`), e regenerá-lo
mais tarde produz o mesmo documento, porque o snapshot é imutável.

### 5.4. Bloco 11 e recálculo (`RF-27`..`RF-29`, `RF-33`)

```text
ACOMPANHAMENTO ──► B11.01 por ACAO_ID (RF-33) ──► B11.03-* por TIPO_ACAO (AC-46)
   ├─ RESULTADO_ACAO_INFORMACAO = Sim ⇒ reabre EXCLUSIVAMENTE o campo faltante
   │                                     (ex.: B5.B03) — AC-33
   ├─ RESULTADO_ACAO_RENEGOCIACAO = Sim ⇒ reabre B7.05–B7.16 — AC-34
   ├─ RESULTADO_ACAO_TROCA = Sim ⇒ reabre B8.01–B8.15
   └─ B11.Q01 = Sim ⇒ STATUS_QUITACAO_REAL = QUITADA (RF-29 · AC-30)
              = "Acredito que sim, mas ainda preciso confirmar" ⇒ NADA (AC-31)

app/eventos/mapeamento.py — resposta → membro de EVENTO_RECALCULO (RF-28)
   • alteração cadastral/cosmética NÃO tem membro no enum: é INEXPRIMÍVEL
     por construção (R-04) — AC-35 é satisfeito pelo tipo, não por um `if`
   • virada de mês NÃO dispara nada
   ▼
recálculo ⇒ calcular_plano(..., anterior=snapshot_corrente, evento=...)
   ⇒ versao+1, snapshot_anterior_id encadeado (AC-30) ⇒ FILA de novo (AC-26)
   ⇒ EC-11: com evento, versiona mesmo se hash_inputs for idêntico (R-05)
```

---

## 6. External Interfaces

| Serviço | Endpoint / contrato | Auth | Limites | Falha → |
| --- | --- | --- | --- | --- |
| **`engine.motor.calcular_plano`** | `(estado, parametros, anterior=None, evento=None, motivo="") -> SnapshotOrdem`. Chamada **em processo** | — | Função pura, sem I/O | `ErroInvariante` propaga: `ERRO_DE_CALCULO`, nada ao aluno (`EC-03`) |
| **`FonteParametros.carregar(versao)`** | `engine/portas.py` — adaptador Supabase já existente | `DATABASE_URL` (env) | — | `ErroParametros`: não calcula, estado preservado (`EC-04`) |
| **`RepositorioSnapshots.anexar/obter/historico`** | `engine/portas.py` — adaptador Supabase já existente. **Único caminho de escrita de snapshot** (`AC-43`) | `DATABASE_URL` (env) | Sem verbo de mutação, por desenho | Falha de `anexar` ⇒ o caso **não** avança (`EC-06`) |
| **Supabase/Postgres — schema `app_aluno`** | Tabelas desta feature, via `persistencia/supabase/conexao.py` | `DATABASE_URL` (env), TLS | Free tier: **pausa após ~7 dias sem atividade** | `EC-05`: resposta não é dada como salva; o aluno vê e repete |
| **Navegador do aluno** | React + TypeScript (SPA) consumindo API JSON (`T-140`..`T-145`) | Cookie de sessão assinado, `HttpOnly`/`Secure`/`SameSite=Lax` | 360 px a desktop; WCAG 2.1 AA | **Exige JavaScript** — `RF-49`/`EC-21` revogados por `OQ-29` |

**Risco operacional do free tier, dimensionado para `OQ-06`.** Com 1 a 3 alunos
em série, semanas podem passar entre acessos — a pausa por inatividade é o modo
de falha **esperado**, não hipotético. Tratamento honesto e proporcional: (a)
*keep-alive* agendado durante a janela do piloto; (b) na indisponibilidade, o
aluno vê "o sistema está reconectando, sua última resposta foi salva" e pode
repetir, nunca uma resposta falsamente confirmada (`EC-05`); (c) avaliar o tier
pago antes de abrir o piloto. Não se planeja pool de conexões nem réplica: seria
escala que ninguém pediu.

**Concorrência, à altura de `OQ-06`.** Com alunos em série, o conflito real é o
mesmo aluno em duas abas (`EC-10`). Tratamento simples e honesto: a chave
primária de `respostas` é `(CASO_ID, ID_PERGUNTA, item_id)`, e a última gravação
confirmada vence — sem merge silencioso. Transições de estado do caso usam
`SELECT ... FOR UPDATE` na linha do caso, o que basta para impedir dois Bloco 6
simultâneos. Nada de fila distribuída ou lock externo.

---

## 7. State Management

Quatro lugares onde estado vive, com dono explícito. Nenhum deles duplica outro.

| Estado | Dono | Vida | Invalidação |
| --- | --- | --- | --- |
| Respostas da coleta | `app_aluno.respostas` (banco) | Permanente, por caso | Nunca apagadas; reabertura marca a pergunta como pendente **sem** apagar o valor anterior (`RF-27`) |
| Estado do caso | `app_aluno.casos.estado` | Permanente | Só por transição nomeada (`RF-01`) |
| Snapshots | `motor_calculo.snapshots` (**já existente**) | Permanente, append-only | **Nunca** — `V-01`, `REVOKE`+trigger (`AC-32`) |
| Sessão | Cookie assinado | Expira | Logout/expiração. **Nunca** contém dado financeiro nem autoriza acesso: o isolamento é reverificado no servidor a cada requisição (`AC-03`) |

### 7.1. Máquina de estados do caso (`RF-01`) — não é wizard linear

```text
                    CADASTRADO
                        │ registra consentimento (RF-30 · AC-39)
                        ▼
             CONSENTIMENTO_REGISTRADO
                        │ inicia coleta        ┌──────────────────────────┐
                        ▼                      │ guarda: nenhuma resposta │
                 COLETA_INICIAL ◄──────────────┤ é gravada antes daqui    │
                  (Blocos 1–5)                 └──────────────────────────┘
                        │ B5.FIM02 respondida + campos OBR completos
                        ▼
                    CALCULANDO ──── ErroInvariante/ErroParametros ──► ERRO_DE_CALCULO
                        │ snapshot anexado (AC-12)                        │ operador
                        ▼                                                 └──► volta
              AGUARDANDO_REVISAO ◄──────────────────────────────────┐        ao estado
                   │           │ reprova (EC-12)                    │        anterior
                   │           ▼                                    │        (EC-06)
                   │   REPROVADO_EM_REVISAO ──► tratamento operador  │
                   │ libera (RF-24)                                  │
                   ▼                                                 │
              PLANO_LIBERADO ──► tela + PDF (OQ-09)                  │
                   │                                                 │
     ┌─────────────┼──────────────────┬──────────────────┐           │
     │ ORDEM_ACOES │ ATAQUE_IMEDIATO  │ ação reportada   │           │
     │ tem ação    │ _RECOMENDADO > 0 │ (meses depois)   │           │
     ▼             ▼                  ▼                  │           │
COLETA_DIRIGIDA  CONFIRMACAO_ATAQUE  ACOMPANHAMENTO ─────┘           │
(Blocos 7/8       (Bloco 10          (Bloco 11)                      │
 SÓ p/ dívidas     só se > 0          │                              │
 sinalizadas       AC-22)             │ quitação confirmada (AC-30)  │
 AC-19)                               │ OU evento material (RF-28)   │
     │             │                  └──────────────────────────────┘
     └─────────────┴───────────────────► CALCULANDO (recálculo)
                                          ⇒ FILA de novo (AC-26)

Retorno a campo ISOLADO (B11.03-INF = Sim): reabre EXCLUSIVAMENTE o campo
faltante (AC-33) — o caso permanece em ACOMPANHAMENTO, NÃO volta a
COLETA_INICIAL. É reabertura de pergunta, não de bloco: o que muda é o
conjunto de perguntas pendentes, não o estado do caso.
```

**Por que reabertura não é estado.** Modelar "reabriu B5.B03" como estado do
caso multiplicaria estados por pergunta. A pendência vive na **pergunta**
(`respostas` + conjunto de reaberturas por `ACAO_ID`), e o estado do caso diz só
em que fase ele está. É isso que permite `AC-33` (um campo isolado) e `AC-34`
(uma faixa de perguntas) sem tocar na máquina.

**Contexto decimal.** A aplicação **não** abre `localcontext`: `calcular_plano`
já o faz internamente na sua fronteira. A aplicação só constrói `Decimal` via
`engine.precisao.dinheiro()`, que abre o contexto do motor por conta própria.

---

## 8. Error Handling Strategy

| Situação | Detecção | Resposta ao usuário | Recuperação |
| --- | --- | --- | --- |
| `loading` — salvando resposta | — | Indicador no campo; a pergunta seguinte só aparece após confirmação (`AC-02`) | — |
| `loading` — Bloco 6 | Estado `CALCULANDO` | Tela de progresso, nunca tela travada (NFR p95 < 10 s) | Se exceder, `EC-06`: ou há snapshot e avança, ou volta ao estado anterior |
| Entrada monetária inválida (`EC-01`) | `app/montagem/conversao.py` recusa | Mensagem no campo, vinculada e anunciada a leitor de tela | Aluno corrige; **nada** gravado, nunca coerção a `0` |
| Validação cruzada violada (`EC-02`) | `collection/validacao.py` | Mensagem apontando **os dois** campos | Nenhum dos dois gravado com o par inconsistente |
| Campo `OBR` em branco sem "não sei" (`AC-11`) | Gerador, pelo registro | A coleta não avança; pergunta permanece pendente | — |
| "não sei" em campo material (`OQ-08`) | `collection/materialidade.py` | **Na hora**: "esta informação **pode** deixar seu plano provisório" | Aluno pode responder depois; vira ação de informação (`RF-33`) |
| `ErroInvariante` do motor (`EC-03`) | Exceção propaga de `calcular_plano` | Nada ao aluno. Caso em `ERRO_DE_CALCULO` | Operador; `hash_inputs` registrado. **Nunca** plano parcial ou degradado |
| `ErroParametros` (`EC-04`) | `FonteParametros.carregar` | Nada ao aluno | Cálculo não é tentado; estado preservado. **Nunca** parâmetro default |
| Banco pausado/indisponível (`EC-05`) | Exceção de `conexao` | "Não foi possível salvar — tente novamente" | Repetir. **Nunca** reportar como persistido sem ter sido |
| Duas sessões do mesmo aluno (`EC-10`) | PK de `respostas` | Última gravação confirmada vence | Sem merge silencioso |
| `ORDEM_QUITACAO` vazia (`EC-07`) | `DIVIDA_ALVO_ATUAL is None` | `ORDEM_ACOES` em **primeiro plano**: o que resolver antes de existir ataque | Não se exibe ordem vazia sem explicação |
| Tudo "não sei" (`EC-08`) | `ORDEM_STATUS`/`STATUS_METODO` do snapshot | Plano sai `PROVISORIO` e **explicita** o que falta | Não recusa a coleta, não inventa valor |
| `MODO_ESTABILIZACAO` (`EC-09`) | Campo do `Diagnostico` | `RESULTADO_CAIXA_OBSERVADO` positivo **nunca** chamado de "sobra"; método/ordem/cronograma como fase 2 condicional | Redação do template, do registro |
| Revisor reprova (`EC-12`) | `DECISAO_REVISAO.REPROVADO` | Nada ao aluno | Registro com autor e data; snapshot **intacto**. Nunca se edita snapshot para "corrigir" |
| Exclusão de dados (`EC-13`) | Pedido do aluno | Procedimento de `PEND-01` | Enquanto `PEND-01` estiver aberta, a resposta é dele — não do desenvolvedor |
| Abandono por meses (`EC-14`) | `ultima_interacao_em` | Caso retomável com tudo preservado | Trilha o marca como parado, com data (`AC-40`) |

**Nenhum log contém valor monetário, saldo, renda ou identificador pessoal**
(NFR de observabilidade). O que se registra: `CASO_ID`, `SNAPSHOT_ID`,
`hash_inputs`, `ENGINE_VERSION`, `PARAMETROS_VERSION`, estado e transição.

---

## 9. Testing Strategy

Convenções do `sdd.config.md` §5: **todo teste rastreia para um `AC-NN`**;
comportamento observável, nunca implementação; tolerância **zero** para status,
gates, ordem e `PROVISORIO` vs `NAO_APLICAVEL`.

- **Unitários** (pytest, `tests/app_aluno/`):
  - **Fronteira `Decimal`** — `AC-09`, `AC-10`, `EC-01`: `"1234,56"` →
    exatamente `Decimal("1234.56")`; entradas inválidas recusadas sem coerção.
    Hypothesis para a propriedade universal *"nenhuma entrada aceita produz
    `float` em nenhum ponto"* (`derandomize=True`, como no slug do motor).
  - **Tradução do "não sei"** — `AC-08`: `NAO_SEI` → `DESCONHECIDO`, nunca `0`,
    `None` ou estimativa. Reprodução de `GAB-03` pela via da coleta.
  - **Montagem do estado** — `AC-13`, `AC-18`: todos os campos obrigatórios,
    as 8 de `PerfilComportamental`, as 10 de `SinaisComportamentais`,
    `AUTOPERCEPCAO_CONTROLE`; `DATA_REFERENCIA` de entrada explícita.
  - **`INVENTARIO_COMPLETO`** — `AC-07`: `B5.FIM02` ≠ `SIM` ⇒ `False`.
  - **Gerador** — `AC-04` (fichas independentes), `AC-05` (interpolação),
    `AC-06` (validação cruzada), `AC-11`, `AC-20`, `AC-21` (`B12.08` com as
    quatro origens, verdadeira e falsa), `AC-22`, `AC-23`, `AC-24`.
  - **Máquina de estados** — `RF-01`: toda transição nomeada; transição não
    declarada é recusada; `AC-33`/`AC-34` (reabertura isolada e por faixa).
  - **Eventos** — `AC-31` (`A_CONFIRMAR` não dispara), `AC-35` (cadastral não
    dispara — garantido pelo enum não ter membro para isso).
  - **Revisão** — `AC-25` (campo `False` entra na fila mesmo assim), `AC-28`
    (os dois mecanismos distinguíveis).

- **Integração** (as costuras que este slug cria):
  - **Coleta → motor**: caso completo de fixture → `EstadoFinanceiro` →
    `calcular_plano` → snapshot. `AC-12` (invocado **uma vez**, persistido
    antes de exibir), `AC-30` (`versao+1`, encadeamento), `EC-11`.
  - **Persistência desta feature** contra Postgres real: `AC-27` (registro de
    revisão imutável), `AC-32` (`UPDATE`/`DELETE` de snapshot recusado),
    `AC-43` (gravação só por `anexar`). Marcador `requer_banco`, pulado sem
    `DATABASE_URL` — a suíte principal roda com os adaptadores de arquivo já
    existentes em `persistencia/arquivo/`.
  - **Retomada** — `AC-01`: sessão encerrada, outro dispositivo, retoma na
    primeira pergunta não respondida; `AC-02` (persistida antes da próxima).

- **Estáticos** (`tests/app_aluno/estatica/`) — as travas da Lei nº 3:
  - `AC-41`: AST de `app/`, `collection/`, `report/` — os imports de `engine.*`
    são **apenas** `calcular_plano`, tipos de E/S e portas. Falha em qualquer
    outro.
  - `AC-37`: nenhum enunciado, opção ou condição das 291 perguntas em
    `.py`; nenhum literal `P_*`.
  - `AC-42`: nenhuma aritmética sobre campo de `SnapshotOrdem` fora de
    `quantizar_exibicao` — o número é lido, nunca recomputado.
  - `AC-44`: nenhum arquivo de `engine/` ou de `persistencia/supabase/`
    (exceto a migração nova) modificado — verificado por hash.
  - `RF-13`: `Decimal(...)` sobre entrada de usuário só em
    `app/montagem/conversao.py`.
  - `AC-38`: nenhum `ID` de pergunta reaproveitado entre versões do registro.

- **E2E** (o mínimo que prova o ciclo, não uma suíte de UI):
  - `US-01`+`US-04`: cadastro → consentimento → coleta multissessão → Bloco 6
    → fila → liberação → tela do plano. Verifica `AC-14`, `AC-15`, `AC-16`,
    `AC-17` no HTML renderizado, **caractere por caractere**.
  - `US-07`: `AC-26` (recálculo passa pela fila), `AC-29` (plano e
    `estado_inputs` na mesma sessão).
  - `AC-03`: caso A autenticado não alcança nada do caso B por **nenhuma** rota
    — teste que enumera as rotas, não uma amostra.
  - `AC-39`: sem consentimento, nenhuma resposta é gravada.

- **Fora de teste automatizado, e por quê:**
  - **`AC-45`, `AC-46`, `AC-47`, `AC-48`, `AC-49`** — dependem das três mudanças
    em `engine/` que o slug `motor-calculo` ainda não entregou (`RF-33`). Os
    testes são **escritos agora e marcados `xfail(strict=True)`**, para virarem
    verde no dia da entrega e falharem ruidosamente se alguém os der por
    satisfeitos antes. `AC-50` **é** testável agora, porque depende só de a
    chave de vínculo ser `ACAO_ID` e não `DIVIDA_ID`.
  - **`EC-13`** (exclusão de dados) — o procedimento é `PEND-01`, texto externo
    ainda inexistente. Testar contra uma regra inventada seria pior que não
    testar. O ponto de encaixe é testado; a política, não.
  - **Conformidade WCAG 2.1 AA completa** — automação (`axe`) cobre contraste,
    rótulo e ordem de foco, e entra no E2E; navegação por teclado com leitor de
    tela real exige verificação manual, registrada como checklist.
  - **`OQ-12`/§25** — a tela de revisão exibe os seis rótulos, mas não se testa
    a **correção** de uma classificação cuja definição normativa não existe.
  - **Redação canônica além de `Q-02`/`Q-03`** — `AC-14`/`AC-15` testam o que é
    normativo e citável. O restante da redação ao aluno é da canônica, e
    auditar prosa por teste automatizado produziria falso verde.

---

## 10. Risks & Trade-offs

| Decisão | Alternativa descartada | Por quê | Risco assumido |
| --- | --- | --- | --- |
| **Motor em processo** | Serviço HTTP (FastAPI) na frente do motor | `RF-13`: em processo o `Decimal` nunca atravessa JSON. `AC-41`: a fronteira vira propriedade verificável por AST, não convenção de rede. `OQ-06` não pede um segundo processo | O cálculo ocupa um worker; um caso grande pode segurar uma requisição. Mitigado por executor e estado `CALCULANDO`. Envolver em serviço depois é aditivo — `calcular_plano` continua puro |
| **Materialidade derivada do contrato de entrada** (`OQ-08`) | (a) Reimplementar Gate 1 na aplicação; (b) avisar só no relatório | (a) violaria `RF-34` e a Lei nº 1 — a regra passaria a ter dois lugares onde morar; (b) contraria a decisão de `OQ-08` | **O aviso é aproximado, e isso é declarado ao aluno.** Diz "**pode** deixar provisório", nunca "vai". Um campo pode ser tipado `DinheiroTalvez` e ainda assim não tornar o plano provisório (fallback de taxa da §11.1). O inverso — campo material que não avisa — não ocorre, porque o conjunto derivado é um **superconjunto** do que o motor pode travar. Errar para o lado do aviso a mais é o lado seguro |
| **Coleta gerada por registros em YAML** | Registros em tabela do banco, editáveis por UI | YAML versionado no repositório dá revisão por diff e `QUESTIONARIO_VERSION` verificável; UI de edição é escopo que ninguém pediu no piloto | Editar o questionário exige acesso ao repositório e reinício (`AC-36` assume isso). `US-09` é atendida — é edição de registro, não de código |
| **HTML server-side + HTMX** | SPA (React/Vue) | `RF-05`: o grafo condicional existe **uma vez**, no servidor. Numa SPA existiria duas vezes | UX menos fluida que uma SPA. A 360 px com formulário nativo, é a troca certa para a persona |
| **Schema `app_aluno` separado** | Reusar `motor_calculo` | NFR de segurança; e mantém óbvio que esta feature não escreve snapshot (`AC-43`) | Duas migrações a coordenar. Baixo |
| **Revisão libera a versão do snapshot** (`OQ-09`) | Revisar tela e PDF separadamente | Um objeto revisado, duas apresentações do mesmo template: `AC-14`/`AC-16` valem para os dois sem duplicar texto normativo | Se um dia o PDF divergir da tela em conteúdo, a premissa cai. Mitigado por template único |
| **`CASO_ID` próprio, com `snapshot_raiz_id` mapeado** (`OQ-11`) | Usar a raiz da cadeia como identidade do caso | O aluno existe semanas antes do primeiro snapshot; a raiz não cobre esse período | Duas identidades coexistem. Mapeamento em um só lugar; se `OQ-11` mudar, muda-se uma coluna |
| **Aceitar Supabase free tier no piloto** | Tier pago desde já | `OQ-06`: 1–3 alunos em série não justificam custo antes de validar o método | **Pausa por inatividade é o modo de falha esperado**, não hipotético, justamente porque o uso é esporádico. Keep-alive + `EC-05` honesto + reavaliar o tier antes de abrir o piloto |
| **`REVISAO_HUMANA_OBRIGATORIA` e `POLITICA_REVISAO_INTEGRAL_PILOTO` como constantes distintas** | Um único booleano de "precisa revisar" | `RF-25`: fundir os dois faria o sistema revisar só uma fração dos casos, violando `PEND-06` sem ninguém perceber | Nenhum, se `AC-25`/`AC-28` existirem. É o risco alto da spec §8, neutralizado por teste |

### 10.1. Riscos herdados que este plano **não** resolve — e não deve

| Risco | Por que aparece aqui | Encaminhamento |
| --- | --- | --- |
| **`RF-33` depende de três mudanças em `engine/` do slug `motor-calculo`** | Sem elas, o Bloco 11 não é dirigido por ação e `US-08` não fecha — é dependência **no caminho crítico**, entre slugs | Declarada em `RF-33`, §4.4 e no sequenciamento. Testes de `AC-45`..`AC-49` escritos e `xfail(strict=True)` |
| **Gate 1 passando a emitir `AcaoRequerida` altera a saída de um gate já verificado** | `GAB-03` (`specs/motor-calculo.spec.md` **linha 156** — `AC-10`: rotativo com saldo e pagamento desconhecidos, dívida `INFORMACAO_PENDENTE`) e `EC-17` (**linha 240** — todas bloqueadas, `ORDEM_ACOES` primeiro) tocam **exatamente** dívidas travadas por informação. Uma `ORDEM_ACOES` que hoje vem vazia passará a vir preenchida | **Verificado nas duas linhas citadas.** É revisão de gabarito no slug `motor-calculo`, não efeito colateral: reexecutar `GAB-A`/`GAB-B`/`GAB-C` e os cinco invariantes, e atualizar as expectativas de `ORDEM_ACOES`. A tolerância **zero** para "gates" (config §5) significa que uma divergência aqui **não** é absorvível por arredondamento |
| **Ação de economia quebra o invariante "toda `AcaoRequerida` é sobre uma dívida"** | `DIVIDA_ID` deixa de estar sempre presente; todo consumidor atual de `ORDEM_ACOES` pode presumi-lo | Esta feature já vincula resposta por `ACAO_ID`, nunca por `DIVIDA_ID` (§4.4) — `AC-50` é satisfeito qualquer que seja a resposta de `OQ-15` |
| **`OQ-13` — identificador exato de `TIPO_ACAO`** | `sdd.config.md` §7 exige o nome da canônica caractere por caractere, e `TIPO_ACAO`/`ACAO_ID` **não têm linha no dicionário de variáveis**. Não há domínio publicado a transcrever | **Nenhum literal de `TIPO_ACAO` é escrito nesta feature.** O mapeamento tipo → pergunta vive em registro. Precisa ser respondida **antes** de a mudança em `engine/` ser escrita, ou o domínio seria inventado |
| **`OQ-12` — §25 ausente** | `RF-26` exige classificar em seis categorias cujo texto normativo não consta da canônica | Enum de seis rótulos **sem glosa inventada** + campo livre. Classificar errado é pior que não classificar |
| **`OQ-07` — painel do operador** | `RF-31` entrega a trilha como dado registrado e consultável | A trilha é gravada em `eventos_caso` desde já; se vira interface dedicada depende de `OQ-07`. Nenhum retrabalho estrutural nos dois caminhos |
| **`PEND-01` (LGPD)** | O sistema pode chegar pronto e impedido de ligar | Fora do caminho crítico técnico, dentro do caminho crítico do piloto. `RF-30` entrega os pontos de encaixe; o texto é insumo externo |
| **Abandono do aluno em 195 perguntas** | `OQ-02` fechou em coleta completa, o que **removeu** a mitigação por recorte mínimo | Resta a instrumentação: salvar a cada resposta (`AC-02`) e trilha que torna o abandono observável (`RF-31`, `AC-40`) |

---

## 11. Traceability

Todos os 34 requisitos da spec, cada um com a seção que o cobre.

| Requisito | Coberto por (seção do plano) |
| --- | --- |
| `RF-01` — caso com ciclo de vida explícito | §4.3 (`ESTADO_CASO`, `Caso`, `Transicao`) · §7.1 (máquina completa, com retorno a Blocos 7/8 e a campo isolado) |
| `RF-02` — login e senha, isolamento por caso | §2 (Argon2id, sessão assinada) · §3 (`app/http/`) · §4.5 (`contas`) · §5.1 (passo 1) · §7 |
| `RF-03` — coleta **gerada** a partir de registros | §3 (`collection/registros/`, `registro.py`, `carga.py`) · §4.1 (`RegistroPergunta`) · §9 (estático `AC-37`) |
| `RF-04` — ficha repetível | §4.1 (`EscopoRepeticao`, `collection/repeticao.py`) · §4.5 (`itens_repetidos`) |
| `RF-05` — condicional composta entre blocos | §4.1 (`Condicao` como árvore declarativa; `B12.08` é `CondicaoOu` no YAML) |
| `RF-06` — texto dinâmico | §4.1 (`Marcador`, `interpolar`) |
| `RF-07` — validação cruzada entre campos | §4.1 (`ValidacaoCruzada`, por `escopo`) · §5.1 · §8 (`EC-02`) |
| `RF-08` — opções produzidas pelo motor | §4.1 (`OrigemOpcoes`, `opcoes_efetivas`) |
| `RF-09` — Etapa B completa + Blocos 7, 8, 10, 11 | §4.1 (`Obrigatoriedade`) · §7.1 (fases da máquina) |
| `RF-10` — persistir a cada resposta, retomar | §4.2 (`Resposta`) · §4.5 (`respostas`) · §5.1 · §7 |
| `RF-11` — "não sei" de primeira classe | §4.2 (`NaoSei`, distinto de ausência) · §4.1 (`admite_nao_sei`) |
| `RF-12` — "não sei" → `DESCONHECIDO`, nunca inventar | §5.2 (passo 2) · §9 (`AC-08`, reprodução de `GAB-03`) |
| `RF-13` — fronteira `Decimal` única e testada | §2 (`engine.precisao.dinheiro`) · §3 (`app/montagem/conversao.py`) · §5.1 · §9 (estático + Hypothesis) |
| `RF-14` — montar `EstadoFinanceiro` completo | §4.3 (`DATA_REFERENCIA` no `Caso`) · §5.2 (passo 2) · §9 (`AC-13`, `AC-18`) |
| `RF-15` — `INVENTARIO_COMPLETO` de `B5.FIM02` | §5.2 (passo 2) · §9 (`AC-07`) |
| `RF-16` — executar o Bloco 6 sem reproduzir cálculo | §5.2 · §6 (contrato de `calcular_plano`) · §1 (Lei nº 3) |
| `RF-17` — Blocos 7/8 só para dívidas sinalizadas | §4.4 (`acoes_em_acompanhamento`) · §7.1 (`COLETA_DIRIGIDA`) |
| `RF-18` — Bloco 10 condicional e validado | §7.1 (`CONFIRMACAO_ATAQUE`) · §9 (`AC-22`, `AC-23`, `AC-24`) |
| `RF-19` — snapshot só por `RepositorioSnapshots.anexar` | §5.2 (passo 4) · §6 · §4.5 (nenhuma tabela de snapshot) · §9 (`AC-43`) |
| `RF-20` — `ENGINE_VERSION`/`PARAMETROS_VERSION` em toda saída | §5.3 (template único: tela **e** PDF) · §9 (`AC-16`) |
| `RF-21` — redação canônica, caractere por caractere | §3 (`report/templates/`) · §5.3 · §9 (E2E verifica no HTML) |
| `RF-22` — `JUSTIFICATIVA_POSICAO` por dívida | §5.3 · §9 (`AC-17`) |
| `RF-23` — fila de revisão para **todo** snapshot | §4.3 (`POLITICA_REVISAO_INTEGRAL_PILOTO`) · §5.2 · §7.1 (`AGUARDANDO_REVISAO`) |
| `RF-24` — revisão com autor e data, imutável | §4.3 (`RegistroRevisao`) · §4.5 (`revisoes` append-only) · §9 (`AC-27`) |
| `RF-25` — os dois mecanismos, nomeados e distintos | §4.3 · §10 (linha própria na tabela de trade-offs) · §9 (`AC-25`, `AC-28`) |
| `RF-26` — plano e `estado_inputs` lado a lado | §4.3 (`CLASSIFICACAO_ERRO`) · §10.1 (`OQ-12` aberta) · §9 (`AC-29`) |
| `RF-27` — Bloco 11 ao longo do tempo, reabertura dirigida | §4.4 · §5.4 · §7.1 (reabertura é da pergunta, não do estado) |
| `RF-28` — recálculo só por quitação ou evento material | §3 (`app/eventos/mapeamento.py`) · §5.4 (cadastral é inexprimível no enum) |
| `RF-29` — só `B11.Q01 = Sim` dispara | §5.4 · §9 (`AC-31`) |
| `RF-30` — consentimento, retenção, exclusão | §3 (`app/consentimento/`) · §4.5 (`consentimentos`) · §7.1 (guarda antes da coleta) · §10.1 (`PEND-01`) |
| `RF-31` — trilha de progresso, abandono observável | §3 (`app/casos/progresso.py`) · §4.3 (`ultima_interacao_em`) · §4.5 (`eventos_caso`) · §9 (`AC-40`) |
| `RF-32` — parâmetros pela `FonteParametros` existente | §5.2 (passo 1) · §6 · §9 (estático: nenhum `P_*` no código) |
| `RF-33` — `ORDEM_ACOES` com `ACAO_ID` e `TIPO_ACAO` | §4.4 (consumo; dependência declarada) · §5.4 · §10.1 (três riscos herdados) |
| `RF-34` — aplicação livre de regra de cálculo | §1 (**Lei nº 3**) · §4.2 (materialidade por contrato, não por regra) · §9 (estáticos `AC-41`, `AC-42`) |

> Requisito sem cobertura é buraco no plano. Item de plano sem requisito é
> over-engineering.

---

## 12. Adendo — divergências reais encontradas durante a implementação (`T-98`)

Registrado no fechamento do portão de qualidade (`T-98`, `sdd.config.md` §8:
"sem regressão nos artefatos SDD"). Nenhuma delas é decisão silenciosa: cada
uma já estava documentada na tarefa que a introduziu; este adendo só a torna
visível **no plano**, que não previa nenhuma das três.

| Divergência | O que o plano previa | O que foi construído | Origem |
| --- | --- | --- | --- |
| **`app/eventos/eventos.py`** e `persistencia/app_aluno/eventos.py::RepositorioEventosCaso` | §3/§4.5 previam a tabela `eventos_caso` e o dado que ela guarda, mas não nomeavam um repositório próprio nem um wrapper de transição — a trilha aparecia como consequência de `RF-31`, sem mecanismo de gravação especificado | Um repositório dedicado (`RepositorioEventosCaso`, com implementação Postgres e arquivo, mesmo padrão de `respostas.py`/`casos.py`/`itens.py`) e um wrapper único, `app/casos/progresso.py::transicionar_e_registrar(*, repositorio_casos, repositorio_eventos, caso_id, de, para, agora=None, detalhe=None)`, que valida a transição contra `app.casos.maquina.transicionar`, persiste por `transicionar_estado_se` (a variante condicional de `T-56`) e só então grava um `EventoCaso`. Os cinco pontos de transição de produção (`rotas_consentimento.py`, `rotas_calculo.py`, `app/revisao/fila.py`, `app/casos/acompanhamento.py`, `app/motor/executor.py`) foram migrados para chamar o wrapper em vez de duplicar a lógica em cada um | `T-91` (`RF-31`, `AC-40`, `EC-14`) |
| **Guarda de papel de revisor** (`e_revisor` em `app_aluno.contas`, migração `003_papel_revisor.sql`, `app/http/sessao.py::exigir_papel_revisor`) | Nenhuma seção do plano previa um segundo tipo de conta. §4.5 modela `contas` como uma única entidade (aluno); a fila de revisão (§7.1, `AGUARDANDO_REVISAO`) não tinha modelo de autorização — `T-69` (Entrega 8) documentou isso como limitação conhecida do piloto, deliberadamente sem autenticação própria, remetendo o fechamento a "controle de rede/infra, fora do escopo deste backlog" | Decisão do usuário (não do desenvolvedor, registrada em `T-100`): `/revisao/*` passou a exigir sessão autenticada **e** o campo `e_revisor = true` na conta, com `401`/`403` — nunca `404` — para quem não tem o papel. Não recria o sistema de papéis que `OQ-03` descartou (não há revisor A vs. revisor B com filas distintas): distingue apenas "é revisor" de "é aluno" | `T-100` (`RF-23`, `RF-25`) |
| **Correção de conversão dos nove `TipoResposta`** em `app/http/rotas_coleta.py` | §5.1 (passo "conversão decimal") e §3 (`app/montagem/conversao.py`) descreviam a fronteira `Decimal` única para `MOEDA`/`TAXA`, mas não detalhavam a conversão dos demais sete tipos de resposta na rota HTTP — implicitamente presumido correto | `T-95` descobriu que `SELECAO_MULTIPLA`, `NUMERO`, `DATA`, `ESCALA_0_10` caíam em `return valor_bruto` (string crua), tornando a resposta gravada estruturalmente incompatível com `app/montagem/estado.py` (que exige `frozenset[str]`/`int`/`date`). Corrigido em `T-101`: cada tipo agora converte para o tipo Python correto na rota, recusando entrada inválida pelo mesmo caminho de erro de `MOEDA`/`TAXA` (`EC-01`), nunca truncando nem coagindo | `T-101` (`RF-11`, `RF-13`, `AC-08`, `AC-13`) |

Nenhuma das três altera a Arquitetura (§1), a Lei nº 3, a fronteira com
`engine/`/`persistencia/` (§0 da spec, `AC-41`/`AC-44`) ou o modelo de dados
central (§4). São extensões aditivas dentro da fronteira já declarada, não
reinterpretação de requisito — por isso não geraram nova versão de spec, só
este registro.

**Nenhum `RF` ficou sem cobertura.** Dois com cobertura **parcial e declarada**,
por dependência externa a esta feature — não por omissão do plano:
`RF-33` (depende das três mudanças em `engine/` do slug `motor-calculo`) e
`RF-26` (depende de `OQ-12`, o texto da §25).

---

# Rodada 2 — Leitura de reserva e caixa do Bloco 4, fatia 2A (2026-09-07)

| Campo | Valor |
| ----- | ----- |
| Slug  | `app-aluno` |
| Spec  | [`specs/app-aluno.spec.md`](../specs/app-aluno.spec.md) — blocos "Rodada 2 (2026-09-07) — fatia 2A" (`RF-36`–`RF-44`, `AC-51`–`AC-71`, `US-13`–`US-16`, `EC-15`–`EC-20`, `OQ-20`–`OQ-25`) |
| Discovery | [`specs/app-aluno.discovery.md`](../specs/app-aluno.discovery.md) — "Discovery — Rodada 2" (§0–§8) |
| Fonte normativa | [`specs/motor-calculo.spec.md`](../specs/motor-calculo.spec.md) **§13.1** e **§13.3** — documento canônico PIQ v1.0.1, **congelado** |
| Status | `rascunho` |
| Autor | virtushold@gmail.com |
| Data | 2026-09-07 |

> **Escopo desta seção.** Cobre exclusivamente `RF-36` a `RF-44` — a **fatia
> 2A**: cinco campos escalares de reserva e caixa lidos de resposta real do
> Bloco 4, três coleções como tupla vazia declarada, allowlist `+2` nomes,
> hashes congelados regravados, fixtures/testes atualizados e o tratamento de
> exibição do valor desconhecido. As seções 1–11 (Rodada 1) e o adendo §12
> **não são alterados**: continuam a fonte de verdade de tudo que existia
> antes de 2026-09-07. Onde esta rodada estende uma decisão anterior, o texto
> aponta a seção original em vez de duplicá-la.
>
> **Fora de escopo, e por quê** (spec §9, bloco da Rodada 2): fatia **2C**
> (investimentos e ativos) — bloqueada por `motor-calculo:OQ-26` **e**
> `motor-calculo:OQ-27`, **ambas**: responder só uma não destrava, porque
> `CLASSIFICACAO_MOBILIZACAO` e `VALOR_LIQUIDO_REALIZAVEL*` são obrigatórios e
> sem default nas três dataclasses de item, por causas independentes. Fatia
> **2B** (recursos extraordinários) — depende de `OQ-22`(b) e `OQ-24`. A
> **correção de `valores_do_escopo`** — é `OQ-24`, pré-requisito de 2B/2C, não
> desta fatia. O **Bloco 10** (`T-77`/`T-78`/`T-79`) — depende de
> `motor-calculo:OQ-29`.
>
> **Precedência inalterada.** A §13 de `motor-calculo` é normativa e congelada.
> Este plano decide **como** ler a resposta e entregá-la ao motor — nunca **o
> que** a §13 diz, e nunca **como** o motor a aplica. Ler não é calcular
> (Lei nº 3, §1 acima).

## R2.1. Architecture Overview

**Nenhuma camada nova, nenhuma dependência nova, nenhum ponto de I/O novo.** A
rodada acrescenta **cinco funções privadas de leitura** a um módulo que já tem
27 delas, e **um campo de contexto de apresentação** a um módulo que já tem a
convenção de exibir desconhecido.

```text
 collection/registros/bloco-04.yaml  (DADO — não tocado nesta fatia)
   B4.01/B4.01A · B4.02/B4.02A · B4.03/B4.03A
            │
            ▼  RespostasCaso.valor(VARIAVEL_GRAVADA)   ← escalar, NUNCA
            │                                            valores_do_escopo (AC-71)
 ┌──────────┴──────────────────────────────────────────────────────────┐
 │ app/montagem/estado.py  — 5 leituras novas (RF-36, RF-37, RF-38)   │
 │   _reserva_existe                    → _membro_do_enum   (RF-36)   │
 │   _disposicao_uso_reserva            → _membro_do_enum   (RF-36)   │
 │   _reserva_total                     → _ou_desconhecido  (RF-37)   │
 │   _valor_maximo_reserva_informado_usuario → _ou_desconhecido(RF-37)│
 │   _dinheiro_disponivel               → _ZERO | erro nomeado (RF-38)│
 │                                                                     │
 │   investimentos=() · ativos=() · recursos_extraordinarios=()        │
 │                       ↑ tupla vazia DECLARADA, motivo em docstring  │
 │                         (RF-39, AC-62) — nenhuma derivação (RF-44)  │
 └──────────┬──────────────────────────────────────────────────────────┘
            │  EstadoFinanceiro COMPLETO (21 campos)
            ▼
 engine/motor.py::calcular_plano   ← CONGELADO, não tocado (AC-44)
   engine/diagnostico.py:788-815 → derivar_RESERVA_MOBILIZAVEL (§13.1)
   ↑ A DERIVAÇÃO JÁ EXISTE. Esta fatia muda a ENTRADA, não a derivação.
            │
            ▼  Diagnostico.RESERVA_MOBILIZAVEL: DinheiroTalvez
 ┌──────────┴──────────────────────────────────────────────────────────┐
 │ report/plano.py — ContextoReservaMobilizavel (RF-43, AC-70, EC-18)  │
 │   is DESCONHECIDO → estado "pendente de decisão"                    │
 │   Decimal        → valor formatado por _formatar_valor_de_apoio     │
 │   NUNCA R$ 0,00, NUNCA omissão, NUNCA exceção                       │
 └─────────────────────────────────────────────────────────────────────┘
```

**Quatro pontos de mudança de código, e só quatro:**

1. **`app/montagem/estado.py`** — cinco funções `_privadas` novas, as três
   tuplas vazias e a docstring que registra o motivo (`RF-36`–`RF-39`,
   `RF-44`).
2. **`tests/app_aluno/estatica/test_fronteira_import_engine.py`** — allowlist
   `+2` nomes, com comentário justificativo (`RF-40`).
3. **`tests/app_aluno/estatica/hashes_congelados.json`** — regravado a partir
   da saída do próprio teste (`RF-41`). É **registro, não código**.
4. **`report/plano.py`** + **`report/templates/plano/`** — o caminho de
   exibição do desconhecido (`RF-43`), reaproveitando a convenção já existente.

Mais as fixtures e dois testes que constroem `EstadoFinanceiro` à mão
(`RF-42`).

**Nenhuma lei de arquitetura é violada.** `app/` continua sem calcular
(Lei nº 3): as cinco leituras são resposta → conversão → tipo, e a Regra 2 da
§13.1 (`MIN`/`MAX`) **não é reproduzida em lugar nenhum de `app/`**. `engine/`
não é modificado (`AC-44`); a única mudança em arquivo compartilhado é o JSON
de hashes, que é o registro de "qual `engine/` este slug consome".

## R2.2. Tech Stack

**Nenhuma dependência nova. Contagem desta rodada: 0.** A decisão aqui é
**manter** a stack da Rodada 1 (§2 acima), e isso também se justifica requisito
a requisito. Verificado por leitura direta dos arquivos citados, não presumido.

| Escolha | Uso | Justificativa (ancorada em `RF-NN`) |
| --- | --- | --- |
| **Python 3.12+ / PEP 695** (o do projeto, já em uso) | as cinco funções de leitura, com o genérico `_membro_do_enum[TEnum: Enum]` já escrito nessa sintaxe (`app/montagem/estado.py:410`) | `RF-36`. Reusar a função genérica existente é o que permite resolver os dois enums **sem uma linha nova de tradução** — `AC-53` audita justamente a ausência de rótulo em português no arquivo. Alternativa descartada: uma função de tradução por pergunta, proibida por `AC-37` e desnecessária porque os `valor_interno` já batem com os `name` |
| **`enum.Enum` de `engine/estado.py`** (`RESERVA_EXISTE`, `DISPOSICAO_USO_RESERVA`), importados sob allowlist ampliada | tipar `EstadoFinanceiro.RESERVA_EXISTE`/`.DISPOSICAO_USO_RESERVA` (`engine/estado.py:511`, `:513`) | `RF-36`, `RF-40`, `AC-51`, `AC-52`, `AC-63`. Os enums só existem em `engine/estado.py` — não são redefinidos nem reexportados por `engine.tipos` (que já é liberado por inteiro). Alternativa descartada: **redeclarar os dois enums em `app/`** — criaria um segundo domínio fechado que pode divergir do do motor sem erro de tipo, exatamente o dicionário mental que `sdd.config.md` §7 proíbe |
| **`DinheiroTalvez = Dinheiro \| Desconhecido`** (`engine/tipos.py`, liberado por inteiro) via `_ou_desconhecido` (`:370`) | `RESERVA_TOTAL`, `VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` | `RF-37`, `AC-55`, `AC-56`, `AC-69`, `EC-15`. A §13.1 Regra 3 **exige** o estado desconhecido como valor, e `mypy --strict` obriga todo consumidor a tratá-lo. Alternativa descartada: `None` — significa "não perguntado", outra coisa (`RF-11`, `collection/respostas.py`) |
| **`_ZERO: Final[Dinheiro] = converter_para_dinheiro("0")`** (`app/montagem/estado.py:266`, já existente) | o zero legítimo de `DINHEIRO_DISPONIVEL` quando `B4.01 = NAO` | `RF-38`, `AC-58`, NFR "Fronteira `Decimal` única". É o **único** zero disponível neste módulo: `tests/app_aluno/estatica/test_fronteira_decimal_unica.py` falha se um `Decimal(...)`/`dinheiro(...)` literal for acrescentado aqui. Alternativa descartada: construir o zero na função — quebraria a fronteira de `RF-13` |
| **`mypy --strict`** (comando `build`, `sdd.config.md` §2 — já em uso) | portão que prova `RF-42` | `AC-66`. É o mecanismo que hoje reporta 1 erro (`app/montagem/estado.py:1326` constrói 13 dos 21 campos) e que passa a reportar zero. Nenhuma configuração nova |
| **pytest** (já em uso) | `AC-51`–`AC-71` | `sdd.config.md` §5. `AC-67`/`AC-68`/`AC-69` são testes de **integração com o motor real** (`calcular_plano`), tolerância **zero** (NFR da fatia: nenhum valor desta fatia é acumulado) — nunca `assertar_monetario` (± R$ 0,05) |
| **`ast`** (stdlib, já em uso pelos estáticos de `tests/app_aluno/estatica/`) | `AC-61`, `AC-71` — auditoria de `app/` por AST | `RF-44`. O teste estático de `motor-calculo` (`tests/estatica/test_sem_derivacao_de_classificacao_mobilizacao.py`) **só varre `engine/`**; um teste próprio, varrendo `app/`, fecha o ponto cego **por decisão**, não por o lint alheio alcançar esta pasta. Ver R2.9 e R2.10 |

**`report/` não ganha dependência.** Jinja2 e WeasyPrint já estão no extra
`app` do `pyproject.toml` desde a Rodada 1 (§2).

## R2.3. Project Structure

| Caminho | Mudança | Novo? |
| --- | --- | --- |
| `app/montagem/estado.py` | `+5` funções `_privadas` de leitura (`_reserva_existe`, `_reserva_total`, `_disposicao_uso_reserva`, `_valor_maximo_reserva_informado_usuario`, `_dinheiro_disponivel`); `+1` exceção nomeada (`ErroDinheiroDisponivelIndeterminado`); `+3` argumentos de tupla vazia em `montar_estado_financeiro`; `+2` imports de `engine.estado`; docstring do módulo estendida (`RF-36`–`RF-39`, `RF-44`, `AC-62`) | não |
| `app/montagem/conversao.py` | **não tocado** — a fronteira já existe e é reusada por `_ZERO` | não |
| `tests/app_aluno/estatica/test_fronteira_import_engine.py` | `+2` entradas em `NOMES_PERMITIDOS_DE_ENGINE` e o bloco de comentário justificativo, no padrão dos quatro precedentes (`RF-40`, `AC-63`, `AC-64`) | não |
| `tests/app_aluno/estatica/hashes_congelados.json` | regravado integralmente a partir da saída do próprio teste; passa a incluir `engine/ataque_imediato.py` (`RF-41`, `AC-65`) | não |
| `tests/app_aluno/fixtures/caso_completo.py` | respostas do Bloco 4 acrescentadas ao caso completo; construção de `EstadoFinanceiro` alinhada aos 21 campos (`RF-42`) | não |
| `tests/app_aluno/test_conversao_decimal.py` (`:300`), `tests/app_aluno/test_plano_ec07_ec08_ec09.py` (`:347`) | os dois `EstadoFinanceiro(...)` construídos à mão ganham os 8 campos novos (`RF-42`, `AC-66`) | não |
| `report/plano.py` | `+1` dataclass de contexto (`ContextoReservaMobilizavel`), `+1` função (`_reserva_mobilizavel`), `+1` campo em `ContextoPlano` (`RF-43`, `AC-70`, `EC-18`) | não |
| `report/templates/plano/reserva_mobilizavel.html` | bloco de exibição do estado "pendente de decisão" × valor, incluído por `plano.html` — mesmo padrão de `pendencias.html` (`RF-43`) | **sim** |
| `tests/app_aluno/test_montagem_bloco_04.py` | `AC-51`–`AC-62`, `AC-67`–`AC-69`, `EC-15`–`EC-17`, `EC-20` | **sim** |
| `tests/app_aluno/estatica/test_sem_patrimonio_derivado_em_app.py` | `AC-61`, `AC-71` — a proibição de `RF-44` auditada por AST sobre `app/` | **sim** |
| `engine/`, `collection/`, `persistencia/` | **não modificados** (`AC-44`; `OQ-24` mantém `collection/respostas.py` intacto nesta fatia) | não |

**Nenhuma pasta nova.** `sdd.config.md` §3 não precisa de alteração nesta
rodada — diferente da Rodada 1, que declarou a divergência de `app/`.

## R2.4. Data Model

Contratos e assinaturas. Nomes idênticos aos da spec, caractere por caractere
(`sdd.config.md` §7). Corpo de função é escopo de `/sdd:implement`.

### R2.4.1. As cinco leituras — `RF-36`, `RF-37`, `RF-38`

**Decisão de nomenclatura deste plano.** Uma função `_privada` por campo,
nomeada pelo campo em minúscula — o padrão que `_tipo_renda` (`:1170`),
`_capacidade_ataque_declarada` (`:1187`) e `_inventario_completo` (`:1204`) já
estabeleceram e que o discovery §5.1 recomendou. Nenhum nome é inventado: cada
um é o `VARIAVEL_GRAVADA` do registro em minúscula.

```python
# app/montagem/estado.py — RF-36 · §13.1 Regra 1 · B4.02, B4.03
# Os dois enums vêm de engine.estado (allowlist ampliada por RF-40).

def _reserva_existe(respostas: RespostasCaso) -> RESERVA_EXISTE: ...
#   B4.02 · VARIAVEL_GRAVADA "RESERVA_EXISTE" · OBR, não repetível
#   valor_interno SIM/INFORMAL/NAO (bloco-04.yaml:52-57) == name do enum
#   (engine/estado.py:187-189) → _membro_do_enum(RESERVA_EXISTE, valor)
#   Ausência de resposta: ErroRespostaAusente("", "B4.02", "RESERVA_EXISTE")
#   — OBR, e o campo não admite Desconhecido. Mesmo padrão de _tipo_renda.

def _disposicao_uso_reserva(respostas: RespostasCaso) -> DISPOSICAO_USO_RESERVA: ...
#   B4.03 · VARIAVEL_GRAVADA "DISPOSICAO_USO_RESERVA" · COND
#   valor_interno PARTE/GRANDE_PARTE/TALVEZ/NAO (:127-133) == name do enum
#   (engine/estado.py:197-200) → _membro_do_enum(...)
#   AUSÊNCIA É ESTRUTURAL, NÃO ERRO (EC-16): condicao_exibicao suprime B4.03
#   quando RESERVA_EXISTE = NAO. Ver R2.4.2 para o valor devolvido.

# app/montagem/estado.py — RF-37 · §13.1 Regra 3 · B4.02A, B4.03A
def _reserva_total(respostas: RespostasCaso) -> DinheiroTalvez: ...
#   B4.02A · "RESERVA_TOTAL" · COND, admite_nao_sei: true
#   NAO_SEI → DESCONHECIDO por _ou_desconhecido (AC-55). Ausência
#   estrutural (B4.02 = NAO) → DESCONHECIDO, nunca erro, nunca 0 (EC-16).

def _valor_maximo_reserva_informado_usuario(respostas: RespostasCaso) -> DinheiroTalvez: ...
#   B4.03A · "VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO" · COND, admite_nao_sei
#   Decimal → repassado (AC-56). NAO_SEI → DESCONHECIDO (AC-56).
#   Opção sem valor_interno ("decidir depois", bloco-04.yaml:154) e ausência
#   estrutural (EC-17) → DESCONHECIDO. Ver R2.4.3 (EC-15/OQ-22).

# app/montagem/estado.py — RF-38 · §13.3 CAIXA_RECOMENDADO · B4.01, B4.01A
def _dinheiro_disponivel(respostas: RespostasCaso) -> Dinheiro: ...
#   Dinheiro PURO — engine/estado.py:517 não admite união com Desconhecido.
#   Três caminhos, cada um explícito (ver R2.4.4 e R2.8).

class ErroDinheiroDisponivelIndeterminado(Exception):
    """RF-38 · EC-20 · AC-59. `DINHEIRO_DISPONIVEL` é `Dinheiro` puro: não
    há `DESCONHECIDO` a entregar, e zero por omissão seria a estimativa
    silenciosa que `sdd.config.md` §4 proíbe. Mesmo padrão de
    `ErroCampoAgregadoDesconhecido` (`:998`), dedicado a este campo.
    Mensagem por `str.join` sobre segmentos curtos (AC-37, `:1254-1259`)."""
    def __init__(self, VARIAVEL_GRAVADA: str, motivo: str) -> None: ...
```

**Por que uma exceção nova e não `ErroRespostaAusente`.** `ErroRespostaAusente`
carrega `DIVIDA_ID`/`ID_PERGUNTA` e nasceu para pergunta `REP` de ficha de
dívida; `ErroCampoAgregadoDesconhecido` é declaradamente "dedicado a agregados
de Bloco 3". `DINHEIRO_DISPONIVEL` não é nenhum dos dois: é campo escalar de
Bloco 4, `Dinheiro` puro, cujo caminho de erro `EC-20`/`OQ-23` precisa ser
distinguível na captura pela chamadora. **Reusar `ErroRespostaAusente` também
seria defensável** — está registrado em R2.10 como trade-off, não como decisão
silenciosa.

### R2.4.2. `_disposicao_uso_reserva` — a ausência estrutural de `EC-16`

`B4.03` é `COND`: `condicao_exibicao` a suprime quando `RESERVA_EXISTE = NAO`
(`bloco-04.yaml:135-137`). Mas `EstadoFinanceiro.DISPOSICAO_USO_RESERVA` é o
enum **puro**, sem união com `Desconhecido` (`engine/estado.py:513`) — não há
"desconhecido" a entregar, e o campo é obrigatório.

**Decisão deste plano:** ausência de resposta em `B4.03` produz
`DISPOSICAO_USO_RESERVA.NAO`, e **só nesse caminho**. Justificativa, em três
passos verificáveis:

1. A ausência só é alcançável quando `RESERVA_EXISTE = NAO` — é a única
   condição que o registro usa para suprimir a pergunta.
2. Nesse caso a Regra 1 da §13.1 **já curto-circuita** em
   `RESERVA_MOBILIZAVEL = 0` pelo primeiro termo (`RESERVA_EXISTE = NAO`),
   independentemente do valor do segundo. O membro escolhido é
   **aritmeticamente inerte**: não muda nenhuma saída do motor.
3. `NAO` é o único membro cuja leitura de fato é verdadeira quando não há
   reserva: não existe disposição de uso de uma reserva que não existe.

**Isto não é reproduzir a Regra 1.** A montagem não escreve
`if RESERVA_EXISTE is NAO: RESERVA_MOBILIZAVEL = 0` — ela entrega os quatro
campos e o motor decide (`AC-68`). O que a decisão acima faz é escolher o valor
de um campo obrigatório numa ausência estrutural, com o motivo em docstring —
o mesmo padrão documentado de `_CAMPOS_DE_GATE_FORA_DE_ESCOPO` (`:315`). A
alternativa (levantar erro) transformaria o caso legítimo "não tenho reserva"
em falha de montagem, contrariando `EC-16` diretamente: *"os campos
condicionais ausentes **não** são erro"*.

### R2.4.3. `_valor_maximo_reserva_informado_usuario` — os três caminhos que colapsam

`B4.03A` tem **três** opções (`bloco-04.yaml:152-155`) e duas ausências
possíveis. O campo devolve `DESCONHECIDO` em tudo que não seja um `Decimal`
real:

| Entrada | Resultado | Âncora |
| --- | --- | --- |
| `Decimal` (campo `R$ ______`) | o próprio `Decimal`, da fronteira única | `AC-56`, `AC-67` |
| `NAO_SEI` (`admite_nao_sei: true`, `:155`) | `DESCONHECIDO` via `_ou_desconhecido` | `AC-56`, `AC-69` |
| "Prefiro decidir somente depois de ver a análise." — **sem `valor_interno`** (`:154`) | `DESCONHECIDO` | `EC-15`, `OQ-22`(a) |
| ausência estrutural (`B4.03 = NAO`, `:157-159`) | `DESCONHECIDO` | `EC-17` |
| ausência estrutural (`B4.02 = NAO`, cadeia) | `DESCONHECIDO` | `EC-16` |

**A opção sem `valor_interno` é `OQ-22`(a), aberta — e este plano não a
fecha.** Aritmeticamente a Regra 3 da §13.1 já obriga "decisão adiada" e "não
sei" a produzirem o **mesmo** `DESCONHECIDA`, então a leitura correta hoje é
idêntica nos dois casos e não depende da resposta. O que `OQ-22`(a) decide é se
o registro passa a **distinguir** os dois para a devolutiva — mudança de YAML,
não de código de leitura. **Enquanto ela estiver aberta, a montagem não pode
distinguir os dois pelo `valor_interno`**, e tratar a opção sem `valor_interno`
como qualquer coisa diferente de desconhecido seria inventar.

### R2.4.4. `_dinheiro_disponivel` — os três caminhos de `RF-38`

`DINHEIRO_DISPONIVEL` é o único dos cinco que é `Dinheiro` **puro**
(`engine/estado.py:517`). Os caminhos, na ordem de avaliação:

| `B4.01` (`DINHEIRO_DISPONIVEL_EXISTE`) | `B4.01A` (`DINHEIRO_DISPONIVEL`) | Resultado | Âncora |
| --- | --- | --- | --- |
| `SIM` | `Decimal` | o `Decimal` da fronteira única | `AC-57` |
| `NAO` | não exibida (`condicao_exibicao`, `:36`) | `_ZERO` — **zero legítimo lido de resposta** | `AC-58` |
| `NAO_SEI` (`:18`) | não exibida | `ErroDinheiroDisponivelIndeterminado` | `EC-20`, `OQ-23` |
| ausente | ausente | `ErroDinheiroDisponivelIndeterminado` | `AC-59` |
| `SIM` | ausente ou `NAO_SEI` | `ErroDinheiroDisponivelIndeterminado` | `RF-38` |

**`_ZERO` no ramo `NAO` não é default.** `sdd.config.md` §4 proíbe inventar
dado, não proíbe ler um zero que o aluno declarou. `B4.01 = NAO` é uma resposta
`OBR` afirmativa — "não possuo dinheiro disponível" — e o zero é a transcrição
dela, não a ausência dela. O que a §4 proíbe é exatamente o quarto e o quinto
ramos, que por isso levantam erro.

**`OQ-23` continua aberta e o plano não a fecha.** Ela pergunta duas coisas:
*qual* erro (encaminhado aqui como decisão de implementação: exceção nomeada
própria, precedente `_renda_principal`) e *como a coleta se recupera dele* —
mais se o registro deveria bloquear o par "`B4.01 = NAO_SEI` + `B4.01A` não
exibida" na própria coleta. **A segunda metade é decisão de produto/registro e
não se decide aqui** (R2.10.1).

### R2.4.5. As três coleções vazias — `RF-39`, `RF-44`

```python
# app/montagem/estado.py::montar_estado_financeiro — RF-39 · AC-60, AC-62
        investimentos=(),
        ativos=(),
        recursos_extraordinarios=(),
```

**Tupla vazia literal no ponto de construção, com o motivo em docstring** — o
mesmo padrão documentado de `_CAMPOS_DE_GATE_FORA_DE_ESCOPO` (`:315`) e de
`CONFIABILIDADE_DADOS` como parâmetro externo. Sem função de leitura, sem
constante intermediária: **não há o que ler**, e uma função vazia sugeriria que
existe leitura parcial.

A docstring de `montar_estado_financeiro` nomeia, caractere por caractere
(`AC-62`):

- `motor-calculo:OQ-26` e `motor-calculo:OQ-27` → `investimentos`, `ativos`.
  **As duas, sempre juntas**: `CLASSIFICACAO_MOBILIZACAO` e
  `VALOR_LIQUIDO_REALIZAVEL*` são obrigatórios e sem default nas três
  dataclasses de item, por causas independentes — responder só uma não destrava
  (spec §9).
- `OQ-22` e `OQ-24` → `recursos_extraordinarios`.

**`AC-60` é mais forte do que "não implementado".** Ele exige que as três
coleções permaneçam vazias **mesmo com fichas de investimento, imóvel, veículo
e outro ativo preenchidas** — a lacuna é do contrato, não da coleta.

### R2.4.6. `EstadoFinanceiro` completo — o alvo de `RF-42`

`montar_estado_financeiro` passa a construir os **21** campos. Assinatura
inalterada: os cinco campos novos são lidos de `respostas`, nenhum vira
parâmetro externo novo.

```python
def montar_estado_financeiro(
    respostas: RespostasCaso,
    *,
    DATA_REFERENCIA: date,
    dividas: tuple[Divida, ...],
    CONFIABILIDADE_DADOS: CONFIABILIDADE_DADOS,
    economia_nao_identificada: Dinheiro | None = None,
    DIVIDA_ID_PARA_LINHA_CONTINUA: str | None = None,
) -> EstadoFinanceiro: ...
#   +8 argumentos no construtor, todos derivados de `respostas` ou literais:
#     RESERVA_EXISTE=_reserva_existe(respostas)
#     RESERVA_TOTAL=_reserva_total(respostas)
#     DISPOSICAO_USO_RESERVA=_disposicao_uso_reserva(respostas)
#     VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=
#         _valor_maximo_reserva_informado_usuario(respostas)
#     DINHEIRO_DISPONIVEL=_dinheiro_disponivel(respostas)
#     investimentos=() · ativos=() · recursos_extraordinarios=()
```

**A função continua pura** (`tests/app_aluno/estatica/
test_sem_relogio_em_montagem.py`): nenhuma das cinco leituras toca relógio,
ambiente ou estado global.

### R2.4.7. Exibição do desconhecido — `RF-43`

**Decisão de localização deste plano: `report/`, não `app/`, e reaproveitando a
convenção que já existe.** Investigado antes de decidir:

- `report/plano.py:180` já tem `_formatar_valor_ou_desconhecido`, que renderiza
  `Desconhecido` como o literal `"DESCONHECIDO"` — **mas é a convenção da tela
  do REVISOR** (`RF-26`, `AC-29`, `_campos_de_apoio`), onde o rótulo técnico é
  adequado e desejável.
- `report/plano.py:431` já tem `_pendencias`/`ContextoPendencias` +
  `pendencias.html` — **a convenção da tela do ALUNO** para "o que está em
  aberto", com texto em português no template e leitura pura por
  `is DESCONHECIDO` (`:427`) em `report/plano.py`.

`RF-43` é sobre o **aluno**, então segue a segunda convenção, não a primeira.
Estrutura, idêntica em forma a `ContextoPendencias`/`_pendencias`:

```python
# report/plano.py — RF-43 · AC-70 · EC-18 · §13.1 ("não convertido
# silenciosamente em zero")

@dataclass(frozen=True, slots=True)
class ContextoReservaMobilizavel:
    """`RF-43` — `Diagnostico.RESERVA_MOBILIZAVEL` (`DinheiroTalvez`,
    `engine/diagnostico.py:654`) pronto para exibição ao aluno. Os dois
    estados são campos SEPARADOS, não um texto que o template precise
    interpretar: `pendente_de_decisao` decide QUAL bloco aparece, `valor`
    só é lido quando ele é `False`."""

    pendente_de_decisao: bool   # RESERVA_MOBILIZAVEL is DESCONHECIDO
    valor: str                  # "" quando pendente; formatado quando não

def _reserva_mobilizavel(snapshot: SnapshotOrdem) -> ContextoReservaMobilizavel: ...
#   Leitura pura: `is DESCONHECIDO` — nenhuma aritmética, nenhuma inferência
#   (mesma disciplina de `_campos_desconhecidos_da_divida`, `:419`).
#   NUNCA passa por `_formatar_valor_de_apoio` no ramo desconhecido: aquela
#   função faria `str(valor)` e produziria "Desconhecido.DESCONHECIDO".

# ContextoPlano ganha UM campo:
    reserva_mobilizavel: ContextoReservaMobilizavel
```

`report/templates/plano/reserva_mobilizavel.html`, incluído por `plano.html`
no mesmo ponto em que `pendencias.html` é incluído:

```jinja
{% if reserva_mobilizavel.pendente_de_decisao %}
  <!-- estado explícito de pendência — NUNCA R$ 0,00, NUNCA omissão -->
{% else %}
  <!-- o valor: {{ reserva_mobilizavel.valor }} -->
{% endif %}
```

> **A REDAÇÃO É `OQ-21`, ABERTA, E NÃO SE INVENTA AQUI.** Este plano fixa o
> **comportamento** e o **ponto de encaixe** (`RF-43` é explícito: *"esta spec
> fixa o comportamento, não o texto"*). O texto que o aluno lê no ramo
> "pendente de decisão" é insumo do especialista. **Consequência de
> sequenciamento:** o template pode ser criado com a estrutura condicional e o
> comportamento testável (`AC-70` verifica que **não** exibe `R$ 0,00`, que
> **não** omite o item e que nenhum caminho levanta exceção — três asserções
> que não dependem da redação), mas o texto definitivo entra quando `OQ-21` for
> respondida. Precedente do projeto: `app/consentimento/registro.py`, onde
> texto pendente (`PEND-01`) tem ponto de encaixe pronto e conteúdo externo.

## R2.5. Data Flow

### R2.5.1. O caminho do dado — do Bloco 4 ao motor

```text
1. COLETA (não tocada nesta fatia)
   B4.01 → grava DINHEIRO_DISPONIVEL_EXISTE (SIM|NAO|NAO_SEI)
   B4.01A → grava DINHEIRO_DISPONIVEL (Decimal, pela fronteira de RF-13)
   B4.02 → RESERVA_EXISTE (SIM|INFORMAL|NAO)
   B4.02A → RESERVA_TOTAL (Decimal | NAO_SEI)
   B4.03 → DISPOSICAO_USO_RESERVA (PARTE|GRANDE_PARTE|TALVEZ|NAO)
   B4.03A → VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO (Decimal | NAO_SEI | —)

2. LEITURA — app/montagem/estado.py
   respostas.valor("<VARIAVEL_GRAVADA>")   ← SEMPRE escalar (AC-71)
        │
        ├─ enum      → _membro_do_enum(EnumAlvo, valor_interno)
        │                └─ falha: ErroValorInternoDesconhecido (AC-54)
        ├─ monetário → _ou_desconhecido(valor)
        │                └─ NAO_SEI → DESCONHECIDO (AC-55, AC-56)
        └─ Dinheiro puro → _ZERO | Decimal | erro nomeado (AC-57..AC-59)

3. MONTAGEM — EstadoFinanceiro com 21 campos, 3 coleções vazias (AC-60)

4. MOTOR — calcular_plano(...)  [CONGELADO]
   engine/diagnostico.py:788-815 → derivar_RESERVA_MOBILIZAVEL (§13.1)
     Regra 1: RESERVA_EXISTE=NAO ou DISPOSICAO_USO_RESERVA=NAO → 0
     Regra 2: MIN(RESERVA_TOTAL, MAX(0, informado))       ← DO MOTOR
     Regra 3: desconhecido em qualquer termo → DESCONHECIDO
        ↑ NENHUMA das três é reproduzida em app/ (RF-44, AC-68)

5. APRESENTAÇÃO — report/plano.py::_reserva_mobilizavel
   is DESCONHECIDO → bloco "pendente de decisão" (RF-43, AC-70)
   Decimal        → valor formatado
```

### R2.5.2. Onde cada etapa falha

| Etapa | Falha | Resposta | Recuperação |
| --- | --- | --- | --- |
| 2 — enum | `valor_interno` fora do domínio | `ErroValorInternoDesconhecido(enum, valor)` nomeando os dois | Nenhuma automática: é regressão de transcrição entre YAML e enum (`AC-54`). Corrigir o registro, nunca acrescentar um `if` |
| 2 — `B4.02` ausente | pergunta `OBR` sem resposta | `ErroRespostaAusente("", "B4.02", "RESERVA_EXISTE")` | Coleta reabre `B4.02` |
| 2 — `B4.03` ausente | ausência **estrutural** | `DISPOSICAO_USO_RESERVA.NAO` (R2.4.2) — **não é falha** | — |
| 2 — `B4.02A`/`B4.03A` ausentes | ausência **estrutural** | `DESCONHECIDO` — **não é falha** (`EC-16`, `EC-17`) | — |
| 2 — `B4.01` `NAO_SEI`/ausente | campo `Dinheiro` puro sem valor | `ErroDinheiroDisponivelIndeterminado` | **`OQ-23`, aberta** — como a coleta se recupera não se decide aqui |
| 4 | `ErroInvariante` do motor | Inalterado: `EC-03` da Rodada 1 (§8) | Inalterado |
| 5 | `RESERVA_MOBILIZAVEL is DESCONHECIDO` | Bloco "pendente de decisão" — **nunca exceção, nunca `R$ 0,00`** (`AC-70`, `EC-18`) | — |

### R2.5.3. Ordem de execução — a dependência que `RF-40` cria

**A allowlist precisa ser ampliada ANTES da leitura que a exige.** Se a ordem
inverter, `test_fronteira_import_engine.py::
test_pastas_da_aplicacao_nao_importam_engine_interno_ac_41` falha no meio da
rodada — e essa falha já aconteceu uma vez: a tentativa mecânica de preencher
os 8 campos com valores neutros reprovou nesse mesmo teste e foi revertida
integralmente (spec §8, discovery §1).

Sequência obrigatória:

```text
1. RF-40 — allowlist +2 nomes                    [tests/.../estatica/]
       ↓  (sem isto, o passo 2 quebra o teste de fronteira)
2. RF-36..RF-39, RF-44 — as leituras + coleções  [app/montagem/estado.py]
       ↓  (mypy --strict: 1 erro → 0)
3. RF-42 — fixtures e os dois testes             [tests/app_aluno/]
       ↓  (a suíte volta a coletar e passar)
4. RF-41 — hashes regravados                     [.../hashes_congelados.json]
       ↓  (independente de 1-3; pode correr em paralelo)
5. RF-43 — exibição do desconhecido              [report/]
       ↓  (depende de 2: só então o caminho é alcançável)
6. AC-67, AC-68, AC-69 — integração com o motor real
```

**`RF-41` é independente dos demais** (o JSON não é importado por código de
produção) e falha **hoje**, antes de qualquer edição desta rodada:
`engine/ataque_imediato.py` existe no disco e não consta do JSON. Pode ser o
primeiro passo, e provavelmente deve — deixa a suíte com uma causa de falha a
menos enquanto o resto anda.

**`RF-41` regrava a partir da saída do próprio teste, nunca de uma lista
transcrita** (`AC-65`). O teste nomeia arquivo por arquivo; uma lista escrita no
enunciado da tarefa envelhece entre a redação e a execução.
`persistencia/supabase/migracoes/002_app_aluno.sql` permanece **fora** do
conjunto, deliberadamente.

## R2.6. External Interfaces

**Nenhuma interface externa nova.** Nada de rede, nada de fornecedor, nada de
autenticação nova nesta fatia. As duas fronteiras internas relevantes:

| Fronteira | Contrato | Direção | Mudança nesta fatia |
| --- | --- | --- | --- |
| `app/montagem/` → `engine.estado` | `EstadoFinanceiro` (21 campos), `RESERVA_EXISTE`, `DISPOSICAO_USO_RESERVA` | `app/` importa de `engine/`; a recíproca nunca | **Consumo** de contrato já publicado pela Rodada 3 de `motor-calculo`. Nada em `engine/` é alterado (`AC-44`) |
| `app/montagem/` → `collection.respostas` | `RespostasCaso.valor(variavel) -> ValorResposta \| None` | leitura | Nenhuma. **`valores_do_escopo` não é chamado para nenhuma variável do Bloco 4** (`AC-71`) |
| `report/` → `engine.snapshot`/`engine.diagnostico` | `SnapshotOrdem.diagnostico.RESERVA_MOBILIZAVEL: DinheiroTalvez` | leitura | Passa a ser lido. `engine.tipos` (de onde vem `DESCONHECIDO`) já é liberado por inteiro — **`RF-43` não exige ampliação de allowlist** |

**A allowlist de `AC-41`, depois desta fatia** (`RF-40`, `AC-63`):

```python
# ADICIONADOS — exatamente dois, cada um com comentário justificativo no
# padrão dos quatro precedentes (TIPO_DIVIDA/T-49; os 8 do Bloco 2/T-50;
# TIPO_RENDA/T-51; AcaoRequerida/T-74):
"engine.estado.RESERVA_EXISTE",
"engine.estado.DISPOSICAO_USO_RESERVA",
```

**Critério, e por que só dois.** O mesmo Critério A já aplicado quatro vezes:
*"enum que COMPÕE um tipo de entrada liberado — sem liberá-lo é impossível
montar um `EstadoFinanceiro` tipado fora de `engine/` sob `mypy --strict`"*. Os
dois tipam `EstadoFinanceiro.RESERVA_EXISTE` (`engine/estado.py:511`) e
`.DISPOSICAO_USO_RESERVA` (`:513`), e não são redefinidos nem reexportados por
`engine.tipos`.

**Os cinco nomes do levantamento que NÃO entram**: `ItemInvestimento`,
`ItemAtivo`, `RecursoExtraordinario`, `JANELA_RECURSO_EXTRAORDINARIO`,
`CERTEZA_RECURSO_EXTRAORDINARIO`. A fatia 2A não os importa, e **allowlist não
contém nome que ninguém usa** — é ampliação por fatia, exatamente o que o
próprio arquivo já registrou por escrito sobre `Oportunidade`
(`test_fronteira_import_engine.py:70-72`).

**`CLASSIFICACAO_MOBILIZACAO` e `Desconhecido` não exigem decisão nenhuma**:
vivem em `engine.tipos`, já liberado por inteiro (`:151-156`). Que a importação
fosse *possível* nunca foi o que bloqueava 2C.

**As proibições explícitas continuam recusadas** (`AC-64`): `engine.gates` além
de `AcaoRequerida`, `engine.ciclo_mensal` além de `ErroInvariante`,
`engine.metodos.*`, `engine.comparacao`, `engine.ordem`, `from engine import *`.

## R2.7. State Management

**Nenhum estado novo, em nenhuma camada.** Verificado item a item:

- **Nenhuma tabela nova, nenhuma migração nova.** As seis respostas do Bloco 4
  já são gravadas por `app_aluno.respostas` como qualquer outra (`RF-10`) —
  esta fatia só passa a **lê-las**.
- **Nenhum membro novo em `EscopoRepeticao`.** A fatia lê apenas campos
  escalares, por `respostas.valor(...)`. Os membros para investimento/imóvel/
  veículo/outro ativo são `OQ-25`, que **não bloqueia 2A nem 2B**.
- **Nenhum estado novo na máquina do caso** (§7.1 da Rodada 1). A montagem
  continua acontecendo dentro do Bloco 6, na mesma transição.
- **`montar_estado_financeiro` continua pura e sem estado próprio.** A mesma
  `RespostasCaso` produz sempre o mesmo `EstadoFinanceiro` — comparável por
  `==` estrutural (`frozen=True, slots=True`).
- **`hash_inputs` muda para todo snapshot novo**, porque `EstadoFinanceiro`
  ganhou 8 campos. Isso **já aconteceu** quando `motor-calculo` publicou o
  contrato (`engine/estado.py:485-489`: *"uma leva, uma mudança de hash"*) —
  esta fatia não introduz uma segunda mudança de hash. Snapshots antigos
  permanecem íntegros: `V-01`, append-only, nada é reescrito.
- **`RESERVA_MOBILIZAVEL` desconhecida é estado registrável, não erro** (NFR da
  fatia): aparece na trilha do caso (`RF-31`) e na tela do revisor (`RF-26`)
  como pendência. **Nenhum log carrega valor monetário** — o NFR de
  observabilidade da Rodada 1 continua valendo integralmente.

## R2.8. Error Handling Strategy

| Situação | Detecção | Resposta | Recuperação |
| --- | --- | --- | --- |
| `B4.02` (`OBR`) sem resposta | `respostas.valor(...) is None` | `ErroRespostaAusente("", "B4.02", "RESERVA_EXISTE")` | Coleta reabre a pergunta (mecanismo de `RF-27` já existente) |
| `valor_interno` fora do domínio do enum | `KeyError` em `_membro_do_enum` | `ErroValorInternoDesconhecido(enum_alvo, valor_interno)` | **Nenhuma automática** (`AC-54`): é divergência entre YAML e enum. Corrigir o registro — **nunca** um `if` que "conserte" o contrato |
| `B4.01` `NAO_SEI` ou ausente | `valor is None` / `== "NAO_SEI"` | `ErroDinheiroDisponivelIndeterminado` nomeando a variável | **`OQ-23`, aberta.** A recuperação (e se o registro deve impedir o par na coleta) não se decide aqui |
| `B4.02A`/`B4.03A` ausentes por condição | `valor is None` | `DESCONHECIDO` — **não é erro** (`EC-16`, `EC-17`) | — |
| `B4.03` ausente por condição | `valor is None` | `DISPOSICAO_USO_RESERVA.NAO` (R2.4.2) — **não é erro** | — |
| `RESERVA_MOBILIZAVEL is DESCONHECIDO` na tela | `is DESCONHECIDO` em `_reserva_mobilizavel` | Bloco "pendente de decisão". **Nunca `R$ 0,00`, nunca omissão, nunca exceção** (`AC-70`, `EC-18`) | O aluno responde `B4.02A`/`B4.03A` → recálculo pelo caminho já existente |
| `loading` / `vazio` / falha de banco | — | Inalterados: §8 da Rodada 1 | Inalterado |

**A disciplina única desta seção:** nenhum dos caminhos acima devolve `0`,
`None` ou estimativa em lugar de um valor que não existe. `_ZERO` aparece em
**exatamente um** ramo — `B4.01 = NAO` —, e ali ele é a transcrição de uma
resposta afirmativa, não a ausência dela.

## R2.9. Testing Strategy

- **Unitários de leitura** — `tests/app_aluno/test_montagem_bloco_04.py`
  (pytest). Uma `RespostasCaso` montada em memória por caso, sem banco:
  - `AC-51` — os **três** membros de `RESERVA_EXISTE`, nenhum colapsado.
  - `AC-52` — os **quatro** membros de `DISPOSICAO_USO_RESERVA`.
  - `AC-54` — `valor_interno` inválido → `ErroValorInternoDesconhecido`
    nomeando enum e valor.
  - `AC-55`, `AC-56` — `NAO_SEI` → `is DESCONHECIDO`; valor → `Decimal` exato,
    sem `float` no caminho.
  - `AC-57`, `AC-58`, `AC-59` — os três caminhos de `DINHEIRO_DISPONIVEL`,
    incluindo o erro nomeado.
  - `AC-60` — as três coleções vazias **mesmo com fichas de ativo preenchidas**.
  - `EC-15`, `EC-16`, `EC-17`, `EC-20` — um teste por caso de borda.
- **Estáticos (AST)** — `tests/app_aluno/estatica/`:
  - `AC-53` — `_membro_do_enum` no caminho dos dois enums **e** nenhum rótulo
    em português de `B4.02`/`B4.03` no arquivo (`AC-37` continua verde).
  - `AC-61`, `AC-71` — **arquivo novo**,
    `test_sem_patrimonio_derivado_em_app.py`: varre `app/` e recusa (a) anotação
    de retorno `CLASSIFICACAO_MOBILIZACAO`, (b) literal dos quatro membros
    atribuído a um item, (c) soma de `VALOR_ESTIMADO_ATIVO`,
    `SALDO_PASSIVO_VINCULADO`, `CUSTOS_ESTIMADOS_DESMOBILIZACAO`, (d) chamada a
    `valores_do_escopo` com variável do Bloco 4.
  - `AC-63`, `AC-64` — a allowlist ganhou **exatamente dois** nomes; as
    proibições anteriores continuam recusadas.
  - `AC-65` — os quatro testes de `AC-44`; `engine/ataque_imediato.py` presente;
    `002_app_aluno.sql` ausente.
  - Não-regressão: `test_fronteira_decimal_unica.py` e
    `test_sem_relogio_em_montagem.py` continuam verdes — **nenhum `Decimal(...)`
    literal novo, nenhuma leitura de relógio**.
- **Integração com o motor real** — `calcular_plano` de verdade, parâmetros
  reais, **tolerância zero**:
  - `AC-67` — `B4.02=SIM`, `B4.03=PARTE`, `B4.02A=10000`, `B4.03A=3000` →
    `RESERVA_MOBILIZAVEL == Decimal("3000")`. É o ganho observável: deixa de ser
    o `0` que a montagem produzia.
  - `AC-68` — `B4.03A=30000`, `B4.02A=10000` → `Decimal("10000")`. **Verificado
    na saída do motor, sem contrapartida em `app/`** — é exatamente esta
    assimetria que prova que a Regra 2 não foi reproduzida na montagem.
  - `AC-69` — `B4.03=TALVEZ`, `B4.03A="Não sei."` →
    `RESERVA_MOBILIZAVEL is DESCONHECIDO`. Nenhum ponto do caminho o converte em
    zero.
  - **`assertar_monetario` (± R$ 0,05) é proibido nestes três.** Nenhum valor
    desta fatia é acumulado — todos são leitura direta. A régua é
    `assertar_exato`.
- **Apresentação** — `AC-70`: três asserções que **não dependem da redação de
  `OQ-21`** — (1) o HTML não contém `R$ 0,00` no ramo desconhecido, (2) o item
  não é omitido, (3) nenhum caminho levanta exceção. Mais o ramo com valor,
  que exibe o valor.
- **Portão de `RF-42`/`AC-66`** — os comandos da seção 2 do `sdd.config.md`:
  `build` (`mypy --strict`) de 1 erro para **zero**; `tests/app_aluno/` de ~129
  falhas de causa raiz única para **zero**.
- **Fora de teste automatizado:** a **redação** do estado pendente (`OQ-21`,
  insumo do especialista — testa-se o comportamento, não o texto); a
  **recuperação de coleta** de `EC-20` (`OQ-23`, aberta).

## R2.10. Risks & Trade-offs

| Decisão | Alternativa descartada | Por quê | Risco assumido |
| --- | --- | --- | --- |
| `_disposicao_uso_reserva` devolve `NAO` na ausência estrutural (R2.4.2) | Levantar erro; ou acrescentar `Desconhecido` ao tipo do campo | O erro contrariaria `EC-16` diretamente (*"os campos condicionais ausentes não são erro"*); mudar o tipo exigiria alterar `engine/`, proibido por `AC-44`. O membro é **aritmeticamente inerte**: a Regra 1 já curto-circuitou por `RESERVA_EXISTE = NAO` | Alguém lê o `NAO` como se a montagem tivesse decidido a Regra 1. Mitigado por docstring explícita e por `AC-68`, que prova que o limite vem do motor. **Merece confirmação humana** — ver R2.10.1 |
| Exceção nomeada nova (`ErroDinheiroDisponivelIndeterminado`) | Reusar `ErroRespostaAusente` | As duas existentes são declaradamente dedicadas (ficha `REP` de dívida; agregados do Bloco 3). O caminho de `EC-20` precisa ser distinguível na captura pela chamadora | Uma quarta classe de exceção no módulo. **Reusar seria defensável** — ver R2.10.1 |
| Tupla vazia literal no construtor, sem função de leitura (R2.4.5) | Três funções `_investimentos()`/`_ativos()`/`_recursos_extraordinarios()` devolvendo `()` | Não há o que ler: uma função sugeriria leitura parcial existente. O padrão de lacuna documentada do módulo é constante/literal com motivo em docstring (`_CAMPOS_DE_GATE_FORA_DE_ESCOPO`) | Quando 2B/2C destravarem, três funções nascem de uma vez. Custo baixo e previsto |
| `RF-43` em `report/`, no padrão `pendencias.html` | Em `app/`; ou reusar `_formatar_valor_ou_desconhecido` | `report/` é onde a apresentação já mora, e `_formatar_valor_ou_desconhecido` é a convenção da tela do **revisor** (rótulo técnico `"DESCONHECIDO"`), inadequada para o aluno. `pendencias.html` é a convenção do **aluno** para "o que está em aberto" | Duas convenções de desconhecido em `report/`. Já era assim antes desta fatia — a fatia respeita a separação, não a cria |
| Ampliar a allowlist com **dois** nomes | Os sete do levantamento; ou preencher os campos com valores neutros | Preencher com neutros **já foi tentado e reprovou** no teste de fronteira, com reversão integral. Sete conteria nome que ninguém importa | Duas ampliações futuras (2B, 2C) em vez de uma. É o custo desejado: a allowlist nunca contém nome sem consumidor |
| **Não corrigir `valores_do_escopo`** | Corrigir agora, "já que está aberto o arquivo" | É `OQ-24`, **aberta**, e afeta os cinco escopos já em uso (exige não-regressão em renda adicional e despesa não-mensal). A fatia 2A **não lê item nenhum** — `AC-71` prova a independência | O bug permanece latente. Mitigado por `AC-71` (torna a não-dependência verificável) e por `OQ-24` ser bloqueante para 2B/2C |
| **Não derivar `CLASSIFICACAO_MOBILIZACAO` em `app/`** | Derivar aqui, já que o teste estático de `motor-calculo` só varre `engine/` | Derivar em `app/` **passaria no lint e ainda assim violaria** a Lei nº 3 e `sdd.config.md` §6. Encontrar o ponto cego da regra não é cumpri-la — o discovery (§4.1) já fechou essa escapatória | Nenhum: `AC-61` fecha o ponto cego **por decisão**, com teste próprio varrendo `app/` |
| **Não reimplementar a Regra 2 da §13.1** | Calcular `MIN`/`MAX` na montagem "para conferir" | `RESERVA_MOBILIZAVEL` já é derivado pelo motor (`engine/diagnostico.py:788-815`). Esta fatia muda a **entrada**, não a derivação. Duas implementações da mesma fórmula não teriam dono numa divergência futura | Nenhum: `AC-68` exige a verificação **na saída do motor**, sem contrapartida no app |

### R2.10.1. Ambiguidades — o que este plano NÃO decide

`sdd.config.md` §3: o que a spec deixou aberto continua aberto. Registrado aqui
para que apareça no sequenciamento, não para ser resolvido.

**Questões de terceiro — não se resolvem neste plano:**

| ID | Bloqueia | Situação |
| --- | --- | --- |
| `motor-calculo:OQ-26` | fatia **2C** | `CLASSIFICACAO_MOBILIZACAO` obrigatório e sem default; derivar é proibido (`AC-67` daquele slug, por AST); perguntar é proibido (`piq-app-spec.md:2614`) |
| `motor-calculo:OQ-27` | fatia **2C** | `VALOR_LIQUIDO_REALIZAVEL*` idem, por causa **independente**. **As duas precisam estar respondidas — responder só uma não destrava** |
| `motor-calculo:OQ-29` | Bloco 10 (`T-77`/`T-78`/`T-79`) | `ATAQUE_IMEDIATO_RECOMENDADO` segue `dinheiro(0)` por decisão registrada. O aluno **não** verá ataque imediato ao fim desta fatia; verá a reserva mobilizável correta |

**Questões nossas, encaminhadas ou ainda abertas:**

| ID | O que este plano faz | O que continua aberto |
| --- | --- | --- |
| `OQ-20` | **Encaminhada.** R2.6 fixa os dois nomes, o critério (Critério A, quatro precedentes) e o comentário justificativo | Nada — é decisão do plano, e está tomada |
| `OQ-21` | **Ponto de encaixe pronto** (R2.4.7): estrutura condicional, contexto e testes que não dependem do texto | **A redação ao aluno.** Insumo do especialista. Texto não se inventa aqui |
| `OQ-22`(a) | Leitura correta hoje é `DESCONHECIDO` para "decidir depois" e para "não sei" — a Regra 3 já os colapsa aritmeticamente (`EC-15`) | **Se o registro passa a distinguir os dois** para a devolutiva. Mudança de YAML, não de código de leitura |
| `OQ-22`(b) | — | Bloqueia **2B** (`B3.05C`, `valor_interno: null` nas cinco opções) |
| `OQ-23` | **Metade encaminhada:** exceção nomeada própria, precedente `_renda_principal` | **Como a coleta se recupera** e **se o registro deveria impedir** o par `B4.01 = NAO_SEI` + `B4.01A` não exibida. Decisão de produto/registro |
| `OQ-24` | Nada — e é deliberado. `AC-71` prova que 2A não depende dela | Bloqueia **2B e 2C**. Nenhuma linha de leitura de item antes dela |
| `OQ-25` | Nada | Bloqueia **2C**, que já está bloqueada por `motor-calculo:OQ-26`/`OQ-27`. Não urge |

**Nenhuma ambiguidade técnica nova foi encontrada** ao inspecionar o código
para escrever este plano. As duas decisões de implementação que mais se
aproximam de uma — o membro devolvido na ausência de `B4.03` (R2.4.2) e a
escolha de exceção nova × reuso (R2.4.1) — estão na tabela de trade-offs acima
com a alternativa descartada nomeada, e ambas são reversíveis sem retrabalho
estrutural.

## R2.11. Traceability

| Requisito | Coberto por (seção do plano) |
| --- | --- |
| `RF-36` — `RESERVA_EXISTE`/`DISPOSICAO_USO_RESERVA` por `_membro_do_enum` | R2.4.1 (`_reserva_existe`, `_disposicao_uso_reserva`) · R2.4.2 (ausência estrutural) · R2.2 (por que reusar o genérico) · R2.9 (`AC-51`, `AC-52`, `AC-53`, `AC-54`) |
| `RF-37` — `RESERVA_TOTAL`/`VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` como `DinheiroTalvez` | R2.4.1 · R2.4.3 (os três caminhos que colapsam em `DESCONHECIDO`) · R2.5.1 (etapa 2) · R2.9 (`AC-55`, `AC-56`, `AC-69`) |
| `RF-38` — `DINHEIRO_DISPONIVEL` como `Dinheiro` puro, zero legítimo × erro nomeado | R2.4.1 (`ErroDinheiroDisponivelIndeterminado`) · R2.4.4 (tabela dos três caminhos) · R2.8 · R2.9 (`AC-57`, `AC-58`, `AC-59`) |
| `RF-39` — três coleções como tupla vazia declarada, motivo em docstring | R2.4.5 · R2.3 (`app/montagem/estado.py`) · R2.9 (`AC-60`, `AC-62`) |
| `RF-40` — allowlist `+2` nomes, exatamente | R2.6 (os dois nomes, o critério e os cinco que **não** entram) · R2.5.3 (a ordem obrigatória) · R2.9 (`AC-63`, `AC-64`) |
| `RF-41` — hashes regravados a partir da saída do teste | R2.3 · R2.5.3 (independente, e falha hoje) · R2.9 (`AC-65`) |
| `RF-42` — fixtures e testes atualizados; `build` e suíte verdes | R2.3 (os três arquivos) · R2.4.6 (`EstadoFinanceiro` de 21 campos) · R2.9 (portão de `AC-66`) |
| `RF-43` — `RESERVA_MOBILIZAVEL` desconhecida como estado explícito | R2.4.7 (`ContextoReservaMobilizavel`, `report/`, convenção reaproveitada) · R2.5.1 (etapa 5) · R2.8 · R2.9 (`AC-70`, sem depender de `OQ-21`) · R2.10.1 (`OQ-21` aberta) |
| `RF-44` — leitura livre de agregação ou fórmula patrimonial | R2.1 (Lei nº 3 preservada) · R2.4.5 · R2.5.1 (etapa 4: as três regras são **do motor**) · R2.9 (`AC-61`, `AC-71`, teste estático novo) · R2.10 (duas linhas próprias na tabela) |

> Requisito sem cobertura é buraco no plano. Item de plano sem requisito é
> over-engineering. **Os nove requisitos da fatia 2A (`RF-36`–`RF-44`) têm
> cobertura.** Um com cobertura **parcial e declarada**, por insumo externo —
> não por omissão: `RF-43`, cuja **redação** depende de `OQ-21` (o
> comportamento e o ponto de encaixe estão cobertos e são testáveis sem ela).

## R5.1. Architecture Overview — a navegação que faltava escrever

A Rodada 4 entregou os **tokens** do protótipo e inventou a **navegação**. Esta
rodada faz o inverso: não toca em cor, tipografia nem raio — reescreve como o
aluno anda pelo produto.

O desenho é o do protótipo, e ele tem nome: **fluxo linear guiado**. Uma tela
por vez, dentro de uma casca fixa de três partes:

```text
┌─ .top ──────────────────────────────┐   ‹ Voltar          localizador
├─ .corpo ────────────────────────────┤   o conteúdo, rolável
│                                     │
├─ .acoes ────────────────────────────┤   sticky: a ação nunca sai da tela
└─────────────────────────────────────┘
```

A barra de sete abas morre. Ela não é uma variação do desenho — é o desenho
oposto: oferece todas as telas o tempo todo a quem precisa saber qual é a
próxima. **A tela Início é o que substitui a barra**, e ela oferece uma etapa só.

### A regra que a barra de abas violava

`RF-34` (Lei nº 3) diz que a aplicação não decide nada de método. A barra de
abas parecia navegação inocente, mas era **decisão de fluxo no cliente**: quem
escolhia se o aluno ia para "Ataque" ou "Ações" era ele mesmo, diante de sete
botões, sem saber qual se aplicava ao seu caso. `RF-58` devolve essa decisão ao
servidor: `GET /caso/{CASO_ID}/inicio` lê a fase e devolve **uma** próxima etapa.

### As cinco fases e os doze estados

`ESTADO_CASO` tem 12 membros (`app/casos/maquina.py:78-92`); o protótipo tem 5
ramos em `renderInicio`. O mapa entre os dois é `app/casos/fases.py`, módulo
**puro** — sem I/O, sem FastAPI, na disciplina de `progresso.py` e
`mensagens_de_estado.py`.

`fase_do_estado` usa `match` **exaustivo sem `case _`**: é a trava que faz um
membro novo de `ESTADO_CASO` sem fase declarada **falhar no `mypy`** em vez de
cair num default silencioso (`AC-89`). O precedente é
`mensagens_de_estado.py:42-71`, que já faz exatamente isso, com a justificativa
escrita no cabeçalho do módulo.

| `ESTADO_CASO` | fase | por quê |
| --- | --- | --- |
| `CADASTRADO` | `coleta` | ainda não consentiu; a próxima etapa é o consentimento, que do ponto de vista do aluno é parte da coleta |
| `CONSENTIMENTO_REGISTRADO` | `coleta` | — |
| `COLETA_INICIAL` | `coleta` | o caso canônico do protótipo (`62 de 195`) |
| `COLETA_DIRIGIDA` | `coleta` | Blocos 7/8 são coleta, dirigida pelo motor |
| `CALCULANDO` | `revisao` | o aluno vê *"estamos montando o seu plano"*. A **fase** é a mesma — *é com a gente, você não faz nada*; só muda o destino, a tela do `.pulse` |
| `ERRO_DE_CALCULO` | `revisao` | `mensagem_do_estado_do_caso` já diz *"Seu plano está em nova análise"*. **Nunca** expor o erro técnico ao aluno; inventar tela de erro é escopo extra |
| `AGUARDANDO_REVISAO` | `revisao` | literal |
| `REPROVADO_EM_REVISAO` | `reprovado` | literal |
| `PLANO_LIBERADO` | `plano` **ou** `acompanhamento` | ver a exceção abaixo |
| `CONFIRMACAO_ATAQUE` | `plano` | é exatamente *"Decidir sobre os R$ X"* — o caso já entrou no Bloco 10 |
| `ACOMPANHAMENTO` | `acompanhamento` | o `else` do protótipo |
| `ENCERRADO` | `acompanhamento` | **não criar sexta fase**: a mensagem é *"Seu caso foi encerrado"*, que `mensagens_de_estado.py` já produz. O **destino** é o plano, não a lista de ações — ver a nota abaixo |

**Nenhuma fase nova é criada.** Duas tentações foram recusadas, e as duas
últimas linhas da tabela são onde elas moravam.

> **`ENCERRADO`: fase `acompanhamento`, destino `plano`** (decidido na
> implementação de `T-147`, registrado aqui). O plano dizia "cartão de
> acompanhamento com `acoes: []`", e mandar o aluno à lista de ações vazia
> seria coerente com a fase — mas é uma tela que só pode dizer "não há nada
> aqui". Quem teve o caso encerrado quer o registro do que foi feito, e é o
> plano que o guarda. A **fase** continua `acompanhamento` (não há sexta
> fase), e é só o destino que difere dos demais casos dessa fase.

`PLANO_LIBERADO` é a **única** exceção a "fase é função do estado": depende
também do snapshot. A fase `plano` do protótipo é literalmente *"Decidir sobre
os R$ 3.000,00"* — o Bloco 10. Sem ataque imediato recomendado não há decisão a
tomar, e a próxima etapa vira *"ver o que fazer agora"* → `acompanhamento`.
A guarda é `bloco_10_alcancavel(snapshot)`
(`app/casos/confirmacao_ataque.py:118-126`), que `rotas_etapas.py:169` já
consulta; **nenhum limiar novo é escrito** (`RF-34`). A exceção fica documentada
no docstring da função.

## R5.2. Tech Stack — a dependência que NÃO entra

`sdd.config.md` §6 exige que dependência nova se justifique contra um requisito.
Aqui a justificativa é para **não** acrescentar `react-router`.

| Critério | Hash router próprio | `react-router` |
| --- | --- | --- |
| Dependência nova | zero | +1 (≈60 kB, mais `@remix-run/router`) |
| Fidelidade ao protótipo | transcrição de `go(id)`, ~14 linhas | traduzir as rotas para `<Route>` é uma segunda forma de escrever o mesmo |
| Foco no `<h1>`, `scrollTo`, `document.title` | escrevemos os três, uma vez | **não faz nenhum dos três** — escreveríamos o mesmo código num `useEffect` acoplado a `useLocation` |
| Rota com parâmetro (`#equipe-caso/CASO-001`) | `split('/')`, 3 linhas | parser de path completo, que não usamos |
| Loaders, lazy routes, data APIs | não temos | temos, e não usamos |

**A biblioteca não resolve o problema que temos.** O benefício real dela — um
mapa declarativo para dezenas de rotas aninhadas — não se aplica a 17 rotas que
cabem num `switch`; e as três coisas que de fato precisamos (`AC-84`: foco,
rolagem, título) ela não entrega.

O roteador próprio é `frontend/src/navegacao.ts`, com `Rota` como união
discriminada — o que torna o `switch` do `App.tsx` **exaustivo por tipo**, a
mesma trava que `fase_do_estado` tem no servidor.

> **Defeito encontrado na revisão de `T-152`, corrigido.** A primeira versão
> de `navegacao.ts` tinha um mapa `TITULO_DA_TELA` que ninguém consumia — o
> título real sempre veio da prop `titulo` que cada tela dá a `Tela.tsx`. O
> mapa era código morto **e já havia divergido**: dizia `'Meu progresso'`
> enquanto a tela passava `'Onde você está'`.
>
> Foi removido. A lição vale além deste caso: duas fontes de verdade para o
> mesmo texto não se mantêm iguais, e quem for ler escolhe a errada. A fonte
> única é `titulo`, que é **também** o texto do `<h1>` — então título da aba e
> cabeçalho não podem discordar por construção, e `AC-84` fica satisfeito sem
> ninguém ter de sincronizar nada.

### A armadilha do `pushState`

`history.pushState` **não dispara `popstate`**. O protótipo não percebe porque
re-renderiza sincronamente no `click`. No React, `irPara` precisa emitir um
`CustomEvent('piq:navegou')`, e o hook escuta **os dois** eventos. Errar isso
produz *"o botão não faz nada, mas a URL muda"* — e `AC-86` existe para que esse
bug não passe.

## R5.3. Project Structure — o que nasce e o que muda

| Caminho | O que é | Estado |
| --- | --- | --- |
| `app/casos/fases.py` | mapa `ESTADO_CASO` → `FASE_INICIO`, puro | **novo** |
| `app/http/rotas_inicio.py` | `GET /caso/{CASO_ID}/inicio` | **novo** |
| `app/casos/progresso.py` | ganha `contar_coleta` e o gerador privado compartilhado | alterado |
| `app/http/rotas_api_conta.py` | `e_revisor` no payload de login/cadastro | alterado |
| `app/http/serializacao.py` | `posicao`/`total_na_ficha` (`RF-63`) | alterado |
| `frontend/src/navegacao.ts` | hash router, tipo `Rota`, `useRota` | **novo** |
| `frontend/src/componentes/Tela.tsx` | a casca de três partes | **novo** |
| `frontend/src/telas/Tela{Inicio,Progresso,Calculando,Aguardando,Recalculo,EquipeCaso,Acao}.tsx` | as sete telas que faltam | **novas** |
| `frontend/src/telas/*` (as 10 existentes) | passam a usar `<Tela>` | alterados |
| `frontend/src/index.css` | as classes da casca | alterado |
| `frontend/tests/e2e/apoio/navegacao.ts` | helper de navegação e intercepts | **novo** |

**Arquivo próprio para `/inicio`.** `rotas_etapas.py` trata da abertura das
etapas pós-plano (Blocos 7/8/10/11) — assunto diferente. Misturar os dois faria
um arquivo que muda por duas razões. O custo é um import e um `include_router`
em `aplicacao.py` (o padrão já registrado 17 vezes, `aplicacao.py:180-203`).

## R5.4. External Interfaces — `GET /caso/{CASO_ID}/inicio`

```json
{
  "CASO_ID": "...",
  "estado": "COLETA_INICIAL",
  "fase": "coleta",
  "mensagem": "Sua coleta está em andamento.",
  "proxima_etapa": {
    "destino": "pergunta",
    "ID_PERGUNTA": "B5.B03",
    "item_id": "D003"
  },
  "progresso": { "respondidas": 62, "total": 195 },
  "valor_em_destaque": null,
  "plano_liberado": false,
  "versao_do_plano": null
}
```

> **Correção durante a implementação (T-147).** O payload acima previa
> `rotulo` e `detalhe` dentro de `proxima_etapa`. **Isso violou `AC-37`** e a
> suíte estática pegou: três das constantes passavam de 40 caracteres, e o
> teste `test_sem_conteudo_de_questionario_no_codigo.py` recusa string longa
> em `app/`.
>
> A trava estava certa, e o erro era de desenho, não de tamanho: **redação ao
> aluno não é decisão de quem escreve rota.** Texto num arquivo de rota não
> passa por revisão de conteúdo. O payload passou a mandar só
> `destino` — um enum `DESTINO_DA_ETAPA`, dado estrutural — e o texto vive em
> `TEXTO_DA_ETAPA`, em `frontend/src/telas/TelaInicio.tsx`.
>
> A divisão ficou mais limpa do que era: **o servidor decide QUAL é a próxima
> etapa** (depende do estado do caso, que só ele conhece); **a interface decide
> COMO dizer**. E `AC-88` ficou mais forte — a asserção passou de "o número não
> está no rótulo" para "não existe campo de texto onde o número pudesse entrar".

**O número nunca entra na frase.** O protótipo escreve *"Decidir sobre os
R$ 3.000,00"* no título da fase `plano`. O servidor **não** monta essa frase:
manda o `destino` e o `valor_em_destaque` como **string** separada, e o React
compõe. Dois motivos normativos: `RF-13` (dinheiro nunca atravessa `float`, e
viaja como string no JSON — a mesma disciplina de `rotas_etapas.py:236`, que
manda `str(ataque_imediato_recomendado_de(snapshot))`) e Lei nº 3 (o número é
leitura de campo do snapshot, não parte de uma frase montada no servidor).
`AC-88` verifica isso.

### Pontos de injeção

Quatro pontos novos, cada um em função própria (`obter_*_do_inicio`), no padrão
de `rotas_operador.py:84-111`, para que os testes sobrescrevam por
`app.dependency_overrides` sem precisar de `DATABASE_URL`. A regra do padrão
está escrita lá: cada módulo declara o **seu** `obter_*`, mesmo quando um
idêntico existe noutro módulo, *"para que este módulo não precise importar de
`rotas_coleta.py` só por causa de um ponto de injeção"*.

Os quatro insumos de `consultar_trilha_de_progresso` são os mesmos que
`rotas_api_plano.py:239-247` já monta — caso, registros, respostas e
`itens_por_escopo` —, só que para um `CASO_ID` da URL em vez de um laço sobre
todos os casos. **Essa rota é o template.**

> **`obter_repositorio_snapshots` vem de `rotas_plano.py:90`, nunca de
> `rotas_coleta_dirigida.py:98`.** Esse foi o defeito nº 1 corrigido em `T-145`,
> e a justificativa está escrita em `rotas_api_plano.py:94-100`: pontos de
> injeção diferentes fazem a tela e o PDF lerem de repositórios distintos num
> teste que sobrescreve só um dos dois, e *"o aluno veria um plano que o PDF não
> confirma"*. Repeti-lo aqui faria a tela Início discordar do plano que ela
> anuncia.

A rota recebe `CASO_ID` no path, então **precisa** declarar
`Depends(exigir_caso_da_sessao("CASO_ID"))` — não é boa prática, é obrigação
verificada: `tests/app_aluno/e2e/test_mecanismo_isolamento.py` enumera as
`APIRoute` registradas e reconhece o par `CASO_ID` + a subdependência de
`app.http.isolamento`. Sem isso, o teste falha no momento do registro (`AC-74`).

### `e_revisor` no login

`e_revisor` **já existe** em `persistencia/app_aluno/contas.py:81-93` (coluna com
migração `003_papel_revisor.sql`) e `exigir_papel_revisor` o consulta a cada
requisição. Esta rodada apenas o **acrescenta ao payload** de
`/api/conta/login` (hoje `{email, conta_id}`, `rotas_api_conta.py:80-96`) e de
`/api/conta/cadastro` (hoje `{email, conta_id, CASO_ID}`, `:54-77`). É campo
aditivo — os testes existentes verificam chaves específicas, não igualdade de
dict.

**Não** se guarda `e_revisor` na sessão: `app/http/sessao.py` grava só
`conta_id`, por design — `isolamento.py:186-189` é explícito de que a consulta é
*"SEMPRE contra o banco, a cada requisição"*. O campo no login serve **apenas**
para a interface decidir o que oferecer (`RF-59`, `AC-80`); a autorização
continua inteiramente no servidor. Esconder um botão não é controle de acesso, e
este plano não finge que seja.

> **Lacuna conhecida, fora do escopo desta rodada.** `POST /api/conta/login`
> **não devolve `CASO_ID`** (só o cadastro devolve), e não existe
> `GET /api/conta/eu`. Depois de um login, o cliente não tem como descobrir o
> caso pelo backend — hoje ele vem de `?caso=` na URL. `/inicio` **não** resolve
> isso, porque ela própria exige `CASO_ID` no path. Vira tarefa própria no
> backlog, não um extra silencioso nesta (`CLAUDE.md`, regra 4).

## R5.5. State Management — a casca e o contador

### `Tela.tsx`

```tsx
interface TelaProps {
  titulo: string                // vai para document.title
  voltar?: () => void           // ausente ⇒ sem "‹ Voltar" (tela Início)
  onde?: string                 // localizador à direita
  largura?: 'aluno' | 'equipe'  // 560px | 900px
  acoes?: ReactNode             // rodapé sticky
  children: ReactNode
}
```

Quatro detalhes que parecem cosméticos e não são:

1. **`<span />` vazio no `.top` quando não há voltar.** O `.top` é
   `justify-between`; sem o span o localizador migra para a esquerda. O
   protótipo faz exatamente isso (linhas 227 e 409).
2. **`mostrarTitulo={false}` exige `<h1 className="sr-only">`.** Quando a casca
   não renderiza título visível (tela de pergunta, cujo `<legend>` já é o
   título), o `<h1>` continua na árvore de acessibilidade — senão não há o que
   focar, e `AC-84` quebra. **Nunca uma tela sem `<h1>`.** Hoje `TelaPergunta` é
   exatamente esse caso: é a única tela sem `<h1>`, e os E2E a localizam pelo
   texto do enunciado.
3. **O `useEffect` da casca depende de `[titulo]`, não de `[]`.** Com `[]`,
   trocar de pergunta dentro da mesma `TelaPergunta` (componente já montado) não
   refocaria o `<h1>`, e quem usa leitor de tela continuaria ouvindo a pergunta
   anterior. `AC-84` diz "inclusive ao trocar de pergunta" por causa disso.
4. **Botão de submit fora do `<form>`.** Ao mover o botão de `TelaLogin` para a
   prop `acoes` (rodapé sticky), ele sai do `<form>` e o Enter para de
   funcionar. Resolve-se com `id="form-entrada"` no `<form>` e
   `form="form-entrada"` no botão.

### O contador `62 de 195` — `RF-62`

`pendencias_obrigatorias` devolve o que **falta**; o protótipo mostra
`respondidas / total`. A tentação é escrever uma segunda varredura — e aí barra
e retomada divergem no dia em que uma condição mudar.

A solução é um gerador privado `_ocorrencias_abertas(...)` consumido pelas duas
funções. **Mas ele precisa ser parametrizado, e isso não é detalhe.** As duas
varreduras de `progresso.py` divergem **deliberadamente** em dois eixos, e a
docstring de `_pergunta_em_branco` (`progresso.py:434-445`) documenta o porquê:

| | `pendencias_obrigatorias` | `proxima_pergunta_nao_respondida` |
| --- | --- | --- |
| elegibilidade | `_e_exigivel_agora` (exige `OBR`; `COND` só se a condição vale) | `_e_pergunta_aberta` (qualquer registro, só condição) |
| "é por item" | `Obrigatoriedade.REP in registro.obrigatoriedade` | `registro.escopo_repeticao != EscopoRepeticao.NENHUM` |
| resultado | **todas** as ocorrências | **a primeira**, e para |

O segundo eixo tem motivo registrado: os registros reais têm perguntas
repetíveis por item **condicionais sem o membro `REP`** — todo o Bloco 7
(`B7.05`..`B7.16`), o Bloco 8 e o Bloco 11 declaram `obrigatoriedade: [COND]`
com `escopo_repeticao: DIVIDA_ID`/`ACAO_ID`. A retomada precisa oferecer toda
pergunta que o aluno de fato veria por item.

> **Um `_ocorrencias_abertas` ingênuo quebra `AC-11` ou `AC-01`.** A assinatura
> tem de parametrizar **ambos** os predicados:
> `_ocorrencias_abertas(registros, respostas, itens_por_escopo, *, elegivel, e_por_item) -> Iterator[PendenciaObrigatoria]`,
> com os chamadores fazendo `tuple(...)` e `next(..., None)`. `contar_coleta`
> usa os predicados de **retomada** (`_e_pergunta_aberta` + `escopo_repeticao`),
> porque a barra conta o que o aluno vê, não o que bloqueia o avanço.

`total` conta só as perguntas **abertas agora** (condição verdadeira). O
denominador varia conforme o aluno responde, e isso é **correto**: mostrar 195
quando 80 nunca abrirão mentiria sobre o tamanho do trabalho restante. O
invariante testado é `respondidas + faltam == total` (`AC-90`).

> **O `195` do protótipo é real**, e coincide com os Blocos 1–5
> (16+15+57+49+58). Mas é o total **estático** dos registros; o `total` da rota
> é o dinâmico, e os dois só coincidem quando toda condição está aberta. A
> tela mostra o dinâmico.
>
> ⚠️ **A coleção tem 247 registros, não 245.** Várias docstrings dizem "os 245
> registros reais" (`progresso.py:51`, `:435`; `rotas_coleta.py:211`) — a
> contagem envelheceu quando `bloco-09.yaml` (2 perguntas) entrou. Nenhum teste
> novo deve afirmar `245`.

## R5.6. Testing Strategy — as fatias 4 a 7 são uma transação

**Risco concreto e datado.** `frontend/tests/e2e/coleta.spec.ts` e
`plano.spec.ts` clicam em `getByRole('button', { name: 'Coleta' | 'Dívidas' |
'Plano' })` — dependem da barra de abas que vai sumir. A barra morre no momento
em que `App.tsx` passa a usar o roteador, e os testes que dependem dela quebram
no mesmo instante.

> **São 18 blocos `test`** (10 em `coleta.spec.ts`, 8 em `plano.spec.ts`), que o
> Playwright executa em 2 projects (`desktop` e `mobile-360`) — daí os **36
> casos**. A migração mexe em 18 testes, não em 36.

> **Nenhuma das fatias de frontend é declarável concluída isoladamente.** A
> suíte E2E só volta ao verde ao final da migração dos testes. Declarar a troca
> do roteador "pronta" com os E2E vermelhos violaria a regra 5 do `CLAUDE.md`.
>
> A alternativa — manter a barra atrás de uma flag — foi **descartada**:
> deixaria dois modelos de navegação vivos no código, que é exatamente o que
> esta rodada existe para eliminar.

**A navegação é centralizada num helper**, não espalhada pelos testes:

```ts
export async function abrirTela(page: Page, caso: string, rota: string) { … }
export function acaoPrincipal(page: Page, rotulo: string) { … }
export async function interceptarBase(page: Page, caso: string, opcoes) { … }
```

Assim a **próxima** mudança de navegação é uma edição em um arquivo.

> ⚠️ **Os testes interceptam tudo com `page.route`, então o backend não precisa
> estar no ar — exceto para a rota que se esquecer de interceptar.** Se
> `TelaInicio` chamar `/caso/X/inicio` sem intercept, o proxy do Vite falha e o
> teste trava até o timeout. **Regra: todo `beforeEach` que abre uma tela
> intercepta `/inicio`, mesmo que o teste não o verifique.**

**O teste de teclado melhora com a mudança.** Hoje ele tabula até 20 vezes
*porque a barra de abas polui o caminho* — o comentário em
`coleta.spec.ts:237-238` diz isso. Sem a barra, a ordem do DOM vira `.back` →
campo → `Continuar`. O limite baixa para 5, e **o limite baixo passa a ser a
asserção**: se alguém reintroduzir navegação global antes da ação, o teste
falha.

Dois detalhes desse teste que a migração não pode quebrar: ele parte de
`campo.focus()` (não de um Tab desde o `<body>`), e compara
`document.activeElement.textContent.trim()` **por igualdade estrita** com
`'Continuar'` — o botão em estado `Salvando…` não casa.

Garantias que **não podem** se perder na migração: `AC-14`, `AC-15`, `AC-16`,
`AC-17`, `AC-25`, `AC-70`, `AC-75`, `AC-76`, `AC-78`, `EC-01`, `EC-02`, `EC-07`,
`EC-22`, `RF-52`, e navegação só por teclado.

Testes **novos** que o modelo novo exige — sem eles ele fica sem prova:

| Teste | Prova |
| --- | --- |
| `#inicio` mostra UMA próxima etapa por fase (×5, parametrizado) | `AC-81` — o contrato de `/inicio` chega à tela |
| voltar no navegador funciona | `AC-86` — `irPara` + `popstate`, a armadilha nº 1 |
| cada navegação foca o `<h1>` e atualiza o título | `AC-84` — a razão de a casca existir |
| o rodapé fica visível com o conteúdo rolado | `AC-85` — `sticky` de fato funcionando |
| conta sem papel não vê caminho para a equipe | `AC-80` |
| área da equipe usa 900px | `AC-87` |
| hash desconhecido cai em `#inicio` | `AC-91`/`EC-26` |

### Nota de ambiente — o gate sem Postgres

A Rodada 5 foi implementada numa máquina **sem Postgres local** (Docker
desligado, porta `55432` recusando conexão). O que isso significa para quem
for ler os números:

| Seleção | Antes da rodada | Depois |
| --- | --- | --- |
| suíte completa | 72 failed · 1510 passed | **72 failed** · 1597 passed |
| sem `integracao`/`regras`/`app_aluno/e2e` | — | 2 failed · 1083 passed |

**A contagem de falhas não se moveu, e as falhas são as mesmas** — verificado
por `comm` entre as duas listas, não por igualdade de total: nenhuma do
baseline desapareceu, nenhuma nova entrou. Os `+87` em `passed` são os testes
escritos nesta rodada. As duas execuções levaram ~2h38 cada, quase inteiramente
gastas esperando `connect_timeout` estourar teste a teste.

As falhas são `psycopg.errors.ConnectionTimeout` e `ErroCadastro: … connection
timeout expired`, verificadas uma a uma. Duas delas **não deveriam** depender
de banco e viraram `T-157`: `test_rotas_coleta_dirigida.py` deixa o ponto de
injeção de respostas apontando para `RepositorioRespostasSupabase`, enquanto
todo o resto do slug roda por `dependency_overrides`.

> **Por que isso importa além do ruído.** Um gate que só fica verde com Docker
> no ar ensina quem desenvolve a ignorar vermelho — e o hábito de ignorar
> vermelho é como a navegação inventada da Rodada 4 atravessou uma suíte de
> 1582 testes sem ninguém notar.

### Quatro travas de teste que a migração pode quebrar sem querer

Nenhuma delas é sobre navegação; todas quebram por efeito colateral:

1. **`test_acessibilidade_plano.py:340`** exige que
   `frontend/tests/e2e/coleta.spec.ts` **exista como arquivo**. Renomear ou
   mover o arquivo quebra um teste Python. Migre o conteúdo, mantenha o nome.
2. **`test_sem_condicional_no_javascript.py:164`** exige `mascaras.ts`,
   `tipos.ts` e **≥10 arquivos** em `frontend/src/`. Esta rodada acrescenta
   arquivos, então a trava fica mais folgada — mas ela também **proíbe a string
   `VARIAVEL_GRAVADA`** em `frontend/src/`, e ela está nos fixtures de teste.
   Não deixe vazar de um lado para o outro.
3. **`test_acessibilidade_coleta.py:127-164`** parseia `tailwind.config.js` por
   **regex linha a linha**, achatando aninhados e parando em `fontFamily:`.
   Reformatar o arquivo — ou mexer na indentação — quebra a auditoria de
   contraste. Esta rodada não precisa tocar nele.
4. **`test_css_360px.py`** recusa `width:<N>px` acima de 360 em
   `frontend/src/index.css` (com lookbehind que isenta `max-`). As classes novas
   da casca usam `padding`/`min-height`, não `width` — mas `.wide`/`max-w-equipe`
   precisa ser `max-width`, nunca `width`.

## R5.7. Traceability

| Requisito | Coberto por (seção do plano) |
| --- | --- |
| `RF-57` — fluxo linear guiado, casca de três partes | R5.1 (o desenho e a regra que a barra violava) · R5.5 (`Tela.tsx` e os quatro detalhes) · R5.6 (`AC-82`, `AC-84`, `AC-85`) |
| `RF-58` — Início com uma única próxima etapa | R5.1 (a decisão volta ao servidor) · R5.4 (o payload) · R5.6 (`AC-83`, `AC-86`) |
| `RF-59` — equipe em rota e largura próprias, escondida por papel | R5.4 (`e_revisor` no login, e por que **não** na sessão) · R5.3 · R5.6 (`AC-80`, `AC-87`) |
| `RF-60` — `GET /caso/{CASO_ID}/inicio` | R5.4 (payload, pontos de injeção, o defeito nº 1 de `T-145`, a obrigação de isolamento) · R5.6 (`AC-81`, `AC-88`) |
| `RF-61` — 12 estados em 5 fases, `match` exaustivo | R5.1 (a tabela completa, as duas tentações recusadas, a exceção de `PLANO_LIBERADO`) · R5.3 (`app/casos/fases.py`) · R5.6 (`AC-89`, `EC-25`) |
| `RF-62` — `respondidas`/`total` sem segunda varredura | R5.5 (o gerador **parametrizado** e por que `total` varia) · R5.6 (`AC-90`) |
| `RF-63` — `posicao`/`total_na_ficha` no payload de pergunta | R5.3 (`serializacao.py`) · R5.6 (`AC-92`) |

> **Os sete requisitos da Rodada 5 (`RF-57`–`RF-63`) têm cobertura.** Nenhum
> depende de insumo externo: `OQ-30`, que bloqueava o localizador, foi
> **respondida em 2026-09-17** e virou `RF-63`.

## R6.1. Architecture Overview — orientação, não navegação

A Rodada 5 acertou a **navegação** (uma tela por vez, uma próxima etapa) e
errou a **orientação**. São coisas diferentes, e o teste com usuário mostrou a
diferença em uma frase: *"me senti perdido, sem saber o que é, qual o
objetivo"*.

| | Rodada 5 | Rodada 6 |
| --- | --- | --- |
| pergunta que responde | *o que eu faço agora?* | *onde eu estou, e onde isso vai dar?* |
| mecanismo | uma próxima etapa (`RF-58`) | a jornada inteira, com a posição marcada (`RF-64`) |
| erro que corrige | parede de sete abas | um passo sem mapa |

**As duas são necessárias, e nenhuma substitui a outra.** Oferecer a jornada
inteira como opções clicáveis seria voltar à barra de abas; oferecer só o passo
seguinte é o que produziu o relato acima. A trilha é **informativa, não
navegável**: ela diz onde o aluno está, e o único botão continua sendo o da
próxima etapa.

## R6.2. Data Flow — nenhum campo novo

`GET /caso/{CASO_ID}/inicio` já devolvia tudo:

- `fase` → qual das cinco etapas está em curso (`RF-61` fez esse mapa);
- `progresso.respondidas`/`total` → o que falta na etapa de coleta.

Verificado **contra a API real** antes de escrever interface. Não há rota nova,
nem campo novo, nem migração: a Rodada 6 é inteiramente de apresentação, e isso
é o sinal de que o contrato de `/inicio` estava certo.

**`localStorage` foi recusado** (`RF-67`, `AC-99`). O gatilho das boas-vindas é
`progresso.respondidas === 0`, estado do caso — não uma marca no navegador.
Quem começa no computador e segue no celular não pode ver a apresentação de
novo, nem perdê-la por ter trocado de aparelho. `RF-10` (retomada em qualquer
dispositivo) é requisito, e uma marca local o violaria em silêncio.

## R6.3. O número precisa de unidade

"3 de 101" é correto e não informa: **101 do quê?** Para quem está endividado,
um total sem unidade lido no meio de perguntas sobre dinheiro soa como
formulário sem fim — e é aí que a pessoa abandona.

`RF-65` fixa o comportamento: a etapa em curso diz o que falta **com a
unidade** e na linguagem do aluno — *"Faltam 98 perguntas"*, *"A espera é com a
equipe"*, *"Há uma decisão sua para tomar"*.

A barra de progresso do Início **saiu** junto. Ela mostrava o mesmo número com
outra redação, e dois lugares dizendo a mesma coisa de formas diferentes era
parte da confusão. Quem conta agora é a trilha, dentro da etapa a que o número
pertence.

## R6.4. Um defeito de layout que só a fotografia revelou

Com a trilha, o Início passou a ser mais alto que a janela — e o rodapé
`sticky` **sobrepôs** o cartão da próxima etapa, letras somadas, ilegível.
Nenhum dos 66 E2E pegou: todos afirmam presença e texto, nenhum compara
posições.

Duas causas, ambas minhas:

1. **`min-h-screen` no wrapper, não na coluna.** O protótipo põe a altura na
   `.screen` (linha 73). Com a coluna encolhida ao conteúdo, o `flex-1` do
   `.corpo` não tinha o que esticar, e o rodapé grudava no fim do conteúdo
   curto.
2. **`.acoes` sem empilhamento declarado.** Elemento `sticky` flutua sobre o
   que ainda não rolou — é assim que funciona. Sem `z-index` e fundo opaco, o
   texto de trás atravessa.

Corrigido com `min-h-screen` na coluna, `z-10` no rodapé, e
`scroll-padding-bottom` no `.corpo` para que o foco por teclado não pare
**debaixo** do rodapé — que é a versão invisível do mesmo problema, e a que
atinge quem navega sem mouse.

> **A lição é de método, não de CSS.** `AC-85` já exigia "o rodapé fica visível
> com o conteúdo rolado", e o teste que o prova mede `viewport ratio` do
> rodapé — ele estava verde com a tela quebrada, porque o rodapé **estava**
> visível: era o conteúdo que sumia atrás dele. Asserção de presença não
> substitui olhar a tela.

## R6.5. Traceability

| Requisito | Coberto por |
| --- | --- |
| `RF-64` — a jornada em cinco etapas, sempre visível | R6.1 · `TrilhaDaJornada.tsx` · `AC-93`, `AC-94`, `AC-95` |
| `RF-65` — o que falta, com unidade | R6.3 · `oQueFalta()` · `AC-96` |
| `RF-66` — boas-vindas na primeira vez | `TelaBoasVindas.tsx` · `App.tsx` (gatilho por `respondidas === 0`) · `AC-97`, `AC-98` |
| `RF-67` — deriva do servidor, nunca do cliente | R6.2 (por que `localStorage` foi recusado) · `AC-99` |

---

# Rodada 8 (2026-09-19) — acabamento visual

> **Rastreia:** `RF-72` a `RF-78` · `AC-107` a `AC-116` · `US-25`
>
> **Nota de rastreabilidade.** Este plano ia da Rodada 6 direto às tarefas
> `T-160`/`T-161`: `RF-68`–`RF-71` e `AC-100`–`AC-106` (Rodada 7) nunca tiveram
> seção de plano. A lacuna é registrada aqui, e não é fechada por esta rodada —
> aquelas tarefas já estão concluídas, e escrever plano retroativo para código
> entregue seria documentação de fachada. Fica como dívida conhecida.

## R8.1. Architecture Overview — uma camada, não um redesenho

O problema não é que o design esteja errado; é que ele nunca descreveu
profundidade. `RF-50` fixou **tokens, tipografia e componentes** — e uma
interface montada só com isso sai plana, porque nada nela diz onde está a
sombra, qual número é o grande, ou o que acontece quando o cursor passa por
cima.

A estratégia, portanto, é **uma camada de acabamento sobre o sistema
existente**, nunca um segundo sistema:

```text
┌─ tokens validados (RF-50) ─────────────┐  cores, fontes, toque  ← INTOCADO
├─ camada de acabamento (RF-72…RF-77) ───┤  elevação, escala,     ← NOVO
│                                        │  ícones, esqueleto,
│                                        │  micro-interação
└─ casca e classes (RF-57, AC-82) ───────┘  .top/.corpo/.acoes    ← INTOCADO
```

**Por que aditivo e não substitutivo.** Três razões, em ordem de força:

1. **Os tokens são auditados por contraste.** `test_acessibilidade_coleta.py`
   recalcula WCAG 2.1 AA sobre sete pares lidos por regex de
   `tailwind.config.js`. Renomear um token faz o teste falhar com erro
   explícito (`:167-176`); clarear um texto ou escurecer um fundo o faz falhar
   por contraste. A camada nova só acrescenta **sombra, espaço e escala** —
   nenhum par de cor muda.
2. **Os nomes de classe são contrato de teste.** `.acoes`, `.corpo`, `.top`,
   `button.back`, `.linha span`, `.cartao-proximo` aparecem como seletor em
   dezenas de E2E (`tests/e2e/apoio/navegacao.ts:161-166`). São API, não
   detalhe interno.
3. **O protótipo foi validado com stakeholders.** Substituir o desenho
   descartaria uma validação que custou uma rodada de usuário; acrescentar
   acabamento não.

## R8.2. Tech Stack — nenhuma dependência nova

| Decisão | Justificativa contra requisito |
| --- | --- |
| **Sem biblioteca de ícones** | `RF-74` pede vocabulário do PIQ (dívida, prazo, conferência, reserva). Nenhum pacote traz isso, e trazer centenas de ícones para usar oito pesa no carregamento de quem está em rede instável (persona). SVG inline, desenhado aqui. |
| **Sem biblioteca de animação** | `RF-76` pede `hover`/`active` e `RF-75` um brilho de esqueleto. CSS resolve os dois; uma lib custaria dezenas de kB para isso. |
| **Sem alteração no `tailwind.config.js`** | `AC-107`. As adições entram como `@layer components` em `index.css` e classes arbitrárias no TSX — o mesmo caminho que `T-161` já usou com sucesso. |
| **Elevação em CSS custom properties** | Três níveis (`--e1/--e2/--e3`) declarados uma vez em `index.css`. `AC-108` exige derivação de `ink`, e uma variável torna isso auditável por regex. |

## R8.3. Project Structure — o que nasce e o que muda

| Caminho | Mudança |
| --- | --- |
| `frontend/src/index.css` | **ALTERADO.** Escala de elevação, hierarquia tipográfica, `.cartao-destaque`, `.trilha`, `.sk` (esqueleto), estados de `hover`/`active`. Tudo em `@layer components`, aditivo. |
| `frontend/src/componentes/Icone.tsx` | **NOVO.** Um componente, um `Record` de paths SVG. Sempre `aria-hidden` (`AC-110`) — a prop de rótulo nem existe, para que seja impossível usá-lo como portador de significado. |
| `frontend/src/componentes/Esqueleto.tsx` | **NOVO.** As formas de carregamento (`AC-112`), com o `role="status"` embutido para que nenhuma tela o esqueça. |
| `frontend/src/componentes/TrilhaDaJornada.tsx` | **ALTERADO.** Trilho e marcas (`RF-77`). A estrutura `<li>` + `.linha span` permanece — `navegacao.spec.ts:801` a usa como seletor. |
| `frontend/src/telas/TelaPlano.tsx` | **ALTERADO.** Resumo (prazo/custo) sobe para antes da ordem (`AC-109`). |
| `frontend/src/telas/*.tsx` (13 telas) | **ALTERADO.** `<p>Carregando…</p>` vira `<Esqueleto/>`. |
| `frontend/public/icons.svg` | **REMOVIDO.** `AC-111` — boilerplate do Vite, sem referência. |
| `frontend/README.md` | **ALTERADO.** Ainda é o README do template do Vite. |

## R8.4. A decisão que exige cuidado: ícone dentro de botão

`AC-114` guarda a trava mais rígida do projeto — do campo até "Continuar", no
máximo 2 Tabs, e `coleta.spec.ts:285` compara o nome acessível do botão por
**igualdade estrita**.

Pôr um `<svg>` dentro do `<button>` é seguro **apenas** com `aria-hidden="true"`
no SVG: sem ele, alguns leitores compõem o nome acessível com o conteúdo do
`<title>`/`<desc>` e a igualdade estrita quebra. O SVG também nunca recebe
`focusable="true"` — em motores legados o padrão é focável, e isso
acrescentaria uma parada de Tab.

> **Regra desta rodada:** todo `<svg>` nasce com `aria-hidden="true"` e sem
> `<title>`. `Icone.tsx` os emite assim por construção, e não expõe prop que
> permita o contrário.

## R8.5. Error Handling Strategy — o esqueleto não pode esconder o erro

O esqueleto substitui o estado de **carregamento**, nunca o de **erro**. As
telas hoje têm três estados (`carregando`, `erro`, dados) e continuam com os
três: `aviso-erro` com `role="alert"` permanece como está.

Um esqueleto que continua girando quando a requisição falhou é pior que o texto
que substituiu — por isso a troca é feita **apenas** no ramo `if (carregando)`,
e nunca no ramo de erro.

## R8.6. Testing Strategy

| Critério | Como é provado |
| --- | --- |
| `AC-107` (tokens intactos) | `tests/app_aluno/estatica/test_tokens_intactos.py` — **NOVO**: compara os 11 tokens, `fontFamily`, `minHeight`, `maxWidth` com os valores literais desta rodada |
| `AC-108` (elevação de `ink`) | Mesmo arquivo: regex que exige `rgba(27,42,47` nas variáveis de elevação e proíbe `rgba(0,0,0` em `index.css` |
| `AC-110`, `AC-111` (ícones) | `tests/app_aluno/estatica/test_iconografia.py` — **NOVO**: todo `<svg` no `src/` tem `aria-hidden`; `public/icons.svg` não existe |
| `AC-112`, `AC-113` (esqueleto) | `frontend/tests/unit/componentes/Esqueleto.test.tsx` — **NOVO**: `aria-hidden` no esqueleto, `role="status"` presente |
| `AC-114` (2 Tabs, nome exato) | `frontend/tests/e2e/coleta.spec.ts` — **JÁ EXISTE**, roda sem edição |
| `AC-115` (trilha não navegável) | `frontend/tests/e2e/navegacao.spec.ts` — **NOVO teste**: nenhum `button`/`a` dentro da trilha |
| `AC-116` (classes preservadas) | A suíte E2E inteira — se uma classe sumir, dezenas de testes quebram |
| `AC-109` (resumo antes da ordem) | `frontend/tests/e2e/plano.spec.ts` — **NOVO teste**: posição vertical do resumo menor que a da ordem |

**Os gates da seção 2 do `sdd.config.md` rodam ao fim de cada tarefa**, e a
suíte E2E existente é o guarda-costas desta rodada: ela já prova que nada
estrutural mudou.

## R8.7. Risks & Trade-offs

| Risco | Mitigação |
| --- | --- |
| **Elevação vira ruído** se aplicada a tudo | `RF-72` exige elevação **por papel**. `.cartao` fica no nível mais baixo (quase nada); só `.cartao-destaque` recebe o mais alto. Se tudo flutua, nada se destaca. |
| **O filete de acento do `.cartao-destaque` compete com a borda de 2px do `.cartao-proximo`** | São a mesma ideia em telas diferentes: o `.cartao-proximo` é o do Início (`RF-58`), o `.cartao-destaque` é o do plano. Nunca aparecem juntos na mesma tela. |
| **`color-mix()` não tem suporte universal** | Toda regra que usa `color-mix` é precedida da cor sólida equivalente. Navegador antigo perde a nuance, não a legibilidade. |
| **Esqueleto que não corresponde ao conteúdo** faz a tela saltar | O esqueleto é escrito por tela, com a forma do que aquela tela carrega — não um retângulo genérico. |
| **A repaginação não foi validada com stakeholders**, diferente do protótipo original | Registrado em `OQ-32`. O protótipo desta rodada foi aprovado pelo especialista (2026-09-19); validação com aluno real fica para o piloto. |

## R8.8. Traceability

| Requisito | Coberto por |
| --- | --- |
| `RF-72` — elevação por papel | R8.1 · `index.css` (variáveis de elevação) · `AC-108` |
| `RF-73` — hierarquia tipográfica e tabular-nums | R8.3 · `TelaPlano.tsx` · `AC-109` |
| `RF-74` — iconografia própria, nunca focável | R8.4 · `Icone.tsx` · `AC-110`, `AC-111` |
| `RF-75` — esqueleto no lugar de "Carregando…" | R8.5 · `Esqueleto.tsx` · `AC-112` |
| `RF-76` — resposta ao apontador | R8.1 · `index.css` · `AC-113` (movimento reduzido) |
| `RF-77` — trilha com trilho, ainda informativa | R8.3 · `TrilhaDaJornada.tsx` · `AC-115` |
| `RF-78` — nada validado é alterado | R8.1 (as três razões) · `AC-107`, `AC-114`, `AC-116` |
