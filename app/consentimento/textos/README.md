# `app/consentimento/textos/`

Diretório de **dado**, não de código: um arquivo YAML por versão do texto de
consentimento, análogo a `collection/registros/` (`RF-30`, `PEND-01`).

**`2026-09-23-v1.yaml` é RASCUNHO, para destravar o teste do piloto — não é
a resposta de `PEND-01`.** A redação final do texto de consentimento, do
prazo de retenção e do procedimento de exclusão é insumo externo — `PEND-01`,
de responsabilidade do jurídico com o especialista —, e este arquivo não
substitui isso: prazo (5 anos), canal de exclusão (e-mail) e prazo de
atendimento (15 dias úteis) são valores razoáveis escolhidos para o texto
funcionar, não decisão jurídica confirmada. Revisar com o jurídico antes de
qualquer aluno pagante consentir de verdade. `app/consentimento/registro.py
::carregar_texto_vigente` trata a AUSÊNCIA de arquivo aqui como **bloqueio
explícito** do fluxo (critério de aceite de `T-35`) — com o rascunho
presente, o bloqueio não dispara mais; é por isso que ele precisa ser
substituído pela versão revisada antes do piloto valer para gente de fora do
teste.

Formato esperado por arquivo:

```yaml
QUESTIONARIO_VERSION: "<identificador da versão do texto>"
titulo: "<título do texto>"
corpo: "<redação completa do texto de consentimento>"
```

Nenhum conteúdo de exemplo é incluído aqui — mesmo um placeholder que
parecesse redação real reintroduziria o problema que este README documenta.
