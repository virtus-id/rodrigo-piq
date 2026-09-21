# Backlog — `<nome da feature>`

| Campo | Valor                                 |
| ----- | ------------------------------------- |
| Slug  | `<slug>`                              |
| Spec  | [`specs/<slug>.spec.md`](../specs/)   |
| Plano | [`plans/<slug>.plan.md`](../plans/)   |

## Progresso

`0/N tarefas concluídas`

---

## Entrega 1 — `<nome da fatia de valor>`

### `T-01` — `<título começando por verbo>`

- **Tipo:** `UI` \| `Data` \| `Infra` \| `Test` \| `Docs`
- **Dependências:** `nenhuma`
- **Rastreia:** `RF-01`, `AC-01`
- **Arquivos:** `<caminhos prováveis a criar/editar>`

**Descrição**

<!-- 1 a 3 linhas. O suficiente para executar sem abrir o plano. -->

**Critérios de aceite**

- [ ] `<condição verificável>`
- [ ] `<condição verificável>`

**Status:** `[ ] pendente` \| `[~] em andamento` \| `[x] concluída`

---

### `T-02` — `<título>`

- **Tipo:** `<tipo>`
- **Dependências:** `T-01`
- **Rastreia:** `RF-01`
- **Arquivos:** `<caminhos>`

**Descrição**

**Critérios de aceite**

- [ ] `<condição verificável>`

**Status:** `[ ] pendente`

---

## Cobertura de requisitos

| Requisito | Tarefas       |
| --------- | ------------- |
| `RF-01`   | `T-01`, `T-02`|

> Requisito sem tarefa não será implementado. Tarefa sem requisito é escopo
> extra — remova ou volte à spec.
