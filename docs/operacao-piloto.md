# Procedimento operacional do piloto — keep-alive do banco

| Campo    | Valor                                                                    |
| -------- | ------------------------------------------------------------------------- |
| Slug     | `app-aluno`                                                                |
| Tarefa   | `T-94` — Implementar o keep-alive do banco durante a janela do piloto      |
| Rastreia | `RF-10`, `EC-05`                                                           |
| Origem   | `plans/app-aluno.plan.md` §6 ("Risco operacional do free tier") e §10 ("Aceitar Supabase free tier no piloto") |

## O risco, em uma frase

O Supabase free tier usado nesta feature **pausa após ~7 dias sem
atividade** (`plans/app-aluno.plan.md` §6). Com 1 a 3 alunos em série
(`OQ-06`), semanas podem se passar entre um acesso e outro — a pausa por
inatividade é o modo de falha **esperado** do piloto, não uma hipótese
remota. Este documento cobre como reduzir a frequência com que ela ocorre
(keep-alive) e o que já acontece quando, mesmo assim, ela ocorre (`EC-05`).

## O que o keep-alive faz, e o que ele não faz

`GET /saude/banco` (`app/http/saude.py`) executa uma única query mínima
(`SELECT 1`, sem tabela nenhuma) contra o banco e devolve `200` se a conexão
respondeu, `503` caso contrário. Ele:

- **não lê nem grava nenhuma tabela de dado do aluno** (`contas`, `casos`,
  `respostas`, `itens_repetidos`, `revisoes`, `consentimentos`,
  `eventos_caso`) — critério de aceite desta tarefa;
- **não é a rota `/saude`** (`app/http/aplicacao.py`, T-29): aquela é uma
  sonda de vida do processo (liveness), sem tocar banco; esta é uma sonda de
  prontidão do banco (readiness), que existe só para ser chamada
  periodicamente pelo agendador externo abaixo;
- **não substitui o tratamento de erro de gravação de resposta** (`EC-05`,
  já implementado em `app/http/rotas_coleta.py`, T-42) — ele só reduz a
  FREQUÊNCIA com que o aluno chega a encontrar aquele erro, ao manter o
  projeto Supabase fora da janela de inatividade.

## Como agendar o keep-alive

Este projeto **não** introduz uma dependência de agendamento em processo
(`apscheduler` ou similar) — o extra `app` do `pyproject.toml` já está
fechado (`fastapi`, `uvicorn`, `argon2-cffi`, `jinja2`), e um agendador
embutido exigiria o processo ASGI rodando continuamente, o que o piloto (1 a
3 alunos em série) não justifica. O keep-alive é, em vez disso, um endpoint
comum, chamado periodicamente por um agendador **externo** ao processo:

- **GitHub Actions** (`schedule` com sintaxe cron), se o repositório já
  estiver hospedado lá — sem infraestrutura adicional a manter. Um job
  mínimo chama `curl -f https://<host-do-piloto>/saude/banco` e falha
  (notificando por e-mail/Actions UI) se a resposta não for `200`.
- **Cron** de qualquer host que já esteja de pé (o próprio host da
  aplicação, se for um VM/container de longa duração), com o mesmo `curl`.
- Qualquer serviço de "uptime monitoring" gratuito que faça requisições
  HTTP periódicas e alerte em caso de falha (ex.: UptimeRobot, cron-job.org)
  também serve — o endpoint já devolve o código HTTP correto (`200`/`503`)
  para esse tipo de ferramenta.

**Frequência sugerida: a cada 3 a 5 dias.** O limite documentado do free
tier é "~7 dias sem atividade" — uma frequência de 3 a 5 dias dá margem
folgada (o dobro ou mais do necessário) para variações de horário do
agendador, sem gerar tráfego desnecessário contra um banco que só serve 1 a
3 alunos. Não há necessidade de rodar de hora em hora nem diariamente: isso
não reduz o risco (o limite é de dias, não de horas) e só aumenta o número
de execuções a monitorar.

## O que o aluno vê quando o banco está indisponível mesmo assim

Keep-alive reduz a frequência da pausa por inatividade, mas não a elimina
por completo (o agendador pode falhar, o Supabase pode ter uma
indisponibilidade não relacionada a pausa, etc.). Quando a gravação de uma
resposta falha, o comportamento já implementado (`EC-05`,
`app/http/rotas_coleta.py`, T-42) é:

1. a resposta **não é gravada** — nenhuma transação é confirmada;
2. o aluno vê a mensagem "Não foi possível salvar.", anunciada como alerta
   (`role="alert"`, na tela React de coleta — `frontend/src/telas/
   TelaPergunta.tsx` e as outras telas que gravam resposta) — nunca uma
   confirmação falsa de que a resposta foi salva;
3. o aluno pode **repetir** a mesma resposta assim que o banco voltar (o
   Supabase "acorda" em segundos a um minuto após a primeira requisição que
   o alcança) — nada do que ele já tinha respondido **antes** desse
   incidente é perdido, porque cada resposta anterior já foi commitada no
   momento em que foi dada (`AC-02`).

Este é o mesmo comportamento por trás da frase "o sistema está
reconectando, sua última resposta foi salva" citada no plano (§6): ela
descreve a experiência de retomar o sistema depois de uma pausa — o que já
estava salvo continua salvo, e é só a tentativa em curso que precisa ser
repetida. Não há duas mensagens conflitantes no código: a tela de erro da
resposta que falhou agora é honesta e pontual ("Não foi possível salvar.");
o que essa tela nunca faz é reportar como salva uma resposta que não foi.

## Antes de abrir o piloto: reavaliar o tier

`plans/app-aluno.plan.md` §10 já registra esta troca explicitamente:
**aceitar o free tier no piloto** (em vez de contratar um tier pago desde
já) foi uma decisão deliberada, justificada por `OQ-06` — 1 a 3 alunos em
série não justificam o custo de um tier pago antes de validar o método. O
risco assumido nessa troca é exatamente o desta tarefa: "pausa por
inatividade é o modo de falha esperado, não hipotético".

**Recomendação explícita desta tarefa, antes de abrir o piloto real:**
reavaliar se o free tier ainda é a escolha certa, à luz de como o piloto
efetivamente vai rodar (quantos alunos, com que espaçamento entre acessos,
se o keep-alive agendado está de fato ativo e sendo monitorado). Se o
volume ou a criticidade do piloto crescer além do que `OQ-06` presumiu, o
tier pago do Supabase remove o modo de falha inteiro (sem pausa por
inatividade) — o keep-alive deste documento é a mitigação de curto prazo, o
tier pago é a solução estrutural.

## Verificação manual do endpoint

```
curl -i https://<host-do-piloto>/saude/banco
```

- `200 {"status": "ok"}` — banco acessível, keep-alive funcionando.
- `503 {"status": "erro", "detalhe": "banco indisponível"}` — banco pausado
  ou inacessível no momento da chamada; repetir em alguns instantes (o
  Supabase leva segundos a um minuto para "acordar" após a primeira
  requisição).
