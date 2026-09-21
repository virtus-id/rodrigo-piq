# Spec — `<nome da feature>`

| Campo    | Valor                                      |
| -------- | ------------------------------------------ |
| Slug     | `<slug>`                                   |
| Status   | `rascunho` \| `em revisão` \| `aprovada`   |
| Autor    | `<quem>`                                   |
| Data     | `<AAAA-MM-DD>`                             |

## 1. Overview

<!-- Problema, objetivo e para quem. Máximo 2 parágrafos. -->

## 2. Functional Requirements

| ID      | Requisito                | Prioridade                        |
| ------- | ------------------------ | --------------------------------- |
| `RF-01` | `<o que o sistema faz>`  | `essencial` \| `importante` \| `desejável` |

## 3. User Stories

### `US-01` — `<título>`

> Como **`<persona>`**, quero **`<ação>`** para **`<valor>`**.

Atende: `RF-01`

## 4. Acceptance Criteria

| ID      | Story   | Critério (verificável)                          |
| ------- | ------- | ----------------------------------------------- |
| `AC-01` | `US-01` | `Dado <contexto>, quando <ação>, então <resultado observável>` |

> Todo critério precisa poder virar teste sem reinterpretação.

## 5. Non-Functional Requirements

- **Performance:** `<meta numérica, ex.: p95 < 500 ms>`
- **Acessibilidade:** `<ex.: WCAG AA, navegável por teclado>`
- **Responsividade:** `<breakpoints suportados>`
- **Segurança:** `<validação, autenticação, dados sensíveis>`
- **Observabilidade:** `<logs, métricas, erros>`

## 6. Edge Cases

| ID      | Situação                    | Comportamento esperado |
| ------- | --------------------------- | ---------------------- |
| `EC-01` | `<entrada inválida>`        | `<o que acontece>`     |
| `EC-02` | `<falha de serviço externo>`| `<o que acontece>`     |
| `EC-03` | `<timeout>`                 | `<o que acontece>`     |
| `EC-04` | `<resultado vazio>`         | `<o que acontece>`     |

## 7. Assumptions

- `<premissa adotada e por quê>`

## 8. Risks

| Risco   | Impacto             | Mitigação   |
| ------- | ------------------- | ----------- |
| `<qual>`| `alto`/`médio`/`baixo` | `<como>` |

## 9. Out of Scope

- `<o que explicitamente NÃO será feito, e por quê>`

## 10. Open Questions

| ID     | Pergunta   | Por que importa                  | Status                     |
| ------ | ---------- | -------------------------------- | -------------------------- |
| `OQ-01`| `<qual>`   | `<o que muda conforme a resposta>` | `aberta` \| `respondida` |
