# Postgres local para a suíte completa

Sem `DATABASE_URL`, 63 testes marcados `requer_banco` são **pulados** — não
falham, mas também não provam nada sobre persistência, isolamento por caso,
consentimento ou imutabilidade de snapshot. Este documento sobe um Postgres
descartável que destrava esses 63.

> **Não é ambiente de produção nem de piloto.** É um container efêmero, com
> senha de desenvolvimento em texto claro neste arquivo. Nada de dado real de
> pessoa entra aqui — o piloto continua bloqueado por `PEND-01` (textos de
> consentimento/LGPD), que é insumo jurídico, não configuração de banco.

## 1. Subir o container

```bash
docker run -d --name piq-postgres \
  -e POSTGRES_PASSWORD=piq_local_dev \
  -e POSTGRES_DB=piq \
  -p 55432:5432 \
  postgres:16
```

Porta **55432** de propósito: não colide com um Postgres já instalado na
máquina em 5432.

> **Se `docker run` recusar a porta no Windows.** A mensagem é
> `bind: An attempt was made to access a socket in a way forbidden by its
> access permissions` — e não é falta de privilégio: o Windows reserva faixas
> inteiras de porta para o Hyper-V/WSL, e `55432` cai dentro de uma delas
> nesta máquina (`55407–55506`). Conferir com:
>
> ```powershell
> netsh interface ipv4 show excludedportrange protocol=tcp
> ```
>
> Escolha uma porta fora das faixas listadas (aqui usamos **15432**) e troque
> os dois lugares: o `-p` do `docker run` e a `DATABASE_URL`. O container não
> precisa ser recriado do zero — um `docker run` novo apontando para o mesmo
> volume preserva os dados:
>
> ```bash
> docker inspect piq-postgres --format '{{json .Mounts}}'   # descobre o volume
> docker rm -f piq-postgres
> MSYS_NO_PATHCONV=1 docker run -d --name piq-postgres \
>   -e POSTGRES_PASSWORD=piq_local_dev -e POSTGRES_DB=piq \
>   -p 15432:5432 -v <VOLUME>:/var/lib/postgresql/data postgres:16
> ```
>
> `MSYS_NO_PATHCONV=1` é necessário no Git Bash: sem ele o shell converte
> `/var/lib/...` para um caminho do Windows e o Docker recusa o mount.

Esperar ficar pronto:

```bash
docker exec piq-postgres pg_isready -U postgres -d piq
```

## 2. Aplicar as migrações, nesta ordem

```bash
for m in 001_inicial 002_app_aluno 003_papel_revisor; do
  docker exec -i piq-postgres psql -U postgres -d piq -v ON_ERROR_STOP=1 \
    < "persistencia/supabase/migracoes/$m.sql"
done
```

Resultado esperado: schema `app_aluno` com 7 tabelas e `motor_calculo` com 2.

## 3. Semear os parâmetros

As migrações criam `motor_calculo.parametros` **vazia** — são só DDL, por
decisão registrada em `001_inicial.sql`. Quatro testes de paridade comparam a
linha do Postgres campo a campo com `parameters/parametros-1.0.1.json`, então
sem a linha eles falham.

A semeadura sai **do próprio arquivo canônico**, nunca digitada à mão: são 44
colunas, e digitar parâmetro de motor de cálculo à mão é como um número errado
entra num plano de quitação sem ninguém notar.

```bash
DATABASE_URL="postgresql://postgres:piq_local_dev@127.0.0.1:55432/piq" \
  .venv/Scripts/python.exe scripts/semear_parametros.py
```

## 4. Rodar a suíte

```bash
export DATABASE_URL="postgresql://postgres:piq_local_dev@127.0.0.1:55432/piq"
.venv/Scripts/python.exe -m pytest -q
```

Esperado: **1620 passed, 3 skipped**. Os 3 que sobram são do WeasyPrint
(`libgobject-2.0-0` ausente neste Windows) — geração de PDF, sem relação com
banco, limitação já documentada em `report/pdf.py`.

Sem `DATABASE_URL`: `1548 passed, 75 skipped`. As duas contagens são válidas;
a segunda só cobre menos.

