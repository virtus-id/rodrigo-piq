"""Lado B de `AC-17`: alterar a fonte externa de parâmetros muda o resultado —
RF-13, `AC-17` · T-56.

`AC-17`: "Dado o código-fonte do motor, quando for auditado, então nenhum
valor `P_*` aparece escrito nele, e alterar o valor na fonte externa muda o
resultado sem recompilar regra." `tests/estatica/test_nenhum_parametro_no_
codigo.py` cobre o lado A (estático: nenhum `P_*` aparece escrito em
`engine/`). Este módulo cobre o lado B (dinâmico): rodar a MESMA carteira
(`GAB-C`) com o MESMO método (Híbrido) muda de resultado quando só a fonte de
parâmetros muda — prova de que o motor de fato LÊ `P_MESES_VITORIA_RAPIDA` em
tempo de execução, em vez de tê-lo hardcoded ou cacheado incorretamente.

Cenário
-----------------------------------------------------------------------------
`tests/gabaritos/test_gabarito_c_hibrido.py` (T-55) já prova que `GAB-C` com
os parâmetros REAIS de `parameters/parametros-1.0.1.json`
(`P_MESES_VITORIA_RAPIDA = 3`) produz `CENARIO_HIBRIDO = CALCULAVEL` com
`D* = D003` (D003 sobrevive às três tolerâncias cumulativas de `H-03`, ver
`engine/metodos/hibrido.py::_e_candidata_valida`). Este teste roda a MESMA
carteira, o MESMO `calcular_diagnostico`/`escolher_D_ESTRELA`/
`criar_selecionar_alvo_hibrido`, trocando SOMENTE a fonte de parâmetros por
uma cópia em diretório temporário onde `P_MESES_VITORIA_RAPIDA = 0` — com
essa tolerância zerada, `MESES_PRIMEIRA_VITORIA(CENARIO_HIBRIDO_D) <= 0` é
impossível de satisfazer para qualquer candidata real (nenhuma dívida quita
no mês zero), então NENHUMA candidata sobrevive a `H-03` e o resultado
esperado é `CENARIO_HIBRIDO = NAO_APLICAVEL` — o oposto do resultado normal
que T-55 provou.

Abordagem da fonte alternativa (decisão de implementação desta tarefa)
-----------------------------------------------------------------------------
Em vez de versionar um segundo arquivo `parametros-*.json` estático em
`tests/fixtures/` (que duplicaria os 38 parâmetros e divergiria
silenciosamente do arquivo real a cada atualização de
`parameters/parametros-1.0.1.json`), a fonte alternativa é GERADA em tempo de
teste: lê o JSON real como texto, faz o parse, sobrescreve o único campo
`P_MESES_VITORIA_RAPIDA` para `0`, e grava a cópia em `tmp_path` (fixture do
pytest, diretório temporário isolado por teste). `FonteParametrosArquivo`
aceita `diretorio_parametros`/`caminho_esquema` injetáveis exatamente para
este cenário (ver `persistencia/arquivo/fonte_parametros.py`, docstring do
`__init__`) — o esquema real (`parameters/esquema-parametros.json`) é
reaproveitado sem cópia, já que ele não muda: só o VALOR do parâmetro muda,
não a lista de parâmetros válidos.

Isso satisfaz o critério de aceite 1 ("o teste altera apenas o arquivo/fonte
de parâmetros, sem tocar em nenhum código de `engine/`"): nenhuma linha de
`engine/` é tocada — a única coisa que muda entre a execução "normal" (T-55)
e esta é QUAL arquivo `FonteParametrosArquivo.carregar()` lê.

REGRAS: RF-13, AC-17
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from engine.diagnostico import calcular_diagnostico
from engine.estado import Divida, EstadoFinanceiro
from engine.metodos.hibrido import criar_selecionar_alvo_hibrido
from engine.tipos import CLASSIFICACAO_CENARIO, DESCONHECIDO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from tests.conftest import assertar_exato
from tests.fixtures.carregar import carregar_gab_c

_RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent
_ARQUIVO_PARAMETROS_REAL = _RAIZ_PROJETO / "parameters" / "parametros-1.0.1.json"
_ESQUEMA_PARAMETROS_REAL = _RAIZ_PROJETO / "parameters" / "esquema-parametros.json"


def _inventario(estado: EstadoFinanceiro) -> dict[str, Divida]:
    """Mesmo padrão de `tests/gabaritos/test_gabarito_c_hibrido.py`."""
    inventario: dict[str, Divida] = {}
    for divida in estado.dividas:
        assert divida.SALDO_DEVEDOR_ATUAL is not DESCONHECIDO
        inventario[divida.DIVIDA_ID] = divida
    return inventario


def _gerar_fonte_alternativa_p_meses_vitoria_rapida_zero(tmp_path: Path) -> FonteParametrosArquivo:
    """Copia `parameters/parametros-1.0.1.json` para `tmp_path`, sobrescrevendo
    SOMENTE `P_MESES_VITORIA_RAPIDA` para `0`. O arquivo original nunca é
    aberto em modo de escrita — só lido — então esta função nunca modifica
    `parameters/parametros-1.0.1.json` real (critério de aceite 1).
    """
    with _ARQUIVO_PARAMETROS_REAL.open(encoding="utf-8") as f:
        bruto = json.load(f)  # parse simples: só reescrevemos um inteiro pequeno

    assert bruto["P_MESES_VITORIA_RAPIDA"] == 3, (
        "pressuposto do teste: o arquivo real tem P_MESES_VITORIA_RAPIDA = 3 "
        f"antes da alteração, obteve {bruto['P_MESES_VITORIA_RAPIDA']!r} — "
        "se este valor mudou na fonte real, o teste precisa ser revisado"
    )
    bruto["P_MESES_VITORIA_RAPIDA"] = 0

    diretorio_alternativo = tmp_path / "parameters"
    diretorio_alternativo.mkdir()
    caminho_alternativo = diretorio_alternativo / "parametros-1.0.1.json"
    conteudo_alternativo = json.dumps(bruto, ensure_ascii=False, indent=2)
    caminho_alternativo.write_text(conteudo_alternativo, encoding="utf-8")

    return FonteParametrosArquivo(
        diretorio_parametros=diretorio_alternativo,
        caminho_esquema=_ESQUEMA_PARAMETROS_REAL,
    )


def test_arquivo_real_permanece_intocado_apos_gerar_fonte_alternativa(tmp_path: Path) -> None:
    """Prova auxiliar do critério de aceite 1: gerar a fonte alternativa não
    escreve no arquivo real — o conteúdo de `parameters/parametros-1.0.1.json`
    antes e depois de `_gerar_fonte_alternativa_p_meses_vitoria_rapida_zero` é
    byte a byte idêntico."""
    conteudo_antes = _ARQUIVO_PARAMETROS_REAL.read_bytes()

    _gerar_fonte_alternativa_p_meses_vitoria_rapida_zero(tmp_path)

    conteudo_depois = _ARQUIVO_PARAMETROS_REAL.read_bytes()
    assertar_exato(conteudo_depois, conteudo_antes)


def test_parametro_externo_muda_resultado(tmp_path: Path) -> None:
    """`AC-17` (lado B): `GAB-C` com o Híbrido, fonte alternativa com
    `P_MESES_VITORIA_RAPIDA = 0` — nenhuma candidata sobrevive a `H-03`
    (`MESES_PRIMEIRA_VITORIA(CENARIO_HIBRIDO_D) <= 0` é impossível), então
    `CENARIO_HIBRIDO` deve virar `NAO_APLICAVEL`, diferente do `CALCULAVEL`
    (com `D* = D003`) que a mesma carteira produz com os parâmetros reais
    (`tests/gabaritos/test_gabarito_c_hibrido.py`, T-55).
    """
    fonte_alternativa = _gerar_fonte_alternativa_p_meses_vitoria_rapida_zero(tmp_path)
    parametros_alterados = fonte_alternativa.carregar("1.0.1")

    # Critério de aceite 3: confirma que a leitura de volta é o valor
    # alterado de verdade (0), não um default de fallback — `Parametros.
    # numero()` nunca tem default (engine/parametros.py, KeyError se
    # ausente), então este `assertar_exato` só passa se a fonte externa foi
    # realmente lida.
    assertar_exato(parametros_alterados.numero("P_MESES_VITORIA_RAPIDA"), Decimal(0))

    estado = carregar_gab_c()
    dividas = _inventario(estado)
    diagnostico = calcular_diagnostico(estado, parametros_alterados)

    resultado = criar_selecionar_alvo_hibrido(estado, dividas, diagnostico, parametros_alterados)

    # Critério de aceite 2/4: o resultado muda de CALCULAVEL (T-55, D003) para
    # NAO_APLICAVEL — comparação com tolerância zero.
    assertar_exato(resultado.classificacao, CLASSIFICACAO_CENARIO.NAO_APLICAVEL)
    assert resultado.selecionar_alvo is None, (
        "H-08/EC-03: NAO_APLICAVEL nunca vem acompanhado de uma SelecionarAlvo"
    )


@pytest.mark.gabarito
def test_parametro_normal_ainda_produz_calculavel_como_referencia(tmp_path: Path) -> None:
    """Contraprova de controle: a MESMA fonte alternativa, mas SEM a
    alteração (cópia fiel do arquivo real, `P_MESES_VITORIA_RAPIDA = 3`),
    reproduz o `CALCULAVEL` de T-55 — isola que a mudança de resultado do
    teste principal vem exclusivamente do valor do parâmetro, não de algum
    outro efeito colateral do mecanismo de cópia (diretório diferente,
    esquema diferente etc.).
    """
    diretorio_alternativo = tmp_path / "parameters"
    diretorio_alternativo.mkdir()
    caminho_copia_fiel = diretorio_alternativo / "parametros-1.0.1.json"
    caminho_copia_fiel.write_text(
        _ARQUIVO_PARAMETROS_REAL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    fonte_copia_fiel = FonteParametrosArquivo(
        diretorio_parametros=diretorio_alternativo,
        caminho_esquema=_ESQUEMA_PARAMETROS_REAL,
    )
    parametros_copia_fiel = fonte_copia_fiel.carregar("1.0.1")
    assertar_exato(parametros_copia_fiel.numero("P_MESES_VITORIA_RAPIDA"), Decimal(3))

    estado = carregar_gab_c()
    dividas = _inventario(estado)
    diagnostico = calcular_diagnostico(estado, parametros_copia_fiel)

    resultado = criar_selecionar_alvo_hibrido(estado, dividas, diagnostico, parametros_copia_fiel)

    assertar_exato(resultado.classificacao, CLASSIFICACAO_CENARIO.CALCULAVEL)
    assert resultado.selecionar_alvo is not None
