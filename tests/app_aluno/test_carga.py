"""Testes de `collection/carga.py` — RF-03, AC-36, AC-38 (T-16).

Cobre `carregar_registros` pelo comportamento observável (a `ColecaoDeRegistros`
devolvida, ou a `ErroDeCarga` levantada), nunca por implementação interna.
Os YAML usados aqui são SINTÉTICOS, escritos em `tmp_path` — os YAML reais dos
Blocos 1–12 são T-17/T-18/T-19, que ainda não existem. Os quatro critérios de
aceite de `T-16` são cobertos um a um.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from collection.carga import ColecaoDeRegistros, ErroDeCarga, carregar_registros
from collection.condicoes import CondicaoContem, CondicaoE, CondicaoIgual, CondicaoNao, CondicaoOu
from collection.interpolacao import Marcador
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    NIVEL_COMPROVACAO,
    EscopoRepeticao,
    NivelCondicional,
    Obrigatoriedade,
    RegistroPergunta,
    TipoResposta,
)
from collection.validacao import ValidacaoCruzada

_ESQUEMA_PADRAO = Path(__file__).resolve().parents[2] / "collection" / "esquema-registros.json"


def _pergunta_minima(
    ID: str,
    *,
    VARIAVEL_GRAVADA: str | None = None,
    condicao_exibicao: dict[str, object] | None = None,
    interpolacoes: list[dict[str, object]] | None = None,
    validacoes_cruzadas: list[dict[str, object]] | None = None,
    origem_opcoes: dict[str, object] | None = None,
    escopo_repeticao: str = "NENHUM",
    obrigatoriedade: list[str] | None = None,
    opcoes: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Fábrica mínima de um registro bruto (dicionário serializável em YAML),
    com todos os campos obrigatórios de `RegistroPergunta` preenchidos por
    padrão neutro. Cada teste sobrescreve só o que precisa exercitar."""
    return {
        "ID": ID,
        "bloco": 1,
        "enunciado": "Enunciado de teste.",
        "tipo": "TEXTO_CURTO",
        "obrigatoriedade": obrigatoriedade or ["OBR"],
        "escopo_repeticao": escopo_repeticao,
        "opcoes": opcoes or [],
        "VARIAVEL_GRAVADA": VARIAVEL_GRAVADA or f"VARIAVEL_{ID.replace('.', '_')}",
        "condicao_exibicao": condicao_exibicao,
        "interpolacoes": interpolacoes or [],
        "validacoes_cruzadas": validacoes_cruzadas or [],
        "origem_opcoes": origem_opcoes or {"fonte": "REGISTRO", "campo_do_snapshot": None},
        "admite_nao_sei": False,
        "salto_consequencia": None,
    }


