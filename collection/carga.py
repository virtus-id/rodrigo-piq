"""Carga dos registros de pergunta a partir de `collection/registros/*.yaml` —
`RF-03` (`AC-36`, `AC-38`).

`plans/app-aluno.plan.md` §4.1. Lê cada YAML de `collection/registros/`, valida
sua forma estrutural contra `collection/esquema-registros.json` e converte cada
entrada em `RegistroPergunta` (T-09), com os quatro campos complexos já
resolvidos nos tipos de `Condicao` (T-10/T-11, `collection/condicoes.py`),
`Marcador` (T-12, `collection/interpolacao.py`), `ValidacaoCruzada` (T-13,
`collection/validacao.py`) e `OrigemOpcoes` (T-14, `collection/opcoes_do_motor.py`)
— o YAML nunca vira `dict` solto além do necessário para a validação de
esquema.

CARGA É TUDO-OU-NADA (`AC-36`, `AC-38`): `carregar_registros` devolve a coleção
completa e válida, ou levanta `ErroDeCarga` nomeando o registro/arquivo
culpado — nunca um resultado parcial. As três checagas adicionais ao esquema
estrutural são: (1) `ID` único entre TODOS os arquivos carregados; (2)
`QUESTIONARIO_VERSION` idêntica em todos os arquivos do diretório (nunca fixada
em código — é sempre a lida dos próprios registros); (3) conversão de
`condicao_exibicao`, `interpolacoes`, `validacoes_cruzadas` e `origem_opcoes`
para os tipos complexos, com qualquer forma inesperada tratada como erro de
esquema, nunca ignorada silenciosamente.

REGRAS: `RF-03`, `AC-36`, `AC-38`
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import jsonschema
import yaml

from collection.condicoes import (
    Condicao,
    CondicaoContem,
    CondicaoE,
    CondicaoExisteItem,
    CondicaoIgual,
    CondicaoNao,
    CondicaoOu,
)
from collection.interpolacao import Marcador
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    OpcaoRegistro,
    RegistroPergunta,
    TipoResposta,
)
from collection.validacao import ValidacaoCruzada

REGRAS: Final[tuple[str, ...]] = ("RF-03", "AC-36", "AC-38")

_DIRETORIO_REGISTROS_PADRAO: Final[Path] = Path(__file__).resolve().parent / "registros"
_CAMINHO_ESQUEMA_PADRAO: Final[Path] = Path(__file__).resolve().parent / "esquema-registros.json"


class ErroDeCarga(Exception):
    """Carga inválida — sempre nomeia o `ID` do registro culpado (ou o
    caminho do arquivo, quando o `ID` nem chega a existir) e o campo
    problemático. Levantar esta exceção nunca deixa uma carga parcial: quem
    chama `carregar_registros` recebe ou a coleção completa, ou nada."""


@dataclass(frozen=True, slots=True)
class ColecaoDeRegistros:
    """RF-03 — o resultado tudo-ou-nada de `carregar_registros`.
    `QUESTIONARIO_VERSION` é sempre a lida dos próprios arquivos de registro,
    nunca um literal do carregador (T-16, critério 3)."""

    QUESTIONARIO_VERSION: str
    registros: tuple[RegistroPergunta, ...]


#: Sufixo dos arquivos que NÃO fazem parte do fluxo de coleta — `T-172`.
#:
#: `bloco-12-casos-de-prova.yaml` transcreve três perguntas do Bloco 12
#: (`B12.08`, `B12.15`, `B12.16`) que existem **só** para exercitar três
#: mecanismos do gerador — condição composta de quatro origens, repetição
#: dirigida pelo motor, e opções vindas do snapshot. O próprio cabeçalho do
#: arquivo diz, em caixa alta, que "O BLOCO 12 NÃO É IMPLEMENTADO COMO FLUXO
#: DE COLETA nesta feature" (`T-19`, spec §9 "Out of Scope", `OQ-12`).
#:
#: **Carregá-las no fluxo de coleta tornava o cálculo inalcançável.**
#: `B12.16` é `OBR`, sempre aberta (`condicao_exibicao: None`), e suas opções
#: vêm de `origem_opcoes.fonte=SNAPSHOT`, campo `ORDEM_ACOES` — que só existe
#: DEPOIS do primeiro cálculo. Como `pendencias_obrigatorias` a contava como
#: pendente, `POST /caso/{id}/calculo` respondia `400` para sempre: a
#: pergunta que bloqueia o cálculo só poderia ser respondida depois do
#: cálculo. Verificado contra o servidor real com a coleta inteira
#: respondida pela tela — 176 de 177, e a 177ª sem nenhuma opção para
#: escolher.
#:
#: O filtro é pelo NOME do arquivo, não por bloco: "casos de prova" é uma
#: categoria de arquivo, e um bloco novo com o mesmo papel deve poder existir
#: sem editar esta constante. Os registros continuam carregáveis passando o
#: diretório explicitamente, que é o que os testes do gerador fazem.
SUFIXO_FORA_DA_COLETA: Final[str] = "-casos-de-prova.yaml"


def carregar_registros(
    diretorio: Path | None = None,
    caminho_esquema: Path | None = None,
    incluir_casos_de_prova: bool = False,
) -> ColecaoDeRegistros:
    """RF-03 — carrega, valida e converte os `*.yaml` de `diretorio`
    (padrão: `collection/registros/`). Tudo-ou-nada: a primeira falha aborta
    a carga inteira com `ErroDeCarga` nomeando o registro ou arquivo
    culpado — nenhuma coleção parcial é devolvida.

    Arquivos terminados em `-casos-de-prova.yaml` ficam **de fora** por
    padrão (`T-172`): são registros de prova do gerador, não perguntas do
    questionário. `incluir_casos_de_prova=True` os traz de volta, para quem
    precisa exercitar o gerador sobre eles."""
    diretorio_registros = diretorio or _DIRETORIO_REGISTROS_PADRAO
    esquema = _carregar_esquema(caminho_esquema or _CAMINHO_ESQUEMA_PADRAO)

    todos = sorted(diretorio_registros.glob("*.yaml"))
    arquivos = (
        todos
        if incluir_casos_de_prova
        else [c for c in todos if not c.name.endswith(SUFIXO_FORA_DA_COLETA)]
    )
    if not arquivos:
        raise ErroDeCarga(f"Nenhum arquivo .yaml encontrado em {diretorio_registros}")

    registros_por_arquivo: list[tuple[Path, str, tuple[RegistroPergunta, ...]]] = []
    for caminho in arquivos:
        bruto = _ler_yaml(caminho)
        _validar_esquema(caminho, bruto, esquema)
        versao = bruto["QUESTIONARIO_VERSION"]
        registros = tuple(
            _converter_registro(caminho, pergunta) for pergunta in bruto["perguntas"]
        )
        registros_por_arquivo.append((caminho, versao, registros))

    _verificar_versao_unica(registros_por_arquivo)
    _verificar_id_unico(registros_por_arquivo)

    QUESTIONARIO_VERSION = registros_por_arquivo[0][1]
    todos_os_registros = tuple(
        registro
        for _caminho, _versao, registros in registros_por_arquivo
        for registro in registros
    )
    return ColecaoDeRegistros(
        QUESTIONARIO_VERSION=QUESTIONARIO_VERSION,
        registros=todos_os_registros,
    )


def _carregar_esquema(caminho_esquema: Path) -> dict[str, Any]:
    with caminho_esquema.open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def _ler_yaml(caminho: Path) -> dict[str, Any]:
    try:
        with caminho.open(encoding="utf-8") as f:
            bruto = yaml.safe_load(f)
    except yaml.YAMLError as erro:
        raise ErroDeCarga(f"YAML inválido em {caminho}: {erro}") from erro
    if not isinstance(bruto, dict):
        raise ErroDeCarga(f"Arquivo {caminho} não é um mapeamento YAML na raiz")
    return bruto


def _validar_esquema(caminho: Path, bruto: dict[str, Any], esquema: dict[str, Any]) -> None:
    try:
        jsonschema.validate(instance=bruto, schema=esquema)
    except jsonschema.ValidationError as erro:
        caminho_do_campo = list(erro.absolute_path)
        campo = ".".join(str(parte) for parte in caminho_do_campo) or "(raiz)"
        identificador = _identificador_do_erro_de_esquema(caminho, bruto, caminho_do_campo)
        raise ErroDeCarga(
            f"Esquema violado em {identificador} (campo {campo!r}): {erro.message}"
        ) from erro


def _identificador_do_erro_de_esquema(
    caminho: Path, bruto: dict[str, Any], caminho_do_campo: list[Any]
) -> str:
    """Quando o campo que violou o esquema pertence a um item de `perguntas`
    (`perguntas.<indice>...`), nomeia o registro pelo seu `ID` — mesmo padrão
    de `_identificador_do_erro`, aplicado ao erro estrutural do `jsonschema`
    em vez do erro de conversão."""
    if len(caminho_do_campo) >= 2 and caminho_do_campo[0] == "perguntas":
        indice = caminho_do_campo[1]
        perguntas = bruto.get("perguntas")
        if isinstance(perguntas, list) and isinstance(indice, int) and 0 <= indice < len(
            perguntas
        ):
            return _identificador_do_erro(caminho, perguntas[indice])
    return str(caminho)


def _identificador_do_erro(caminho: Path, pergunta: dict[str, Any]) -> str:
    """Nomeia o registro culpado por seu `ID` sempre que ele já existe no
    dicionário bruto — mesmo que outro campo obrigatório esteja ausente; cai
    para o caminho do arquivo só quando o `ID` nem chega a existir."""
    ID = pergunta.get("ID")
    if isinstance(ID, str) and ID:
        return f"ID={ID!r} ({caminho})"
    return f"{caminho} (registro sem ID)"


def _converter_registro(caminho: Path, pergunta: dict[str, Any]) -> RegistroPergunta:
    identificador = _identificador_do_erro(caminho, pergunta)
    try:
        return RegistroPergunta(
            ID=pergunta["ID"],
            bloco=pergunta["bloco"],
            enunciado=pergunta["enunciado"],
            tipo=TipoResposta(pergunta["tipo"]),
            obrigatoriedade=frozenset(
                Obrigatoriedade(item) for item in pergunta["obrigatoriedade"]
            ),
            escopo_repeticao=EscopoRepeticao(pergunta["escopo_repeticao"]),
            opcoes=tuple(_converter_opcao(opcao) for opcao in pergunta["opcoes"]),
            VARIAVEL_GRAVADA=pergunta["VARIAVEL_GRAVADA"],
            condicao_exibicao=_converter_condicao(pergunta["condicao_exibicao"]),
            interpolacoes=tuple(
                _converter_marcador(marcador) for marcador in pergunta["interpolacoes"]
            ),
            validacoes_cruzadas=tuple(
                _converter_validacao_cruzada(validacao)
                for validacao in pergunta["validacoes_cruzadas"]
            ),
            origem_opcoes=_converter_origem_opcoes(pergunta["origem_opcoes"]),
            admite_nao_sei=pergunta["admite_nao_sei"],
            salto_consequencia=pergunta["salto_consequencia"],
        )
    except KeyError as erro:
        raise ErroDeCarga(f"Registro {identificador}: campo ausente {erro}") from erro
    except ValueError as erro:
        raise ErroDeCarga(f"Registro {identificador}: {erro}") from erro


def _converter_opcao(bruta: dict[str, Any]) -> OpcaoRegistro:
    return OpcaoRegistro(
        rotulo=bruta["rotulo"],
        valor_interno=bruta["valor_interno"],
        admite_nao_sei=bruta.get("admite_nao_sei", False),
    )


def _converter_condicao(bruta: dict[str, Any] | None) -> Condicao | None:
    if bruta is None:
        return None
    tipo = bruta["tipo"]
    if tipo == "IGUAL":
        return CondicaoIgual(variavel=bruta["variavel"], valor=bruta["valor"])
    if tipo == "CONTEM":
        return CondicaoContem(variavel=bruta["variavel"], valor=bruta["valor"])
    if tipo == "EXISTE_ITEM":
        return CondicaoExisteItem(
            escopo=EscopoRepeticao(bruta["escopo"]),
            variavel=bruta["variavel"],
            valor_em=frozenset(bruta["valor_em"]),
        )
    if tipo == "E":
        return CondicaoE(
            termos=tuple(_converter_condicao(termo) for termo in bruta["termos"])  # type: ignore[misc]
        )
    if tipo == "OU":
        return CondicaoOu(
            termos=tuple(_converter_condicao(termo) for termo in bruta["termos"])  # type: ignore[misc]
        )
    if tipo == "NAO":
        termo = _converter_condicao(bruta["termo"])
        assert termo is not None
        return CondicaoNao(termo=termo)
    raise ValueError(f"tipo de condição desconhecido: {tipo!r}")


def _converter_marcador(bruta: dict[str, Any]) -> Marcador:
    return Marcador(
        marcador=bruta["marcador"],
        origem=bruta["origem"],
        referencia=bruta["referencia"],
    )


def _converter_validacao_cruzada(bruta: dict[str, Any]) -> ValidacaoCruzada:
    return ValidacaoCruzada(
        variavel_esquerda=bruta["variavel_esquerda"],
        operador=bruta["operador"],
        variavel_direita=bruta["variavel_direita"],
        escopo=EscopoRepeticao(bruta["escopo"]),
        mensagem=bruta["mensagem"],
    )


def _converter_origem_opcoes(bruta: dict[str, Any]) -> OrigemOpcoes:
    return OrigemOpcoes(
        fonte=bruta["fonte"],
        campo_do_snapshot=bruta["campo_do_snapshot"],
    )


def _verificar_versao_unica(
    registros_por_arquivo: list[tuple[Path, str, tuple[RegistroPergunta, ...]]],
) -> None:
    """`QUESTIONARIO_VERSION` precisa ser a mesma em todos os arquivos do
    diretório — um questionário tem uma única versão corrente, nunca uma
    mistura entre blocos (T-16, critério 3)."""
    versoes = {versao for _caminho, versao, _registros in registros_por_arquivo}
    if len(versoes) > 1:
        # Mensagem composta a partir de fragmentos curtos em tempo de
        # execução — nunca um único literal longo (limiar de `AC-37`/`T-08`:
        # string > 40 caracteres fora de docstring é auditada; mesmo padrão
        # de `collection/interpolacao.py::_erro`).
        detalhe = ", ".join(
            f"{caminho} (QUESTIONARIO_VERSION={versao!r})"
            for caminho, versao, _registros in registros_por_arquivo
        )
        raise ErroDeCarga(" ".join(("QUESTIONARIO_VERSION divergente", "entre arquivos:", detalhe)))


def _verificar_id_unico(
    registros_por_arquivo: list[tuple[Path, str, tuple[RegistroPergunta, ...]]],
) -> None:
    """`ID` duplicado entre arquivos (ou dentro do mesmo arquivo) faz a carga
    falhar nomeando os dois arquivos envolvidos (T-16, critério 2; `AC-38`)."""
    arquivo_por_id: dict[str, Path] = {}
    for caminho, _versao, registros in registros_por_arquivo:
        for registro in registros:
            arquivo_anterior = arquivo_por_id.get(registro.ID)
            if arquivo_anterior is not None:
                raise ErroDeCarga(
                    f"ID duplicado {registro.ID!r} entre {arquivo_anterior} e {caminho}"
                )
            arquivo_por_id[registro.ID] = caminho
