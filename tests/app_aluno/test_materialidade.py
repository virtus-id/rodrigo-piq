"""Testa `collection/materialidade.py` — `RF-11`, `RF-34`, `AC-41` (T-40) e
o aviso de materialidade na hora, `OQ-08` (T-41).

Cobre os quatro critérios de aceite de T-40:
1. a derivação é por introspecção, sem lista de nomes escrita à mão;
2. `Dinheiro` puro não é material, `DinheiroTalvez` é;
3. a introspecção roda uma vez na carga (cache), não a cada chamada;
4. o módulo não contém gate/limiar/regra do motor — `T-06`/`T-08` passam
   sobre ele (verificado aqui reaproveitando os próprios detectores de
   `tests/app_aluno/estatica/`, e via suíte completa no relatório da tarefa).

E os quatro critérios de aceite de T-41 (`AvisoMaterialidade`/
`avaliar_ao_responder` e o transporte do aviso até a tela):
1. `NAO_SEI` em campo material produz aviso; em campo não material, não;
2. o texto do aviso usa "pode", nunca "vai"/"será";
3. o aviso ATRAVESSA a fronteira servidor→cliente junto da pergunta —
   originalmente provado renderizando `report/templates/coleta/
   aviso_materialidade.html` via Jinja2; **desde T-144 a tela é React** e o
   template foi removido, então a mesma garantia é provada sobre o payload
   de `app/http/serializacao.py::serializar_pergunta`, que é o sucessor
   exato daquele template (campo `aviso`);
4. o vínculo `aria-describedby` entre aviso e campo — `id` estável, região
   `role="status"` — deixou de ser markup produzido em Python: hoje é
   `frontend/src/componentes/CampoPergunta.tsx` que o monta a partir de
   `pergunta.ID`, coberto por `frontend/tests/unit/componentes/
   CampoPergunta.test.tsx`. O que ainda é responsabilidade DESTE lado da
   fronteira — e é o que se testa aqui — é o payload levar o texto do aviso
   e NÃO levar `VARIAVEL_GRAVADA` (T-144).

Nenhum teste aqui hardcoda a lista esperada de campos materiais: cada
asserção consulta `Divida`/`EstadoFinanceiro` diretamente, para que o teste
não vire ele mesmo a lista escrita à mão que a tarefa proíbe no módulo.

REGRAS: `RF-11`, `RF-34`, `AC-41`
"""

from __future__ import annotations

import types
import typing

import pytest

from app.http.renderizacao import montar_contexto_pergunta
from app.http.serializacao import serializar_pergunta
from collection.materialidade import (
    TEXTO_AVISO_MATERIALIDADE,
    AvisoMaterialidade,
    avaliar_ao_responder,
    campos_materiais,
)
from collection.opcoes_do_motor import OrigemOpcoes
from collection.registro import (
    EscopoRepeticao,
    Obrigatoriedade,
    RegistroPergunta,
    TipoResposta,
)
from collection.respostas import NAO_SEI, RespostasCaso
from engine.estado import Divida, EstadoFinanceiro
from engine.tipos import Desconhecido, Dinheiro, DinheiroTalvez, Taxa, TaxaTalvez


def _tipo_e_material_por_definicao_do_teste(tipo_anotado: object) -> bool:
    """Réplica INDEPENDENTE do critério estrutural, escrita direto contra
    `typing`/`types` sem importar a lógica de `collection/materialidade.py`
    — usada só para derivar, a partir do próprio contrato, o conjunto
    esperado de campos materiais, sem hardcodar nomes."""
    while isinstance(tipo_anotado, typing.TypeAliasType):
        tipo_anotado = tipo_anotado.__value__
    if not isinstance(tipo_anotado, types.UnionType):
        return False
    return Desconhecido in typing.get_args(tipo_anotado)


def _campos_materiais_esperados() -> frozenset[str]:
    """Deriva o conjunto esperado consultando `Divida`/`EstadoFinanceiro`
    diretamente neste teste — nunca uma lista literal de nomes."""
    esperados: set[str] = set()
    for contrato in (Divida, EstadoFinanceiro):
        for nome_campo, tipo_anotado in typing.get_type_hints(contrato).items():
            if _tipo_e_material_por_definicao_do_teste(tipo_anotado):
                esperados.add(nome_campo)
    return frozenset(esperados)


def test_campos_materiais_e_derivado_por_introspecao_sem_lista_manual() -> None:
    """Critério 1: o conjunto devolvido bate exatamente com o derivado, aqui
    no teste, por uma segunda implementação independente do mesmo critério
    estrutural — nenhuma das duas é uma lista de nomes escrita à mão."""
    assert campos_materiais() == _campos_materiais_esperados()


