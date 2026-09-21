"""Adaptador de arquivo de `FonteParametros` — RF-13, RF-12, AC-17.

Lê `parameters/parametros-<versao>.json`, valida contra
`parameters/esquema-parametros.json` com `jsonschema` e só então constrói um
`Parametros`. Padrão em testes e dev (plans/motor-calculo.plan.md §6).

Direção de dependência: este módulo importa de `engine/` — nunca o
contrário. `engine/` não sabe que arquivo existe (lei nº 1 da §1 do plano).
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

import jsonschema

from engine.parametros import ErroParametros, Parametros
from engine.portas import FonteParametros

REGRAS: Final[tuple[str, ...]] = ("RF-13", "RF-12", "AC-17")

_DIRETORIO_PARAMETROS: Final[Path] = Path(__file__).resolve().parents[2] / "parameters"
_ESQUEMA_PADRAO: Final[Path] = _DIRETORIO_PARAMETROS / "esquema-parametros.json"

# Chaves do JSON que não são parâmetros numéricos escalares — não passam por
# numero(), mas fazem parte do carimbo (`Parametros`) ou do domínio de
# REGRA_* (comportamento, não número).
_CHAVES_CARIMBO: Final[frozenset[str]] = frozenset(
    {"ENGINE_VERSION", "PARAMETROS_VERSION", "DATA_VIGENCIA"}
)


class FonteParametrosArquivo(FonteParametros):
    """Lê parâmetros de `parameters/parametros-<versao>.json`.

    `diretorio_parametros` e `caminho_esquema` são injetáveis para teste
    (arquivo temporário com esquema violado, versão divergente etc.) — sem
    isso, T-07 não seria verificável sem tocar o arquivo real do repositório.
    """

    def __init__(
        self,
        diretorio_parametros: Path | None = None,
        caminho_esquema: Path | None = None,
    ) -> None:
        self._diretorio_parametros = diretorio_parametros or _DIRETORIO_PARAMETROS
        self._caminho_esquema = caminho_esquema or _ESQUEMA_PADRAO

    def carregar(self, versao: str) -> Parametros:
        """RF-13/AC-17: carrega, valida contra o esquema e confere a versão.

        Ordem: ler JSON com `parse_float=Decimal` (nenhum literal numérico
        passa por `float`) → normalizar `int` remanescente para `Decimal`
        (json.load só chama `parse_float` para literais com ponto/expoente;
        `1`, `20` etc. continuam `int` — normalizar aqui fecha essa lacuna
        sem jamais passar o valor por `float`) → validar contra o esquema →
        conferir `PARAMETROS_VERSION` → construir `Parametros`. Qualquer
        falha aborta com `ErroParametros`, nunca com um valor embutido no
        motor.
        """
        caminho = self._diretorio_parametros / f"parametros-{versao}.json"
        if not caminho.is_file():
            raise ErroParametros(
                f"Arquivo de parâmetros não encontrado para a versão {versao!r}: {caminho}"
            )

        try:
            with caminho.open(encoding="utf-8") as f:
                bruto = json.load(f, parse_float=Decimal)
        except json.JSONDecodeError as erro:
            raise ErroParametros(f"JSON inválido em {caminho}: {erro}") from erro

        bruto = _normalizar_numeros(bruto)

        with self._caminho_esquema.open(encoding="utf-8") as f:
            esquema = json.load(f)

        try:
            jsonschema.validate(instance=_serializavel(bruto), schema=esquema)
        except jsonschema.ValidationError as erro:
            campo = ".".join(str(parte) for parte in erro.absolute_path) or "(raiz)"
            raise ErroParametros(
                f"Esquema de parâmetros violado em {campo!r}: {erro.message}"
            ) from erro

        versao_arquivo = bruto.get("PARAMETROS_VERSION")
        if versao_arquivo != versao:
            raise ErroParametros(
                f"PARAMETROS_VERSION do arquivo ({versao_arquivo!r}) diverge "
                f"da versão pedida ({versao!r})"
            )

        return _construir_parametros(bruto)


def _normalizar_numeros(bruto: dict[str, object]) -> dict[str, object]:
    """`int` puro (sem ponto/expoente) escapa de `parse_float` — vira `Decimal`
    aqui via `Decimal(int)`, uma conversão exata que nunca passa por `float`
    (RF-12). Arrays têm cada elemento normalizado da mesma forma.
    """

    def normalizar(valor: object) -> object:
        if isinstance(valor, bool):
            return valor  # bool é subclasse de int — não é parâmetro numérico
        if isinstance(valor, int):
            return Decimal(valor)
        if isinstance(valor, list):
            return [normalizar(v) for v in valor]
        return valor

    return {chave: normalizar(valor) for chave, valor in bruto.items()}


def _serializavel(bruto: dict[str, object]) -> dict[str, object]:
    """Converte `Decimal` para tipo aceito pelo validador do `jsonschema`.

    O validador de `"type": "number"` do `jsonschema` não reconhece
    `Decimal` (não é `int`/`float`/`bool`). A conversão aqui é só para a
    checagem de esquema — o `Parametros` construído em seguida usa sempre o
    `Decimal` normalizado por `_normalizar_numeros`, nunca este `float`.
    """
    convertido: dict[str, object] = {}
    for chave, valor in bruto.items():
        if isinstance(valor, Decimal):
            convertido[chave] = float(valor)
        elif isinstance(valor, list):
            convertido[chave] = [float(v) if isinstance(v, Decimal) else v for v in valor]
        else:
            convertido[chave] = valor
    return convertido


def _construir_parametros(bruto: dict[str, object]) -> Parametros:
    """Monta `_valores`: escalares viram `Decimal`, arrays viram `tuple[Decimal, ...]`.

    `_normalizar_numeros` já garantiu que todo literal numérico — incluindo
    os de dentro de arrays JSON — é `Decimal` neste ponto. Aqui só se
    organiza a estrutura resultante; nenhum novo valor numérico é criado.
    """
    valores: dict[str, Decimal | str | tuple[Decimal, ...]] = {}
    for chave, valor in bruto.items():
        if chave in _CHAVES_CARIMBO:
            continue
        if isinstance(valor, list):
            valores[chave] = tuple(valor)
        elif isinstance(valor, (Decimal, str)):
            valores[chave] = valor
        else:
            raise ErroParametros(
                f"Parâmetro {chave!r} tem tipo inesperado após a carga: "
                f"{type(valor).__name__}"
            )

    return Parametros(
        PARAMETROS_VERSION=_string_obrigatoria(bruto, "PARAMETROS_VERSION"),
        ENGINE_VERSION=_string_obrigatoria(bruto, "ENGINE_VERSION"),
        DATA_VIGENCIA=_data_vigencia(bruto["DATA_VIGENCIA"]),
        _valores=valores,
    )


def _string_obrigatoria(bruto: dict[str, object], chave: str) -> str:
    valor = bruto[chave]
    if not isinstance(valor, str):
        raise ErroParametros(f"{chave} deve ser string, recebido {valor!r}")
    return valor


def _data_vigencia(valor: object) -> date:
    if not isinstance(valor, str):
        raise ErroParametros(f"DATA_VIGENCIA deve ser string ISO 8601, recebido {valor!r}")
    return date.fromisoformat(valor)