def _escrever_arquivo(
    caminho: Path, *, QUESTIONARIO_VERSION: str, perguntas: list[dict[str, object]]
) -> None:
    caminho.write_text(
        yaml.safe_dump(
            {"QUESTIONARIO_VERSION": QUESTIONARIO_VERSION, "perguntas": perguntas},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def test_registro_com_campo_obrigatorio_ausente_falha_nomeando_id_e_campo(
    tmp_path: Path,
) -> None:
    """Critério de aceite 1: um registro sem `enunciado` (campo obrigatório de
    `RegistroPergunta`) faz a carga falhar, e a mensagem de erro nomeia tanto
    o `ID` do registro culpado quanto o campo ausente."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    pergunta_incompleta = _pergunta_minima("B1.INCOMPLETA")
    del pergunta_incompleta["enunciado"]
    _escrever_arquivo(
        diretorio / "bloco-01.yaml",
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[pergunta_incompleta],
    )

    with pytest.raises(ErroDeCarga) as excecao:
        carregar_registros(diretorio, _ESQUEMA_PADRAO)

    mensagem = str(excecao.value)
    assert "B1.INCOMPLETA" in mensagem
    assert "enunciado" in mensagem


def test_registro_sem_id_falha_nomeando_o_caminho_do_arquivo(tmp_path: Path) -> None:
    """Complementa o critério 1: quando o próprio `ID` nem existe, o erro
    nomeia o caminho do arquivo culpado em vez de um `ID` inexistente."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    pergunta_sem_id = _pergunta_minima("PLACEHOLDER")
    del pergunta_sem_id["ID"]
    caminho_arquivo = diretorio / "bloco-01.yaml"
    _escrever_arquivo(caminho_arquivo, QUESTIONARIO_VERSION="1.0.0", perguntas=[pergunta_sem_id])

    with pytest.raises(ErroDeCarga) as excecao:
        carregar_registros(diretorio, _ESQUEMA_PADRAO)

    assert str(caminho_arquivo) in str(excecao.value)


def test_id_duplicado_entre_arquivos_falha_nomeando_os_dois_arquivos(tmp_path: Path) -> None:
    """Critério de aceite 2: o mesmo `ID` em dois arquivos diferentes faz a
    carga falhar, nomeando os dois caminhos de arquivo envolvidos."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    caminho_bloco_01 = diretorio / "bloco-01.yaml"
    caminho_bloco_02 = diretorio / "bloco-02.yaml"
    _escrever_arquivo(
        caminho_bloco_01,
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[_pergunta_minima("B1.01")],
    )
    _escrever_arquivo(
        caminho_bloco_02,
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[_pergunta_minima("B1.01")],
    )

    with pytest.raises(ErroDeCarga) as excecao:
        carregar_registros(diretorio, _ESQUEMA_PADRAO)

    mensagem = str(excecao.value)
    assert "B1.01" in mensagem
    assert str(caminho_bloco_01) in mensagem
    assert str(caminho_bloco_02) in mensagem


def test_carga_com_id_duplicado_nao_devolve_nenhuma_colecao_parcial(tmp_path: Path) -> None:
    """Reforça "nunca carrega parcialmente": mesmo havendo registros válidos
    nos dois arquivos, a duplicidade de um único `ID` aborta a carga inteira
    — nenhuma coleção parcial chega a ser observável pelo chamador."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    _escrever_arquivo(
        diretorio / "bloco-01.yaml",
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[_pergunta_minima("B1.01"), _pergunta_minima("B1.02")],
    )
    _escrever_arquivo(
        diretorio / "bloco-02.yaml",
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[_pergunta_minima("B1.01")],
    )

    with pytest.raises(ErroDeCarga):
        carregar_registros(diretorio, _ESQUEMA_PADRAO)


def test_questionario_version_e_lido_dos_registros_nunca_fixado_em_codigo(
    tmp_path: Path,
) -> None:
    """Critério de aceite 3: `QUESTIONARIO_VERSION` da coleção devolvida é
    exatamente o valor lido do YAML — trocar o valor no arquivo muda o valor
    exposto, sem qualquer alteração em `collection/carga.py`."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    _escrever_arquivo(
        diretorio / "bloco-01.yaml",
        QUESTIONARIO_VERSION="2024.03-rc7",
        perguntas=[_pergunta_minima("B1.01")],
    )

    colecao = carregar_registros(diretorio, _ESQUEMA_PADRAO)

    assert colecao.QUESTIONARIO_VERSION == "2024.03-rc7"


def test_questionario_version_divergente_entre_arquivos_falha(tmp_path: Path) -> None:
    """Complementa o critério 3: dois arquivos com `QUESTIONARIO_VERSION`
    diferentes é carga inválida — um questionário tem uma única versão
    corrente, nunca uma mistura entre blocos."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    _escrever_arquivo(
        diretorio / "bloco-01.yaml",
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[_pergunta_minima("B1.01")],
    )
    _escrever_arquivo(
        diretorio / "bloco-02.yaml",
        QUESTIONARIO_VERSION="1.0.1",
        perguntas=[_pergunta_minima("B2.01")],
    )

    with pytest.raises(ErroDeCarga) as excecao:
        carregar_registros(diretorio, _ESQUEMA_PADRAO)

    mensagem = str(excecao.value)
    assert "1.0.0" in mensagem
    assert "1.0.1" in mensagem