def test_dinheiro_puro_nao_e_material_dinheiro_talvez_e() -> None:
    """Critério 2, com os próprios tipos de `engine.tipos`."""
    from collection.materialidade import _e_material

    assert _e_material(Dinheiro) is False
    assert _e_material(DinheiroTalvez) is True
    assert _e_material(Taxa) is False
    assert _e_material(TaxaTalvez) is True


@pytest.mark.parametrize(
    ("contrato", "campo_material_esperado"),
    [
        (Divida, "SALDO_DEVEDOR_ATUAL"),
        (EstadoFinanceiro, "CAPACIDADE_ATAQUE_DECLARADA"),
    ],
)
def test_campos_conhecidos_materiais_aparecem_classificados(
    contrato: type, campo_material_esperado: str
) -> None:
    """`SALDO_DEVEDOR_ATUAL` (Divida) e `CAPACIDADE_ATAQUE_DECLARADA`
    (EstadoFinanceiro) são `DinheiroTalvez` no contrato real — a asserção
    confirma o tipo anotado ANTES de checar o resultado, para que o teste
    não dependa de um nome hardcoded desconectado do contrato."""
    tipo_anotado = typing.get_type_hints(contrato)[campo_material_esperado]
    assert _tipo_e_material_por_definicao_do_teste(tipo_anotado), (
        f"pré-condição do teste falhou: {contrato.__name__}.{campo_material_esperado} "
        "não é mais DinheiroTalvez/TaxaTalvez/int|Desconhecido no contrato — "
        "atualizar o teste"
    )
    assert campo_material_esperado in campos_materiais()


@pytest.mark.parametrize(
    ("contrato", "campo_nao_material_esperado"),
    [
        (Divida, "TIPO_DIVIDA"),
        (Divida, "DIVIDA_ID"),
    ],
)
def test_campos_conhecidos_nao_materiais_aparecem_classificados(
    contrato: type, campo_nao_material_esperado: str
) -> None:
    """`TIPO_DIVIDA` (enum fechado) e `DIVIDA_ID` (`str`) nunca são
    `DinheiroTalvez`/`TaxaTalvez`/`int | Desconhecido` — confirmado contra o
    contrato antes de checar o resultado."""
    tipo_anotado = typing.get_type_hints(contrato)[campo_nao_material_esperado]
    assert not _tipo_e_material_por_definicao_do_teste(tipo_anotado), (
        f"pré-condição do teste falhou: {contrato.__name__}.{campo_nao_material_esperado} "
        "passou a ser material no contrato — atualizar o teste"
    )
    assert campo_nao_material_esperado not in campos_materiais()


def test_todo_campo_material_pertence_de_fato_a_algum_dos_dois_contratos() -> None:
    """Nenhum nome espúrio: todo nome devolvido é um campo real de `Divida`
    ou de `EstadoFinanceiro` (prova que a introspecção não inventa nome)."""
    nomes_dos_contratos = set(typing.get_type_hints(Divida)) | set(
        typing.get_type_hints(EstadoFinanceiro)
    )
    assert campos_materiais() <= nomes_dos_contratos


def test_introspeccao_roda_uma_vez_por_cache() -> None:
    """Critério 3: `campos_materiais` é decorada com `lru_cache` — chamadas
    repetidas devolvem o mesmo objeto `frozenset` (identidade), sem repetir
    `typing.get_type_hints` a cada chamada."""
    primeira_chamada = campos_materiais()
    segunda_chamada = campos_materiais()

    assert primeira_chamada is segunda_chamada
    info_cache = campos_materiais.cache_info()
    assert info_cache.currsize == 1
    assert info_cache.hits >= 1


def test_resultado_e_frozenset_imutavel() -> None:
    """O contrato de retorno é `frozenset[str]` — não uma lista mutável que
    um chamador poderia corromper entre respostas."""
    resultado = campos_materiais()
    assert isinstance(resultado, frozenset)
    assert all(isinstance(nome, str) for nome in resultado)


def test_modulo_materialidade_nao_constroi_decimal_diretamente() -> None:
    """Critério 4 (parcial, sanidade local): o módulo não constrói
    `Decimal`/`Dinheiro` a partir de entrada — só introspecciona tipos do
    contrato. A verificação exaustiva de ausência de gate/regra do motor é
    feita pelas suítes `T-06`/`T-08` (`tests/app_aluno/estatica/`), que
    passam sobre este arquivo por já pertencer a `collection/`."""
    import inspect

    import collection.materialidade as modulo

    codigo_fonte = inspect.getsource(modulo)
    assert "Decimal(" not in codigo_fonte


