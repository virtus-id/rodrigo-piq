# Plano Técnico — `<nome da feature>`

| Campo | Valor                                    |
| ----- | ---------------------------------------- |
| Slug  | `<slug>`                                 |
| Spec  | [`specs/<slug>.spec.md`](../specs/)      |
| Status| `rascunho` \| `em revisão` \| `aprovado` |

## 1. Architecture Overview

<!-- Componentes, camadas e como conversam. Um diagrama em texto ajuda. -->

```text
<entrada> → <camada> → <camada> → <saída>
```

## 2. Tech Stack

| Escolha | Uso | Justificativa (ancorada em `RF-NN`) |
| ------- | --- | ----------------------------------- |
| `<tec>` | `<para quê>` | `<por quê, e qual alternativa foi descartada>` |

> A stack é decidida **aqui**, não no `sdd.config.md`. Deve respeitar as
> restrições e não-objetivos do config. Toda dependência precisa de justificativa.

## 3. Project Structure

| Caminho | Responsabilidade | Novo? |
| ------- | ---------------- | ----- |
| `<path>`| `<o que vive aqui>` | `sim`/`não` |

## 4. Data Model

```ts
// Contratos e tipos principais — assinaturas, não implementação.
```

## 5. Data Flow

<!-- O caminho do dado: entrada → validação → processamento → estado → saída.
     Inclua o que acontece quando cada etapa falha. -->

## 6. External Interfaces

| Serviço | Endpoint / contrato | Auth | Limites | Falha → |
| ------- | ------------------- | ---- | ------- | ------- |
| `<qual>`| `<qual>`            | `<como>` | `<rate limit>` | `<comportamento>` |

## 7. State Management

<!-- Onde o estado vive, quem o possui, como é sincronizado e invalidado. -->

## 8. Error Handling Strategy

| Situação | Detecção | Resposta ao usuário | Recuperação |
| -------- | -------- | ------------------- | ----------- |
| `loading`| —        | `<indicador>`       | —           |
| `erro`   | `<como>` | `<mensagem>`        | `<retry?>`  |
| `vazio`  | `<como>` | `<estado vazio>`    | —           |

## 9. Testing Strategy

- **Unitários:** `<o que, com qual ferramenta>`
- **Integração:** `<quais costuras>`
- **E2E:** `<quais fluxos>`
- **Fora de teste automatizado:** `<o que e por quê>`

## 10. Risks & Trade-offs

| Decisão | Alternativa descartada | Por quê | Risco assumido |
| ------- | ---------------------- | ------- | -------------- |
| `<qual>`| `<qual>`               | `<razão>` | `<qual>`     |

## 11. Traceability

| Requisito | Coberto por (seção do plano) |
| --------- | ---------------------------- |
| `RF-01`   | `<seção>`                    |

> Requisito sem cobertura é buraco no plano. Item de plano sem requisito é
> over-engineering.