def test_condicao_do_yaml_e_convertida_para_os_tipos_de_condicoes_py(tmp_path: Path) -> None:
    """Critério de aceite 4 (parte `Condicao`, T-10/T-11): `condicao_exibicao`
    do YAML vira uma árvore real de `collection.condicoes` — aqui um
    `CondicaoOu` de dois termos (`CondicaoIgual` e `CondicaoContem`), o mesmo
    formato do caso de prova `B12.08` (quatro termos, RF-05) reduzido a dois
    para o teste. Nunca um `dict` solto."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    condicao_bruta: dict[str, object] = {
        "tipo": "OU",
        "termos": [
            {"tipo": "IGUAL", "variavel": "SITUACAO_EMPREGO", "valor": "DESEMPREGADO"},
            {"tipo": "CONTEM", "variavel": "MECANISMO_DEFICIT", "valor": "CARTAO_CREDITO"},
        ],
    }
    _escrever_arquivo(
        diretorio / "bloco-12.yaml",
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[_pergunta_minima("B12.08", condicao_exibicao=condicao_bruta)],
    )

    colecao = carregar_registros(diretorio, _ESQUEMA_PADRAO)

    registro = colecao.registros[0]
    condicao = registro.condicao_exibicao
    assert isinstance(condicao, CondicaoOu)
    assert len(condicao.termos) == 2
    assert condicao.termos[0] == CondicaoIgual(variavel="SITUACAO_EMPREGO", valor="DESEMPREGADO")
    assert condicao.termos[1] == CondicaoContem(
        variavel="MECANISMO_DEFICIT", valor="CARTAO_CREDITO"
    )


def test_interpolacao_do_yaml_e_convertida_para_marcador_de_interpolacao_py(
    tmp_path: Path,
) -> None:
    """Critério de aceite 4 (parte `Marcador`, T-12): `interpolacoes` do YAML
    vira uma tupla de `collection.interpolacao.Marcador` — o caso de
    `B11.Q01` (`[Dxxx]` → `ID_DO_ITEM`)."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    marcador_bruto: dict[str, object] = {
        "marcador": "[Dxxx]",
        "origem": "ID_DO_ITEM",
        "referencia": "",
    }
    _escrever_arquivo(
        diretorio / "bloco-11.yaml",
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[
            _pergunta_minima(
                "B11.Q01",
                escopo_repeticao="ACAO_ID",
                interpolacoes=[marcador_bruto],
            )
        ],
    )

    colecao = carregar_registros(diretorio, _ESQUEMA_PADRAO)

    registro = colecao.registros[0]
    assert registro.interpolacoes == (
        Marcador(marcador="[Dxxx]", origem="ID_DO_ITEM", referencia=""),
    )


def test_validacao_cruzada_do_yaml_e_convertida_para_validacaocruzada_de_validacao_py(
    tmp_path: Path,
) -> None:
    """Critério de aceite 4 (parte `ValidacaoCruzada`, T-13): o caso
    normativo `VALOR_UTILIZADO_MARGEM <= VALOR_TOTAL_MARGEM`, por
    `MARGEM_ID`."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    validacao_bruta: dict[str, object] = {
        "variavel_esquerda": "VALOR_UTILIZADO_MARGEM",
        "operador": "<=",
        "variavel_direita": "VALOR_TOTAL_MARGEM",
        "escopo": "MARGEM_ID",
        "mensagem": "O valor utilizado não pode superar o valor total da margem.",
    }
    _escrever_arquivo(
        diretorio / "bloco-05.yaml",
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[
            _pergunta_minima(
                "B5.M02",
                escopo_repeticao="MARGEM_ID",
                validacoes_cruzadas=[validacao_bruta],
            )
        ],
    )

    colecao = carregar_registros(diretorio, _ESQUEMA_PADRAO)

    registro = colecao.registros[0]
    assert registro.validacoes_cruzadas == (
        ValidacaoCruzada(
            variavel_esquerda="VALOR_UTILIZADO_MARGEM",
            operador="<=",
            variavel_direita="VALOR_TOTAL_MARGEM",
            escopo=EscopoRepeticao.MARGEM_ID,
            mensagem="O valor utilizado não pode superar o valor total da margem.",
        ),
    )


def test_origem_de_opcoes_do_yaml_e_convertida_para_origemopcoes_de_opcoes_do_motor_py(
    tmp_path: Path,
) -> None:
    """Critério de aceite 4 (parte `OrigemOpcoes`, T-14): o caso de prova
    `B12.16`, com `fonte=SNAPSHOT` e o campo do snapshot nomeado."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    origem_bruta: dict[str, object] = {"fonte": "SNAPSHOT", "campo_do_snapshot": "REGRAS_PROPOSTAS"}
    _escrever_arquivo(
        diretorio / "bloco-12.yaml",
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[_pergunta_minima("B12.16", origem_opcoes=origem_bruta)],
    )

    colecao = carregar_registros(diretorio, _ESQUEMA_PADRAO)

    registro = colecao.registros[0]
    assert registro.origem_opcoes == OrigemOpcoes(
        fonte="SNAPSHOT", campo_do_snapshot="REGRAS_PROPOSTAS"
    )