## 5. Abrir a aplicação no navegador

```bash
DATABASE_URL="postgresql://postgres:piq_local_dev@127.0.0.1:55432/piq" \
  .venv/Scripts/python.exe scripts/subir_demo.py
```

O script imprime a URL da coleta e as credenciais. O certificado é
autoassinado, então o navegador avisa — aceite (*Avançado → Prosseguir*).

**Por que um script e não `uvicorn` direto.** Três coisas impedem
`uvicorn app.http.aplicacao:criar_aplicacao --factory` de dar algo navegável:

1. **HTTPS é obrigatório.** `criar_aplicacao()` fixa `https_only=True` no
   cookie de sessão; sobre `http://localhost` o navegador não devolve o
   cookie e toda rota protegida responde `401`. O script serve por TLS com
   certificado efêmero — a produção não é afrouxada para a demo rodar.
2. **Não existe rota HTTP que crie um caso.** `rotas_conta.py` tem cadastro,
   login e logout; o `Caso` nasce direto no repositório (`OQ-11`). O script
   cria conta e caso, como a suíte faz.
3. **`PEND-01`** — sem texto de consentimento, aquela tela bloqueia.

**O passo do consentimento é pulado, e isso não é "resolvido".** O caso nasce
já em `COLETA_INICIAL` — o estado que `inicia_coleta` produziria. O script
**não** escreve nada em `app/consentimento/textos/`: o README de lá é
explícito em que nem um placeholder deve existir, porque um texto que pareça
redação real reintroduz o risco que `PEND-01` existe para evitar. Quando o
jurídico entregar o texto, ele entra lá e a tela volta ao fluxo.

## Restrições de plataforma do frontend (Rodada 4)

Três obstáculos desta máquina, apurados um a um. Nenhum é erro de código, e
todos voltam a morder quem tentar "atualizar tudo".

| O quê | Por quê | O que foi feito |
| --- | --- | --- |
| **Vite 8** não sobe | Usa Rolldown, e `rolldown@1.2.8` publica binário para darwin/android/linux e `win32-arm64` — **não** para `win32-x64-msvc`. Não é download falho: é plataforma sem suporte | Fixado em **Vite 6** |
| **Vite 7** não sobe | Exige Node `^20.19 \|\| >=22.12`; esta máquina tem **22.9.0**. `nvm install 22.20.0` funciona, mas `nvm use` não troca o PATH (preso em `C:\Program Files\nodejs`) | Vite 6 declara `>=22.0.0` e roda como está |
| **oxlint** não roda | Mesma falta de binário: sem `win32-x64-msvc` (só arm64 e ia32) | `npm run lint` passou a ser `tsc -b --noEmit`, que roda e está limpo. `lint:oxlint` continua declarado para quem estiver noutra plataforma |
| **jsdom** quebra | `ERR_REQUIRE_ESM` em `@csstools/css-calc` sob Node 22.9, verificado fora do Vitest | Teste de lógica em `environment: 'node'`; teste de componente em **happy-dom**, por docblock |

Se um dia o Node desta máquina passar de 22.12, dá para voltar ao Vite 7.
Rolldown e oxlint continuam dependendo de a upstream publicar o binário
`win32-x64`.

## Descartar

```bash
docker rm -f piq-postgres
```

O container não tem volume: remover apaga tudo. É o desejado — cada rodada
começa limpa, e nenhum estado de teste sobrevive para contaminar a próxima.

## Uma observação sobre imutabilidade

`002_app_aluno.sql` protege `app_aluno.revisoes` de duas formas: `REVOKE
UPDATE, DELETE ... FROM PUBLIC` **e** uma trigger que levanta exceção. Aqui a
conexão é `postgres`, superusuário — e `REVOKE` não restringe superusuário.

Isso foi verificado, não suposto: um `UPDATE` direto em `app_aluno.revisoes`
como `postgres` é recusado com `RF-24: app_aluno.revisoes é append-only`. É a
**trigger** que sustenta `V-01`/`AC-27` neste ambiente, e ela funciona. Vale
saber, porque num banco onde só o `REVOKE` existisse, estes testes passariam
sem provar nada.
