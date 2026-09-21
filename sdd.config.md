# SDD Config — Configuração do Projeto

> **Este é o ÚNICO arquivo que você precisa preencher ao usar o kit SDD em um
> projeto novo.** Todos os agentes e comandos leem daqui. Nada de específico do
> projeto deve viver dentro de `.claude/agents/` ou `.claude/commands/`.

**Não preencha na mão.** Rode `/sdd:config` — ele pergunta e escreve por você.
Rodar de novo atualiza só o que você quiser mudar.

> **Onde fica a stack?** No plano técnico, não aqui. Linguagem, framework,
> banco e bibliotecas são decisões de refinamento técnico e vivem na seção
> `Tech Stack` do plano da feature, em `plans/`, onde cada escolha é justificada
> contra um requisito. Este arquivo guarda apenas o que vale para o projeto
> inteiro, independentemente da feature.

Deixe `—` no que não se aplica ou no que ainda não foi decidido.

---

## 1. Identidade

| Campo             | Valor                                                                                                          |
| ----------------- | -------------------------------------------------------------------------------------------------------------- |
| **Projeto**       | PIQ                                                                                                              |
| **Descrição**     | Motor de cálculo, questionário e relatório que produzem um plano de quitação de dívidas personalizado para servidores públicos endividados. |
| **Repositório**   | `c:\Especialistas\especialista-rodrigo\piq` — local, ainda sem controle de versão                               |
| **Estágio**       | `greenfield`                                                                                                     |

## 2. Comandos de verificação

Os agentes rodam estes comandos antes de declarar qualquer tarefa concluída.
Se um comando ainda não existe, escreva `—` e ele será pulado.

> Em projeto novo, é normal esta seção nascer toda `—`: os comandos só existem
> depois que o primeiro plano define a stack. Rode `/sdd:config` de novo para
> preenchê-los quando existirem.

```yaml
install: uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
lint:    .venv/Scripts/python.exe -m ruff check .
build:   .venv/Scripts/python.exe -m mypy $(for d in engine persistencia collection app report tests; do [ -d "$d" ] && printf "%s " "$d"; done)
test:    .venv/Scripts/python.exe -m pytest -q ; test $? -eq 0 -o $? -eq 5
e2e:     —
run:     —
```

> **Nota de ambiente.** `pip install` puro falha neste ambiente (SSL corporativo
> intercepta `files.pythonhosted.org` com certificado self-signed); `uv`
> contorna o problema com sua própria stack TLS e é o instalador usado em
> `install`. `.venv/` é o ambiente virtual do projeto, criado com
> `python -m venv .venv`. Não há passo de compilação binária em Python puro —
> `build` é a checagem de tipos (`mypy --strict`), que cumpre o mesmo papel de
> portão de qualidade. Em `test`, exit code `5` do pytest ("no tests collected")
> é aceito além do `0`: é esperado enquanto a Entrega 1 do backlog ainda não
> escreveu testes (a partir de `T-09`/`T-11` a coleta deixa de ser vazia).
>
> **`build` filtra pastas ausentes (`T-02`).** `[tool.mypy] files` no
> `pyproject.toml` já lista as seis pastas de destino (`engine persistencia
> collection app report tests`), mas `mypy` não tolera, em nenhuma forma
> testada (`files`, `packages`, `--explicit-package-bases`), uma entrada cujo
> caminho ainda não existe: com uma pasta ausente ele falha com
> `Cannot read file`; com mais de uma, cai num fallback ambíguo e reporta
> `Duplicate module named "__main__"`. Como `collection/`, `app/` e `report/`
> só nascem em `T-04` e tarefas seguintes, o comando `build` da CLI monta a
> lista de pastas a checar filtrando em tempo de execução (`[ -d "$d" ]`) as
> que já existem no disco — sem precisar editar este comando de novo quando
> as pastas forem criadas.

## 3. Estrutura de pastas

<!-- Derivada da ordem de construção da seção 15.3 da spec canônica:
     parâmetros → motor → coleta → relatório. As pastas existem como destino
     desde já, mesmo que só a primeira seja preenchida agora. -->

| Caminho        | Responsabilidade                                                              |
| -------------- | ----------------------------------------------------------------------------- |
| `parameters/`  | Os 45 parâmetros ajustáveis da seção 8, fora do código                        |
| `engine/`      | Motor de cálculo: ciclo mensal, ranqueamento e os três métodos                |
| `persistencia/`| Adaptadores de banco e arquivo (leitura de parâmetros, snapshots), fora de `engine/` |
| `collection/`  | Questionário das 291 perguntas, gerado a partir dos registros da seção 11     |
| `report/`      | Geração do relatório a partir de `SnapshotOrdem`, com templates do plano e fila de revisão humana |
| `app/`         | Camada de aplicação: sessão, autenticação, máquina de estados do caso, montagem do estado a partir das respostas e invocação do motor |
| `tests/`       | Gabaritos numéricos, invariantes e testes das regras da seção 9               |
| `specs/`       | Especificações — artefato SDD                                                 |
| `plans/`       | Planos técnicos, incluindo a decisão de stack — artefato SDD                  |
| `tasks/`       | Backlogs `T-NN` — artefato SDD                                                |

<!-- Divergência declarada em plans/motor-calculo.plan.md §3 (T-02): adaptadores
     de banco e arquivo vivem em `persistencia/`, fora de `engine/`, para que o
     motor continue executável sem processo externo. `engine/` NÃO importa nada
     de `persistencia/`, de driver de banco nem de sistema de arquivos — a
     pureza do motor (função pura, sem I/O) depende disso e é verificada em
     teste estático (`tests/estatica/`). -->

