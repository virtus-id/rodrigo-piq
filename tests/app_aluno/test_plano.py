"""Testes de `report/plano.py` e `report/templates/plano/plano.html` — a
redação canônica de `Q-03` em um único template (`RF-21`, `AC-14`, `AC-15`,
T-59) e a renderização da ordem a partir de um `SnapshotOrdem` real
(`RF-20`, `RF-22`, `AC-16`, `AC-17`, `AC-42`, T-60).

Cobre os dois critérios de aceite normativos de T-59:

1. `AC-14` — o título renderizado é exatamente "Sua ordem projetada de
   quitação" e o texto é exatamente o corpo de `Q-03`, caractere por
   caractere (igualdade de string, nunca `in`/substring).
2. `AC-15` — a palavra "projetada" aparece no HTML renderizado, e nenhuma das
   palavras "definitiva", "final" ou "fixa" (busca sem diferenciar
   maiúsculas/minúsculas) aparece qualificando a ordem.

Mais dois testes de estrutura, não normativos, mas exigidos pela tarefa:
a redação vive num único arquivo (`textos-canonicos.yaml`) e é a MESMA
carregada tanto pela leitura direta do YAML quanto pela função de apoio
`carregar_textos_canonicos` — não duas transcrições independentes.

E os quatro critérios de T-60, com um `SnapshotOrdem` REAL (produzido por
`engine.motor.calcular_plano` sobre a fixture de caso completo com DUAS
dívidas, `tests/app_aluno/fixtures/caso_completo.py`, T-53 — nunca fabricado
à mão):

1. `AC-17` — uma ordem com N dívidas exibe N posições, cada uma com sua
   `JUSTIFICATIVA_POSICAO`.
2. `AC-16` — `ENGINE_VERSION`/`PARAMETROS_VERSION` do snapshot aparecem na
   saída.
3. `AC-42` — nenhuma aritmética sobre campo do snapshot fora de
   `quantizar_exibicao` (verificado por AST sobre `report/plano.py`, mais a
   prova por igualdade de valor com o campo lido diretamente do snapshot).
4. Prazo e custo exibidos correspondem exatamente aos campos do snapshot
   (`Cenario.PRAZO_TOTAL`/`Cenario.CUSTO_FUTURO_TOTAL` do método
   recomendado), sem reformatação numérica própria.

REGRAS: `RF-20`, `RF-21`, `RF-22`, `AC-14`, `AC-15`, `AC-16`, `AC-17`, `AC-42`
"""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.respostas import RespostasCaso
from engine.motor import calcular_plano
from engine.precisao import quantizar_exibicao
from engine.snapshot import SnapshotOrdem
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from report.plano import (
    CAMINHO_TEXTOS_CANONICOS,
    ContextoPlano,
    carregar_textos_canonicos,
    montar_contexto_plano,
)
from tests.app_aluno.fixtures.caso_completo import (
    DATA_REFERENCIA,
    caso_completo,
    montar_respostas_caso,
)

_DIRETORIO_TEMPLATES_PLANO = (
    Path(__file__).resolve().parent.parent.parent / "report" / "templates" / "plano"
)

# Transcrição de Q-03 (specs/piq-app-spec.md) usada SÓ para comparação no
# teste — não é uma segunda fonte da redação: `report/plano.py` continua
# sendo a única leitura de `textos-canonicos.yaml` em código de produção.
_TITULO_Q03 = "Sua ordem projetada de quitação"
_CORPO_Q03 = (
    "Com os dados e condições atuais, o PIQ projeta a seguinte sequência de "
    "quitação. A ordem poderá ser recalculada se ocorrer alguma mudança "
    "material durante a execução."
)

_PALAVRAS_PROIBIDAS = ("definitiva", "final", "fixa")


def _renderizar_plano_html() -> str:
    ambiente = Environment(
        loader=FileSystemLoader(str(_DIRETORIO_TEMPLATES_PLANO)),
        autoescape=select_autoescape(["html"]),
    )
    template = ambiente.get_template("plano.html")
    textos = carregar_textos_canonicos()
    return template.render(titulo=textos.titulo, corpo=textos.corpo, ordem=[])


def test_ac14_titulo_e_corpo_carregados_sao_exatamente_q03() -> None:
    """AC-14: `carregar_textos_canonicos` devolve o título e o texto de
    `Q-03` caractere por caractere — igualdade exata de string."""
    textos = carregar_textos_canonicos()

    assert textos.titulo == _TITULO_Q03
    assert textos.corpo == _CORPO_Q03