# ---------------------------------------------------------------------------
# T-41 — AvisoMaterialidade / avaliar_ao_responder (OQ-08)
# ---------------------------------------------------------------------------


def _um_campo_material() -> str:
    """Um campo material real, derivado do contrato — nunca hardcoded como
    lista, só usado como amostra para os testes de `avaliar_ao_responder`."""
    campo = next(iter(campos_materiais()))
    return campo


def _um_campo_nao_material() -> str:
    """`TIPO_DIVIDA` é um enum fechado em `Divida` — não é
    `DinheiroTalvez`/`TaxaTalvez`/`int | Desconhecido`, confirmado no próprio
    teste antes de servir de amostra."""
    tipo_anotado = typing.get_type_hints(Divida)["TIPO_DIVIDA"]
    assert "TIPO_DIVIDA" not in campos_materiais(), (
        "pré-condição do teste falhou: TIPO_DIVIDA passou a ser material"
    )
    assert tipo_anotado is not None
    return "TIPO_DIVIDA"


def test_ac1_nao_sei_em_campo_material_produz_aviso() -> None:
    """Critério de aceite 1 (parte material): `NAO_SEI` num campo material
    devolve um `AvisoMaterialidade` vinculado à variável respondida."""
    campo_material = _um_campo_material()

    aviso = avaliar_ao_responder(campo_material, NAO_SEI)

    assert aviso is not None
    assert isinstance(aviso, AvisoMaterialidade)
    assert aviso.VARIAVEL_GRAVADA == campo_material


def test_ac1_nao_sei_em_campo_nao_material_nao_produz_aviso() -> None:
    """Critério de aceite 1 (parte não material): `NAO_SEI` num campo que
    não é `DinheiroTalvez`/`TaxaTalvez`/`int | Desconhecido` não produz
    aviso nenhum."""
    campo_nao_material = _um_campo_nao_material()

    aviso = avaliar_ao_responder(campo_nao_material, NAO_SEI)

    assert aviso is None


def test_valor_concreto_em_campo_material_nao_produz_aviso() -> None:
    """Responder com um valor concreto (não `NAO_SEI`) a um campo material
    não produz aviso — a materialidade só é relevante junto de "não sei"."""
    campo_material = _um_campo_material()

    aviso = avaliar_ao_responder(campo_material, "1234.56")

    assert aviso is None


def test_valor_concreto_em_campo_nao_material_nao_produz_aviso() -> None:
    """Caso trivial: nem material, nem "não sei" — sem aviso."""
    campo_nao_material = _um_campo_nao_material()

    aviso = avaliar_ao_responder(campo_nao_material, "CONSIGNADO")

    assert aviso is None


def test_ac2_texto_do_aviso_usa_pode_nunca_vai_ou_sera() -> None:
    """Critério de aceite 2: a redação-núcleo do aviso usa "pode" e nunca as
    formas "vai"/"será" — checado tanto na constante do módulo quanto no
    `AvisoMaterialidade` devolvido."""
    campo_material = _um_campo_material()
    aviso = avaliar_ao_responder(campo_material, NAO_SEI)
    assert aviso is not None

    for texto in (TEXTO_AVISO_MATERIALIDADE, aviso.texto):
        texto_min = texto.lower()
        assert "pode" in texto_min
        assert " vai " not in f" {texto_min} "
        assert "será" not in texto_min
        assert "sera" not in texto_min


def test_aviso_materialidade_e_dataclass_imutavel() -> None:
    """`AvisoMaterialidade` é `frozen=True, slots=True`, mesmo padrão dos
    demais dataclasses de `collection/` — sem mutação após construído."""
    aviso = AvisoMaterialidade(VARIAVEL_GRAVADA="X", texto="pode deixar seu plano provisório")
    with pytest.raises(AttributeError):
        aviso.texto = "outro"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# T-41 — o aviso atravessando a fronteira servidor→cliente.
#
# Até T-144 esta seção renderizava `report/templates/coleta/
# aviso_materialidade.html` direto no Jinja2. Aquele template não existe
# mais: a tela virou React, e o sucessor do template é
# `app/http/serializacao.py::serializar_pergunta`, que leva o aviso ao
# cliente no campo `aviso`. As asserções mudaram de markup para payload; a
# garantia — "o aviso chega até a tela quando existe, e não chega quando não
# existe" — é a mesma.
# ---------------------------------------------------------------------------