<!-- Divergência declarada em plans/app-aluno.plan.md §3 (T-01): `app/` não é
     `collection/` nem `report/` — se a camada de aplicação (sessão,
     autenticação, máquina de estados do caso, montagem do estado, invocação do
     motor) entrasse em `collection/`, o Bloco 11 (que não é questionário
     inicial) e a fila de revisão ficariam presos no módulo errado; se fosse
     duplicada nos dois, haveria duas máquinas de estado. `app/`, `collection/`
     e `report/` importam de `engine/` e de `persistencia/`; a recíproca nunca
     ocorre — nada em `engine/` ou `persistencia/` importa de `app/`,
     `collection/` ou `report/`. -->

## 4. Convenções de código

<!-- Regras que o Code Agent deve seguir. Todas derivadas de TRAVAs e regras
     normativas da spec canônica — dá para apontar a linha que as viola. -->

- **Zero parâmetro no código.** Nenhum dos 45 valores `P_*` da seção 8 pode ser
  escrito no código; o motor os lê em tempo de execução a partir de
  `parameters/`. "Calibrável" não autoriza o desenvolvedor a alterar.
- **Precisão interna integral.** Todo cálculo mantém precisão decimal integral;
  arredondamento existe apenas na camada de exibição (regra `G-01`).
- **Regra citada no código.** Cada unidade que implementa uma regra do motor cita
  seu ID normativo (`M-01`, `R-01`, `A-03`, `F-02`, `O-01`, `H-04`, `S-03`,
  `Q-02`, `V-01`, `T-01`, `G-01`) no nome ou em comentário.
- **Carimbo de versão em toda saída.** Todo resultado emitido pelo motor carrega
  `ENGINE_VERSION` e `PARAMETROS_VERSION` (regra `V-03`).
- **Não inventar dado.** Valor desconhecido vira `INFORMACAO_PENDENTE` e bloqueia
  o que depende dele — nunca uma estimativa silenciosa (gabarito `GAB-03`).
- **Snapshot imutável.** Ordem e estado nunca são sobrescritos: quitação
  confirmada ou evento material cria um novo snapshot, preservando o anterior
  com data, motivo e justificativas (regra `V-01`).

## 5. Convenções de teste

- **Gabaritos e invariantes são suíte obrigatória.** `GAB-A`, `GAB-B` e `GAB-C`
  (numéricos ponta a ponta) mais `GAB-01` a `GAB-05` (invariantes) existem como
  testes automatizados. A seção 10 define que a engine só é aprovada quando os
  reproduz.
- **Duas tolerâncias, nunca uma só.** `± R$ 0,05` apenas em valores monetários
  acumulados. Tolerância **zero** para método recomendado, ordem, gates, status,
  número de meses, primeira vitória, `D*`, aplicação de resíduo, gatilho de
  recálculo e `NAO_APLICAVEL` versus `PROVISORIO`.
- **Todo teste rastreia para um ID.** Cada teste aponta para um critério de
  aceite `AC-NN` ou para uma regra normativa da seção 9. Teste sem âncora não
  entra.
- **Comportamento observável, nunca implementação.** Testar as saídas do motor —
  ordem, custo, prazo, status, método recomendado — e não suas funções internas.

## 6. Restrições e não-objetivos

<!-- O que o projeto explicitamente NÃO faz / não pode fazer. É o que impede o
     agente de "resolver" um problema que você decidiu não ter. -->

- **Metodologia não se decide implementando.** Nenhuma decisão registrada na spec
  canônica fica a critério do desenvolvedor. Qualquer alteração exige nova versão
  formal da especificação. Encontrou uma regra que parece errada? Reporte, não
  corrija.
- **Questionário é gerado, não codificado.** A interface das 291 perguntas é
  renderizada a partir dos registros da seção 11; uma nova versão do questionário
  deve ser edição de registro, não reescrita de código. IDs de pergunta são
  estáveis e nunca reaproveitados.
- **Google Forms puro está descartado** como plataforma de coleta: 115 das 291
  perguntas são repetíveis por item, há condicional composta entre blocos, texto
  dinâmico e validação entre campos (seção 15.1).
- **Revisão humana obrigatória no piloto.** 100% dos relatórios são revisados por
  uma pessoa antes do envio. O sistema não entrega plano direto ao usuário final
  nesta fase.

## 7. Idioma

- **Documentação, specs, comentários narrativos:** `pt-BR`
- **Identificadores, nomes de arquivo, termos técnicos:** `pt-BR`

> **Decisão deliberada, contrária ao padrão do kit.** As 270 variáveis da spec
> canônica já são nomeadas em português (`CAPACIDADE_ATAQUE_ATUAL`,
> `DIVIDA_ALVO_ATUAL`, `RESIDUO_ATAQUE_M`). Traduzir os identificadores criaria
> um dicionário mental permanente entre a spec e o código, e é justamente essa
> distância que faz uma regra se perder na implementação. O nome no código deve
> ser o nome na especificação, caractere por caractere.

## 8. Definition of Done

Uma entrega só está pronta quando **todas** forem verdadeiras:

- [ ] Existe spec, plano e tarefa cobrindo a mudança
- [ ] Todos os critérios de aceite da tarefa foram verificados
- [ ] Comandos da seção 2 passam
- [ ] Testes correspondentes existem e passam
- [ ] Sem regressão nos artefatos SDD (spec/plan/tasks atualizados se mudaram)