def test_ac14_template_renderiza_titulo_e_corpo_exatos_de_q03() -> None:
    """AC-14: o HTML produzido por `plano.html` contém o título em `<title>`/
    `<h1>` e o corpo em `<p>`, exatamente como `Q-03` define — nenhuma
    paráfrase introduzida pelo template."""
    html = _renderizar_plano_html()

    assert f"<title>{_TITULO_Q03}</title>" in html
    assert f"<h1>{_TITULO_Q03}</h1>" in html
    assert f"<p>{_CORPO_Q03}</p>" in html


def test_ac15_palavra_projetada_aparece_e_nenhum_qualificador_proibido() -> None:
    """AC-15: "projetada" aparece no HTML renderizado; nenhuma das palavras
    "definitiva", "final" ou "fixa" qualifica a ordem — nem no título/corpo
    canônicos, nem em qualquer texto fixo do próprio template."""
    html = _renderizar_plano_html()
    html_minusculo = html.lower()

    assert "projetada" in html_minusculo

    for palavra_proibida in _PALAVRAS_PROIBIDAS:
        assert palavra_proibida not in html_minusculo, (
            f"'{palavra_proibida}' não deveria qualificar a ordem (AC-15), "
            f"mas apareceu no HTML renderizado"
        )


def test_redacao_canonica_vive_em_um_unico_arquivo() -> None:
    """A redação de `Q-03` está inteiramente em `textos-canonicos.yaml` — o
    template `plano.html` não contém o título nem o corpo como literal,
    apenas a referência de variável `{{ titulo }}`/`{{ corpo }}`."""
    conteudo_template = (_DIRETORIO_TEMPLATES_PLANO / "plano.html").read_text(encoding="utf-8")

    assert _TITULO_Q03 not in conteudo_template
    assert _CORPO_Q03 not in conteudo_template
    assert "{{ titulo }}" in conteudo_template
    assert "{{ corpo }}" in conteudo_template
    assert CAMINHO_TEXTOS_CANONICOS.is_file()


def test_nenhuma_variavel_nova_de_rotulo_visual_para_a_ordem() -> None:
    """Nenhum campo de rótulo visual foi criado para apresentar A ORDEM ao
    usuário (ex.: um `rotulo_ordem` paralelo): a variável interna permanece
    `ORDEM_QUITACAO`, fora do escopo deste módulo de apresentação (`Q-02`).

    **`rotulos_de_apoio` (`T-177`) não é isso.** Ele não renomeia a ordem
    nem cria um nome paralelo para ela — traduz os nomes de variável dos
    VALORES DE APOIO (`SALDO_DEVEDOR_ATUAL`, `TAXA_EFETIVA_MENSAL_
    NORMALIZADA`…) para o vocabulário do aluno, porque até então a tela
    mostrava o identificador do motor a um servidor público endividado. É
    redação ao aluno, e por isso vive no YAML, nunca em `.py` (`AC-37`)."""
    textos = carregar_textos_canonicos()

    assert {campo.name for campo in fields(textos)} == {
        "titulo",
        "corpo",
        "rotulos_de_apoio",
        "explicacao_da_posicao",
        "rotulos_de_pendencia",
    }
    # A ordem continua sem rótulo paralelo: nenhuma chave de apoio fala
    # sobre a ORDEM, só sobre campos de uma dívida.
    assert "ORDEM_QUITACAO" not in textos.rotulos_de_apoio


# ---------------------------------------------------------------------------
# T-60 — renderizar a ordem lendo campos do snapshot (RF-20, RF-22, AC-16,
# AC-17, AC-42). `_snapshot_real_com_duas_dividas` monta um SnapshotOrdem de
# VERDADE: fixture de caso completo (T-53) com DUAS fichas de dívida (via
# duas chamadas a `montar_respostas_caso`, cada uma sobrescrevendo só
# `DIVIDA_ID`/`valores_divida`) → EstadoFinanceiro → engine.motor.
# calcular_plano — nunca um SnapshotOrdem fabricado à mão.
# ---------------------------------------------------------------------------

_DIVIDA_ID_A = "D-T60-A"
_DIVIDA_ID_B = "D-T60-B"
_VERSAO_PARAMETROS_REAL = "1.0.1"


