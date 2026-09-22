# Conceder e tirar o papel de revisor

O revisor é quem confere o caso de um aluno e libera (ou reprova) o plano.
Sem pelo menos um revisor, **nenhum plano é liberado**: o aluno termina a
coleta, o caso entra na fila, e fica lá. É o penúltimo passo do sistema, e
ele trava sozinho.

Toda conta nasce sem o papel. Numa instalação nova não existe revisor
nenhum — conceder o primeiro é parte de subir o sistema, não um extra.

## Antes de começar

Você precisa de:

- acesso ao servidor onde a aplicação roda (ou a qualquer máquina com o
  projeto e a `DATABASE_URL` de produção);
- o e-mail de uma conta **que já existe**. O comando nunca cria conta: a
  pessoa precisa ter comprado e definido a senha pelo fluxo normal.

> **Não há tela nem rota para isso, de propósito.** Uma rota de "promover a
> revisor" seria uma porta pública que dá acesso aos dados de todos os
> alunos a quem tiver o segredo dela. Um comando que exige acesso ao
> servidor não tem como ser atacado pela internet.

## Ver quem é revisor hoje

```bash
DATABASE_URL="postgresql://..." .venv/Scripts/python.exe \
    scripts/papel_revisor.py listar
```

Numa instalação nova a resposta é `Nenhum revisor. A fila de revisão está
inalcançável.` — esperado, e é o que você vai resolver a seguir.

## Conceder o papel

```bash
DATABASE_URL="postgresql://..." .venv/Scripts/python.exe \
    scripts/papel_revisor.py promover pessoa@exemplo.br
```

**Confira com `listar` depois.** Um caractere trocado no e-mail pode bater
com a conta de outra pessoa real, e aí um aluno passa a ver o caso de todos
os outros. O `listar` é o que transforma isso de acidente silencioso em
erro visível.

Maiúsculas e espaços sobrando não atrapalham: o e-mail é normalizado do
mesmo jeito que no cadastro.

## Tirar o papel

```bash
DATABASE_URL="postgresql://..." .venv/Scripts/python.exe \
    scripts/papel_revisor.py revogar pessoa@exemplo.br
```

A conta **não** é apagada: ela perde o papel e volta a ser conta comum, com
o caso e o histórico intactos. O acesso fecha na requisição seguinte — o
papel é lido do banco a cada requisição, nunca guardado na sessão.

Revogar de quem já não é revisor não dá erro: o estado final é o que você
pediu.

## Quando algo dá errado

O comando devolve um código de saída por causa, para quem quiser
automatizar:

| Código | O que aconteceu | O que fazer |
| --- | --- | --- |
| `0` | Deu certo | — |
| `2` | `DATABASE_URL` não definida ou banco fora do ar | Confira a variável e se o banco responde |
| `3` | O e-mail não corresponde a nenhuma conta | Confira a digitação; a conta precisa existir antes |
| `4` | A gravação falhou | Leia a mensagem; provavelmente permissão ou conexão caída |

## Se preferir SQL direto

O comando é conveniência. O efeito é uma coluna:

```sql
-- conceder
UPDATE app_aluno.contas SET e_revisor = true  WHERE email = 'pessoa@exemplo.br';
-- tirar
UPDATE app_aluno.contas SET e_revisor = false WHERE email = 'pessoa@exemplo.br';
-- conferir
SELECT email, conta_id, criado_em FROM app_aluno.contas WHERE e_revisor = true;
```

Escrevendo o e-mail **em minúsculas** — é assim que ele é gravado, e o SQL
não normaliza nada por você.