def test_carga_bem_sucedida_produz_registropergunta_real_nao_dict_solto(
    tmp_path: Path,
) -> None:
    """Reforça o critério 4 de forma direta: o resultado de uma carga válida
    é uma tupla de `RegistroPergunta` — nunca um `dict`."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    _escrever_arquivo(
        diretorio / "bloco-01.yaml",
        QUESTIONARIO_VERSION="1.0.0",
        perguntas=[_pergunta_minima("B1.01")],
    )

    colecao = carregar_registros(diretorio, _ESQUEMA_PADRAO)

    assert isinstance(colecao, ColecaoDeRegistros)
    assert len(colecao.registros) == 1
    assert isinstance(colecao.registros[0], RegistroPergunta)
    assert colecao.registros[0].tipo == TipoResposta.TEXTO_CURTO
    assert colecao.registros[0].obrigatoriedade == frozenset({Obrigatoriedade.OBR})
    assert colecao.registros[0].escopo_repeticao == EscopoRepeticao.NENHUM


def test_diretorio_sem_nenhum_yaml_falha(tmp_path: Path) -> None:
    """Diretório vazio nunca produz coleção vazia silenciosa — a ausência
    total de registro é tratada como carga inválida."""
    diretorio = tmp_path / "registros_vazio"
    diretorio.mkdir()

    with pytest.raises(ErroDeCarga):
        carregar_registros(diretorio, _ESQUEMA_PADRAO)


def test_arquivo_yaml_malformado_falha_nomeando_o_arquivo(tmp_path: Path) -> None:
    """YAML sintaticamente inválido é carga inválida, nomeando o arquivo
    culpado — nunca uma carga parcial dos arquivos restantes."""
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    caminho_malformado = diretorio / "bloco-01.yaml"
    caminho_malformado.write_text("QUESTIONARIO_VERSION: [not: closed", encoding="utf-8")

    with pytest.raises(ErroDeCarga) as excecao:
        carregar_registros(diretorio, _ESQUEMA_PADRAO)

    assert str(caminho_malformado) in str(excecao.value)


# ---------------------------------------------------------------------------
# T-213 — opção que abre campo (`abre_campo`), declarada no YAML.
# ---------------------------------------------------------------------------


def test_t213_opcao_com_abre_campo_data_e_convertida(tmp_path: Path) -> None:
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    pergunta = _pergunta_minima(
        "B1.01",
        opcoes=[
            {"rotulo": "Data", "valor_interno": None, "abre_campo": "DATA"},
            {"rotulo": "Outra", "valor_interno": "OUTRA"},
        ],
    )
    _escrever_arquivo(diretorio / "bloco-01.yaml", QUESTIONARIO_VERSION="1", perguntas=[pergunta])

    registro = carregar_registros(diretorio, _ESQUEMA_PADRAO).registros[0]

    assert registro.opcoes[0].abre_campo is TipoResposta.DATA
    assert registro.opcoes[1].abre_campo is None


def test_t213_abre_campo_desconhecido_e_recusado_na_carga(tmp_path: Path) -> None:
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    pergunta = _pergunta_minima(
        "B1.01", opcoes=[{"rotulo": "R$", "valor_interno": None, "abre_campo": "MOEDA"}]
    )
    _escrever_arquivo(diretorio / "bloco-01.yaml", QUESTIONARIO_VERSION="1", perguntas=[pergunta])

    with pytest.raises(ErroDeCarga) as excecao:
        carregar_registros(diretorio, _ESQUEMA_PADRAO)

    assert "B1.01" in str(excecao.value)


_IDS_COM_OPCAO_DE_DATA = ("B5.B04", "B5.B05B", "B7.15", "B8.14")
# Questão do especialista (T-213, Open Questions): valor e base/unidade numa
# só variável — nenhum campo até ser decidida.
_IDS_SEM_CAMPO_ATE_DECISAO = ("B5.D05A", "B7.13A", "B8.12A")


def test_t213_registro_real_marca_so_as_quatro_opcoes_de_data() -> None:
    registros = {r.ID: r for r in carregar_registros().registros}

    marcadas = {
        r.ID: [o.abre_campo for o in r.opcoes if o.abre_campo is not None]
        for r in registros.values()
        if any(o.abre_campo is not None for o in r.opcoes)
    }

    assert marcadas == {ID: [TipoResposta.DATA] for ID in _IDS_COM_OPCAO_DE_DATA}
    for ID in _IDS_SEM_CAMPO_ATE_DECISAO:
        assert all(o.abre_campo is None for o in registros[ID].opcoes), ID


# ---------------------------------------------------------------------------
# T-222/T-223 — campos opcionais da Rodada 9 (RF-79, RF-84, RF-91, RF-93).
# ---------------------------------------------------------------------------


def _carregar_uma(tmp_path: Path, pergunta: dict[str, object]) -> RegistroPergunta:
    diretorio = tmp_path / "registros"
    diretorio.mkdir()
    _escrever_arquivo(diretorio / "bloco-01.yaml", QUESTIONARIO_VERSION="1", perguntas=[pergunta])
    return carregar_registros(diretorio, _ESQUEMA_PADRAO).registros[0]


def _recusa(tmp_path: Path, pergunta: dict[str, object]) -> str:
    with pytest.raises(ErroDeCarga) as excecao:
        _carregar_uma(tmp_path, pergunta)
    return str(excecao.value)


def test_t222_registros_reais_carregam_com_os_campos_novos_em_padrao_neutro() -> None:
    """AC-38: os YAML atuais carregam sem edição; todo registro/opção que não
    declara um campo novo recebe o padrão neutro (nenhuma diferença de
    conteúdo) — comparado com o YAML bruto, arquivo a arquivo."""
    diretorio = _ESQUEMA_PADRAO.parent / "registros"
    brutos = {
        pergunta["ID"]: pergunta
        for caminho in diretorio.glob("*.yaml")
        for pergunta in yaml.safe_load(caminho.read_text(encoding="utf-8"))["perguntas"]
    }

    registros = carregar_registros(incluir_casos_de_prova=True).registros

    assert {r.ID for r in registros} == set(brutos)
    for registro in registros:
        bruto = brutos[registro.ID]
        if "painel" not in bruto:
            assert registro.painel is None, registro.ID
        if "indispensavel" not in bruto:
            assert registro.indispensavel is False, registro.ID
        if "faixa" not in bruto:
            assert registro.faixa is None, registro.ID
        for opcao, opcao_bruta in zip(registro.opcoes, bruto["opcoes"], strict=True):
            if "nivel_comprovacao" not in opcao_bruta:
                assert opcao.nivel_comprovacao is None, registro.ID
            if "nivel_comprovacao_se" not in opcao_bruta:
                assert opcao.nivel_comprovacao_se is None, registro.ID


def test_t223_campos_novos_carregam_com_o_valor_declarado(tmp_path: Path) -> None:
    pergunta = _pergunta_minima(
        "B1.01",
        opcoes=[
            {"rotulo": "Documento", "valor_interno": "DOC", "nivel_comprovacao": "COMPROVADO"},
            {
                "rotulo": "Outra",
                "valor_interno": "OUTRA",
                "nivel_comprovacao": "INFORMADO",
                "nivel_comprovacao_se": {
                    "condicao": {"tipo": "IGUAL", "variavel": "X", "valor": "S"},
                    "nivel": "COMPROVADO",
                },
            },
        ],
    )
    pergunta.update(
        painel="FOTOGRAFIA_DO_MES", indispensavel=True, faixa={"minimo": 0, "maximo": 100}
    )

    registro = _carregar_uma(tmp_path, pergunta)

    assert registro.painel == "FOTOGRAFIA_DO_MES"
    assert registro.indispensavel is True
    assert registro.faixa is not None
    assert (str(registro.faixa[0]), str(registro.faixa[1])) == ("0", "100")
    assert registro.opcoes[0].nivel_comprovacao is NIVEL_COMPROVACAO.COMPROVADO
    assert registro.opcoes[0].nivel_comprovacao_se is None
    se = registro.opcoes[1].nivel_comprovacao_se
    assert se == NivelCondicional(
        condicao=CondicaoIgual(variavel="X", valor="S"), nivel=NIVEL_COMPROVACAO.COMPROVADO
    )


def test_t223_sem_os_campos_novos_valem_os_padroes_neutros(tmp_path: Path) -> None:
    registro = _carregar_uma(
        tmp_path, _pergunta_minima("B1.01", opcoes=[{"rotulo": "A", "valor_interno": "A"}])
    )

    assert (registro.painel, registro.indispensavel, registro.faixa) == (None, False, None)
    assert registro.opcoes[0].nivel_comprovacao is None
    assert registro.opcoes[0].nivel_comprovacao_se is None


def test_t223_painel_desconhecido_e_recusado_nomeando_o_registro(tmp_path: Path) -> None:
    pergunta = _pergunta_minima("B1.01")
    pergunta["painel"] = "OUTRO_PAINEL"

    assert "B1.01" in _recusa(tmp_path, pergunta)


def test_t223_nivel_fora_do_enum_e_recusado_nomeando_o_registro(tmp_path: Path) -> None:
    pergunta = _pergunta_minima(
        "B1.01", opcoes=[{"rotulo": "A", "valor_interno": "A", "nivel_comprovacao": "NIVEL_4"}]
    )

    assert "B1.01" in _recusa(tmp_path, pergunta)


def test_t223_nivel_condicional_fora_do_enum_e_recusado(tmp_path: Path) -> None:
    pergunta = _pergunta_minima(
        "B1.01",
        opcoes=[
            {
                "rotulo": "A",
                "valor_interno": "A",
                "nivel_comprovacao": "INFORMADO",
                "nivel_comprovacao_se": {
                    "condicao": {"tipo": "IGUAL", "variavel": "X", "valor": "S"},
                    "nivel": "NIVEL_4",
                },
            }
        ],
    )

    assert "B1.01" in _recusa(tmp_path, pergunta)


def test_t223_faixa_com_minimo_maior_que_maximo_e_recusada(tmp_path: Path) -> None:
    pergunta = _pergunta_minima("B1.01")
    pergunta["faixa"] = {"minimo": 100, "maximo": 0}

    assert "B1.01" in _recusa(tmp_path, pergunta)


def test_t223_faixa_nao_numerica_e_recusada(tmp_path: Path) -> None:
    pergunta = _pergunta_minima("B1.01")
    pergunta["faixa"] = {"minimo": "zero", "maximo": 100}

    assert "B1.01" in _recusa(tmp_path, pergunta)


def test_t224_questionario_na_versao_1_0_3_e_b3_c00_com_painel() -> None:
    """RF-03/AC-38 (T-224, `OQ-52`): a canônica v1.0.3 é a versão única de
    todos os registros; `B3.C00` declara o painel da fotografia do mês e é o
    único registro que o faz."""
    colecao = carregar_registros(incluir_casos_de_prova=True)

    assert colecao.QUESTIONARIO_VERSION == "1.0.3"
    assert [r.ID for r in colecao.registros if r.painel is not None] == ["B3.C00"]
    assert next(r for r in colecao.registros if r.ID == "B3.C00").painel == "FOTOGRAFIA_DO_MES"


def _folhas(condicao: object) -> list[CondicaoIgual | CondicaoContem]:
    if isinstance(condicao, (CondicaoIgual, CondicaoContem)):
        return [condicao]
    if isinstance(condicao, (CondicaoE, CondicaoOu)):
        return [folha for termo in condicao.termos for folha in _folhas(termo)]
    if isinstance(condicao, CondicaoNao):
        return _folhas(condicao.termo)
    return []


def test_t284_condicao_sobre_selecao_compara_valor_interno_nunca_rotulo() -> None:
    """RF-05 (`T-284`): a seleção grava o `valor_interno`; condição que compara
    o RÓTULO nunca abre (`B5.D02` por documento em `B5.I01`)."""
    registros = carregar_registros().registros
    valores = {
        r.VARIAVEL_GRAVADA: {o.valor_interno for o in r.opcoes}
        for r in registros
        if r.tipo in (TipoResposta.SELECAO_UNICA, TipoResposta.SELECAO_MULTIPLA)
    }

    assert [
        (r.ID, folha.variavel, folha.valor)
        for r in registros
        for folha in _folhas(r.condicao_exibicao)
        if folha.variavel in valores and folha.valor not in valores[folha.variavel]
    ] == []
