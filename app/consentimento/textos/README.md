# `app/consentimento/textos/`

Diretório de **dado**, não de código: um arquivo YAML por versão do texto de
consentimento, análogo a `collection/registros/` (`RF-30`, `PEND-01`).

**Hoje este diretório está vazio de propósito.** A redação do texto de
consentimento, do prazo de retenção e do procedimento de exclusão é insumo
externo — `PEND-01`, de responsabilidade do jurídico com o especialista — e
ainda não chegou. `app/consentimento/registro.py::carregar_texto_vigente`
trata a ausência de arquivo aqui como **bloqueio explícito** do fluxo, nunca
como "sem consentimento = ok, prossiga" (critério de aceite de `T-35`).

Quando `PEND-01` for respondida, o formato esperado por arquivo é:

```yaml
QUESTIONARIO_VERSION: "<identificador da versão do texto>"
titulo: "<título do texto>"
corpo: "<redação completa do texto de consentimento>"
```

Nenhum conteúdo de exemplo é incluído aqui — mesmo um placeholder que
parecesse redação real reintroduziria o problema que este README documenta.