def _snapshot_real_com_duas_dividas() -> SnapshotOrdem:
    caso_a = caso_completo(DIVIDA_ID=_DIVIDA_ID_A)
    respostas_divida_b = montar_respostas_caso(
        valores_divida={
            "TIPO_DIVIDA": "CONSIGNADO",
            "SALDO_DEVEDOR_ATUAL": converter_para_dinheiro("8.000,00"),
            "PAGAMENTO_MENSAL_EFETIVO": converter_para_dinheiro("400,00"),
        },
        DIVIDA_ID=_DIVIDA_ID_B,
    )
    respostas = caso_a.respostas.respostas + respostas_divida_b.respostas
    respostas_caso = RespostasCaso(respostas=respostas)

    divida_a = montar_divida(respostas_caso, _DIVIDA_ID_A)
    divida_b = montar_divida(respostas_caso, _DIVIDA_ID_B)
    estado = montar_estado_financeiro(
        respostas_caso,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida_a, divida_b),
        **caso_a.parametros_externos,  # type: ignore[arg-type]
    )

    parametros = FonteParametrosArquivo().carregar(_VERSAO_PARAMETROS_REAL)
    return calcular_plano(estado, parametros)


def test_ac17_ordem_com_n_dividas_exibe_n_posicoes_cada_uma_com_justificativa() -> None:
    """AC-17: uma ordem com N dívidas (aqui, N=2) exibe N posições no
    contexto montado por `montar_contexto_plano`, cada uma com sua
    `JUSTIFICATIVA_POSICAO` não vazia — e o HTML renderizado contém as N
    seções.

    **`T-177`: duas justificativas, uma por audiência.** A técnica
    (`JUSTIFICATIVA_POSICAO`) continua íntegra no contexto, para o revisor
    (`AC-29`) e para auditoria; o HTML do ALUNO passa a mostrar
    `explicacao`, a redação em português. `AC-17` segue cumprido — toda
    posição explica por que está ali —, agora com o texto certo para quem
    lê."""
    snapshot = _snapshot_real_com_duas_dividas()
    textos = carregar_textos_canonicos()

    contexto = montar_contexto_plano(snapshot, textos)

    assert len(contexto.ordem) == len(snapshot.ORDEM_QUITACAO)
    assert len(contexto.ordem) == 2
    for posicao_do_contexto, posicao_do_snapshot in zip(
        contexto.ordem, snapshot.ORDEM_QUITACAO, strict=True
    ):
        assert posicao_do_contexto.DIVIDA_ID == posicao_do_snapshot.DIVIDA_ID
        assert (
            posicao_do_contexto.JUSTIFICATIVA_POSICAO
            == posicao_do_snapshot.JUSTIFICATIVA_POSICAO
        )
        assert posicao_do_contexto.JUSTIFICATIVA_POSICAO != ""
        # `T-177`: a redação ao aluno existe e NÃO é a técnica.
        assert posicao_do_contexto.explicacao != ""
        assert posicao_do_contexto.explicacao != posicao_do_contexto.JUSTIFICATIVA_POSICAO

    html = _renderizar_plano_html_com_contexto(contexto)
    for posicao_do_contexto, posicao_do_snapshot in zip(
        contexto.ordem, snapshot.ORDEM_QUITACAO, strict=True
    ):
        assert posicao_do_snapshot.DIVIDA_ID in html
        # Toda posição explica por que está ali — `AC-17`.
        assert posicao_do_contexto.explicacao in html
    # E o vocabulário do motor não vaza para o documento do aluno.
    assert "VALOR_RELEVANTE_PARA_QUITACAO" not in html
    assert "BOLA_DE_NEVE" not in html


def test_ac16_engine_version_e_parametros_version_do_snapshot_aparecem_na_saida() -> None:
    """AC-16: `ENGINE_VERSION`/`PARAMETROS_VERSION` do snapshot aparecem no
    contexto montado e no HTML renderizado — carimbo de versão de toda
    saída do motor (`V-03`)."""
    snapshot = _snapshot_real_com_duas_dividas()
    textos = carregar_textos_canonicos()

    contexto = montar_contexto_plano(snapshot, textos)

    assert contexto.ENGINE_VERSION == snapshot.ENGINE_VERSION
    assert contexto.PARAMETROS_VERSION == snapshot.PARAMETROS_VERSION
    assert contexto.ENGINE_VERSION != ""
    assert contexto.PARAMETROS_VERSION != ""

    html = _renderizar_plano_html_com_contexto(contexto)
    assert snapshot.ENGINE_VERSION in html
    assert snapshot.PARAMETROS_VERSION in html