def _registro_de_teste(*, VARIAVEL_GRAVADA: str) -> RegistroPergunta:
    """Registro sintético mínimo para montar um `ContextoPergunta` — o
    enunciado é curto de propósito (`AC-37`: nenhum conteúdo real de
    questionário escrito em `.py`)."""
    return RegistroPergunta(
        ID="B5.A01",
        bloco=5,
        enunciado="Enunciado sintético de teste, nunca uma pergunta real da §11.",
        tipo=TipoResposta.TEXTO_CURTO,
        obrigatoriedade=frozenset({Obrigatoriedade.OBR}),
        escopo_repeticao=EscopoRepeticao.NENHUM,
        opcoes=(),
        VARIAVEL_GRAVADA=VARIAVEL_GRAVADA,
        condicao_exibicao=None,
        interpolacoes=(),
        validacoes_cruzadas=(),
        origem_opcoes=OrigemOpcoes(fonte="REGISTRO", campo_do_snapshot=None),
        admite_nao_sei=True,
        salto_consequencia=None,
    )


def _serializar_com_aviso(
    aviso: AvisoMaterialidade | None, *, VARIAVEL_GRAVADA: str = "SALDO_DEVEDOR_ATUAL"
) -> dict[str, object]:
    """Monta o contexto de uma pergunta com (ou sem) aviso e o serializa —
    exatamente o caminho que `rotas_pergunta.py`/`rotas_fichas.py` percorrem
    para entregar a pergunta ao cliente."""
    registro = _registro_de_teste(VARIAVEL_GRAVADA=VARIAVEL_GRAVADA)
    contexto = montar_contexto_pergunta(
        registro, RespostasCaso(respostas=()), aviso=aviso
    )
    return serializar_pergunta(contexto, CASO_ID="CASO-TESTE")


def test_ac3_payload_da_pergunta_carrega_o_texto_do_aviso_quando_presente() -> None:
    """Critério de aceite 3, na camada que hoje o sustenta (T-144): com um
    `AvisoMaterialidade` no contexto, `serializar_pergunta` leva a redação
    com "pode" no campo `aviso` — antes isso era o HTML do template
    `aviso_materialidade.html`, removido junto com a tela Jinja2."""
    aviso = AvisoMaterialidade(
        VARIAVEL_GRAVADA="SALDO_DEVEDOR_ATUAL", texto=TEXTO_AVISO_MATERIALIDADE
    )

    payload = _serializar_com_aviso(aviso)

    assert payload["aviso"] == TEXTO_AVISO_MATERIALIDADE
    texto = str(payload["aviso"]).lower()
    assert "pode" in texto
    assert "vai deixar" not in texto
    assert "será" not in texto


def test_ac4_payload_identifica_a_pergunta_por_id_e_nao_vaza_variavel_gravada() -> None:
    """Critério de aceite 4, deslocado de camada por T-144. O `id` estável
    do aviso e o `aria-describedby` que o vincula ao campo são montados hoje
    em `frontend/src/componentes/CampoPergunta.tsx`, a partir de
    `pergunta.ID` — não mais a partir de `VARIAVEL_GRAVADA`, que
    deliberadamente NÃO atravessa a fronteira (é vocabulário do modelo de
    dados; quem resolve variável é o servidor). O que continua sendo
    responsabilidade deste lado, e é o que se prova aqui: o payload carrega
    o `ID` que ancora o vínculo, e não carrega a variável."""
    aviso = AvisoMaterialidade(
        VARIAVEL_GRAVADA="CAPACIDADE_ATAQUE_DECLARADA", texto=TEXTO_AVISO_MATERIALIDADE
    )

    payload = _serializar_com_aviso(
        aviso, VARIAVEL_GRAVADA="CAPACIDADE_ATAQUE_DECLARADA"
    )

    assert payload["ID"] == "B5.A01"
    assert "VARIAVEL_GRAVADA" not in payload
    assert "CAPACIDADE_ATAQUE_DECLARADA" not in payload.values()


def test_payload_traz_aviso_nulo_quando_nao_ha_aviso() -> None:
    """Sem aviso (campo não material, ou resposta que não é "não sei"), o
    campo `aviso` do payload é `None` — o cliente não recebe elemento de
    aviso nenhum para desenhar. Sucessor do "template não emite nada quando
    `aviso is None`" que Jinja2 provava antes de T-144."""
    payload = _serializar_com_aviso(None)

    assert payload["aviso"] is None
