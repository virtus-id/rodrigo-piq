# Parâmetros deprecados

## `P_CAIXA_VS_ESTRUTURAL`

- **Status:** `DEPRECATED` — não faz parte de `parameters/parametros-1.0.1.json`.
- **Decisão:** registrada em 2026-09-01, fechando `OQ-02` ("Corte de
  `P_CAIXA_VS_ESTRUTURAL`") — ver `specs/motor-calculo.spec.md` §10 e §11.8.

### Motivo

`GAP_CAIXA_VS_ESTRUTURAL` (`= RESULTADO_CAIXA_OBSERVADO − RESULTADO_MENSAL_ATUAL`,
§11.8 da spec do slug) é um **diagnóstico matemático, sem limiar**. Qualquer
valor `> 0` já indica, por definição, que existe obrigação vigente não saindo
integralmente do caixa observado — não há necessidade de um parâmetro de corte
para decidir se o gap "importa": o próprio sinal do valor é a resposta.

A capacidade de ataque continua derivando exclusivamente de
`RESULTADO_MENSAL_ATUAL`, nunca de um limiar arbitrário aplicado sobre o gap.
Se um dia surgir a necessidade de destacar o alerta no relatório a partir de
um certo tamanho de gap, esse seria um parâmetro de **apresentação**, não de
**decisão da engine** — e viria com nome e escopo próprios, não como
ressurreição deste parâmetro.

### Consequência para quem integra

- `parameters/parametros-1.0.1.json` **não contém** a chave
  `P_CAIXA_VS_ESTRUTURAL`.
- `parameters/esquema-parametros.json` proíbe explicitamente essa chave: um
  arquivo de parâmetros que a incluir falha na validação.
- Nenhum módulo de `engine/` deve ler `P_CAIXA_VS_ESTRUTURAL` de `Parametros`.