def test_ac42_nenhuma_aritmetica_sobre_campo_do_snapshot_em_report_plano() -> None:
    """AC-42: `report/plano.py` não contém nenhuma operação aritmética
    (`+`, `-`, `*`, `/`) cujo operando derive de `snapshot`/`posicao_do_
    snapshot`/`cenario_recomendado` — a única exceção documentada é a
    CONTAGEM de itens (`len(...)`), que não é aritmética sobre valor
    financeiro. Verificado por AST sobre o próprio código-fonte do módulo,
    não por convenção de code review."""
    codigo_fonte = Path("report/plano.py").read_text(encoding="utf-8")
    arvore = ast.parse(codigo_fonte, filename="report/plano.py")

    nomes_de_snapshot = {"snapshot", "posicao_do_snapshot", "cenario_recomendado"}

    def _deriva_de_snapshot(no: ast.AST) -> bool:
        for sub in ast.walk(no):
            if isinstance(sub, ast.Name) and sub.id in nomes_de_snapshot:
                return True
        return False

    violacoes = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.BinOp)
        and isinstance(no.op, (ast.Add, ast.Sub, ast.Mult, ast.Div))
        and (_deriva_de_snapshot(no.left) or _deriva_de_snapshot(no.right))
    ]

    assert not violacoes, (
        "encontrada aritmética sobre campo do snapshot fora de quantizar_exibicao: "
        f"linhas {[getattr(v, 'lineno', '?') for v in violacoes]}"
    )

    # Prova positiva de que a função de fato lê o snapshot (o teste acima
    # não passaria trivialmente por ausência total de uso de `snapshot`).
    assert "def montar_contexto_plano(" in codigo_fonte
    assert "snapshot.ORDEM_QUITACAO" in codigo_fonte


def test_prazo_e_custo_exibidos_correspondem_exatamente_aos_campos_do_snapshot() -> None:
    """Prazo e custo exibidos são a leitura exata de `Cenario.PRAZO_TOTAL`/
    `Cenario.CUSTO_FUTURO_TOTAL` do método recomendado — sem recalcular
    prazo em meses nem custo total.

    **`T-177` mudou a APRESENTAÇÃO, não o valor.** Antes o contexto
    carregava `'33'` e `'73640.56'`, e o template prefixava "R$"/"meses";
    agora o servidor entrega `'33 meses'` e `'R$ 73.640,56'`, para que tela
    e PDF escrevam o mesmo (`RF-13`: a formatação de dinheiro é do
    servidor). O que este teste guarda continua sendo o mesmo: o NÚMERO
    exibido é o do snapshot, nunca um recalculado — por isso a asserção é
    sobre os dígitos, e não sobre a string inteira."""
    snapshot = _snapshot_real_com_duas_dividas()
    textos = carregar_textos_canonicos()
    cenario_recomendado = snapshot.cenarios[snapshot.METODO_RECOMENDADO_PIQ]

    contexto = montar_contexto_plano(snapshot, textos)

    assert contexto.PRAZO_TOTAL == f"{cenario_recomendado.PRAZO_TOTAL} meses"
    # Os dígitos do custo são os do snapshot; só o separador muda.
    custo_do_snapshot = str(quantizar_exibicao(cenario_recomendado.CUSTO_FUTURO_TOTAL))
    inteiro, _, centavos = custo_do_snapshot.partition(".")
    assert contexto.CUSTO_FUTURO_TOTAL.startswith("R$ ")
    assert contexto.CUSTO_FUTURO_TOTAL.endswith(f",{centavos}")
    assert inteiro in contexto.CUSTO_FUTURO_TOTAL.replace(".", "")

    html = _renderizar_plano_html_com_contexto(contexto)
    assert contexto.PRAZO_TOTAL in html
    assert contexto.CUSTO_FUTURO_TOTAL in html
    # O template não prefixa mais — senão sairia "R$ R$ 73.640,56".
    assert "R$ R$" not in html


def _renderizar_plano_html_com_contexto(contexto: ContextoPlano) -> str:
    ambiente = Environment(
        loader=FileSystemLoader(str(_DIRETORIO_TEMPLATES_PLANO)),
        autoescape=select_autoescape(["html"]),
    )
    template = ambiente.get_template("plano.html")
    return template.render(
        titulo=contexto.titulo,
        corpo=contexto.corpo,
        ordem=contexto.ordem,
        PRAZO_TOTAL=contexto.PRAZO_TOTAL,
        CUSTO_FUTURO_TOTAL=contexto.CUSTO_FUTURO_TOTAL,
        ENGINE_VERSION=contexto.ENGINE_VERSION,
        PARAMETROS_VERSION=contexto.PARAMETROS_VERSION,
    )
