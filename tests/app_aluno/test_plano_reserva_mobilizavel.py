"""Testes da exibição de `RESERVA_MOBILIZAVEL` ao aluno — `RF-43`, `AC-70`,
`EC-18` (T-117): `report/plano.py::_reserva_mobilizavel`/
`ContextoReservaMobilizavel` e `report/templates/plano/
reserva_mobilizavel.html`.

**O que estes testes provam, e o que deliberadamente NÃO provam.** Quando o
aluno responde que prefere decidir depois quanto da reserva quer usar
(`B4.03 = TALVEZ`, `B4.03A = "Não sei."`), a Regra 3 da §13.1 faz
`Diagnostico.RESERVA_MOBILIZAVEL` valer `DESCONHECIDO` — e a §13.1 é
enfática: *"o estado DESCONHECIDA não é convertido silenciosamente em zero
como informação. A engine registra a pendência."* Exibir `R$ 0,00` aí seria
mentir para o aluno: "ainda não decidi" e "não tenho nada" são coisas
diferentes, e a segunda leitura poderia levá-lo a achar que não tem reserva
alguma.

A **redação** que o aluno lê nesse estado é `OQ-21`, **ABERTA** — insumo do
especialista do método. Por isso **nenhuma asserção deste arquivo depende do
texto em português do estado pendente**: as três asserções de `AC-70` são
estruturais (não exibe `R$ 0,00`, não omite o item, nenhum caminho levanta
exceção), e trocar a redação quando `OQ-21` for respondida não quebra
nenhum destes testes. É exatamente esse recorte que torna `RF-43` testável
hoje, com a redação ainda em aberto, e que permite declarar a cobertura como
**parcial** com honestidade.

Os dois snapshots são produzidos pelo **motor REAL** (`engine.motor.
calcular_plano` sobre `FonteParametrosArquivo`, os 45 parâmetros lidos de
`parameters/` e nunca escritos no teste, `sdd.config.md` §4) — mesmo padrão
de `tests/app_aluno/test_montagem_bloco_04.py::
TestT114IntegracaoComOMotorReal` (T-114) e de
`tests/app_aluno/test_plano_ec07_ec08_ec09.py` (T-62). Nenhum `Diagnostico`
fabricado à mão: o valor precisa chegar à camada de exibição pelo mesmo
caminho que chega em produção, senão o teste provaria o dublê e não o
sistema.

`TALVEZ` é deliberado e não intercambiável no caso desconhecido: com `NAO` a
Regra 1 da §13.1 zeraria antes de a Regra 3 ser alcançada, e o teste passaria
pelo motivo errado — provando zero em vez de `DESCONHECIDO`.

A renderização passa por `report/pdf.py::renderizar_html_do_plano`, a ÚNICA
função de renderização de `plano.html` compartilhada por tela e PDF — nunca
uma segunda configuração de Jinja2 montada aqui, que poderia divergir do que
o aluno realmente vê.

REGRAS: `RF-43`, `AC-70`, `EC-18`
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.montagem.conversao import converter_para_dinheiro
from app.montagem.estado import montar_divida, montar_estado_financeiro
from collection.respostas import NAO_SEI
from engine.motor import calcular_plano
from engine.snapshot import SnapshotOrdem
from engine.tipos import DESCONHECIDO
from persistencia.arquivo.fonte_parametros import FonteParametrosArquivo
from report.pdf import renderizar_html_do_plano
from report.plano import carregar_textos_canonicos, montar_contexto_plano
from tests.app_aluno.fixtures.caso_completo import DATA_REFERENCIA, caso_completo

_PARAMETROS_VERSAO = "1.0.1"

# O texto que NUNCA pode aparecer no bloco da reserva quando o estado é
# `DESCONHECIDO` (§13.1). Escrito como padrão tolerante a separador para que
# `R$ 0,00`, `R$0,00` e `R$  0,00` sejam todos pegos — a proibição é sobre o
# VALOR mostrado ao aluno, não sobre uma grafia específica.
_ZERO_MONETARIO = re.compile(r"R\$\s*0[.,]00")


def _snapshot_com_reserva(**bloco_04: object) -> SnapshotOrdem:
    """Roda o motor REAL sobre o caso completo com as sobrescritas de Bloco 4
    pedidas e devolve o `SnapshotOrdem`.

    Mesmo padrão de `test_montagem_bloco_04.py::_reserva_mobilizavel_do_motor`
    (T-114), mas devolvendo o snapshot inteiro em vez do campo: a camada de
    exibição recebe o snapshot, e é por ele que `montar_contexto_plano` lê
    `diagnostico.RESERVA_MOBILIZAVEL`."""
    caso = caso_completo(valores_caso=dict(bloco_04))
    divida = montar_divida(caso.respostas, caso.DIVIDA_ID)
    estado = montar_estado_financeiro(
        caso.respostas,
        DATA_REFERENCIA=DATA_REFERENCIA,
        dividas=(divida,),
        **caso.parametros_externos,  # type: ignore[arg-type]
    )
    parametros = FonteParametrosArquivo().carregar(_PARAMETROS_VERSAO)
    return calcular_plano(estado, parametros)


def _snapshot_reserva_desconhecida() -> SnapshotOrdem:
    """`B4.02 = SIM`, `B4.03 = TALVEZ`, `B4.03A = "Não sei."` — o aluno que
    prefere decidir depois. Regra 3 da §13.1: `RESERVA_MOBILIZAVEL is
    DESCONHECIDO`."""
    return _snapshot_com_reserva(
        RESERVA_EXISTE="SIM",
        DISPOSICAO_USO_RESERVA="TALVEZ",
        RESERVA_TOTAL=converter_para_dinheiro("10.000,00"),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=NAO_SEI,
    )


def _snapshot_reserva_conhecida() -> SnapshotOrdem:
    """`B4.02 = SIM`, `B4.03 = PARTE`, `B4.02A = 10000`, `B4.03A = 3000` — o
    aluno que decidiu. Regra 2 da §13.1: `RESERVA_MOBILIZAVEL ==
    Decimal("3000")`."""
    return _snapshot_com_reserva(
        RESERVA_EXISTE="SIM",
        DISPOSICAO_USO_RESERVA="PARTE",
        RESERVA_TOTAL=converter_para_dinheiro("10.000,00"),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=converter_para_dinheiro("3.000,00"),
    )


def _html_do_plano(snapshot: SnapshotOrdem) -> str:
    """O HTML que o aluno vê, pela MESMA função de renderização de tela e PDF
    (`report/pdf.py::renderizar_html_do_plano`)."""
    return renderizar_html_do_plano(
        montar_contexto_plano(snapshot, carregar_textos_canonicos())
    )


def _bloco_da_reserva(html: str) -> str:
    """A `<section>` de `reserva_mobilizavel.html` recortada do HTML do
    plano, localizada pelo seu heading — nunca o documento inteiro.

    O recorte é o que dá sentido à asserção "não contém `R$ 0,00`": o plano
    inteiro pode legitimamente exibir `R$ 0,00` em outro campo (um custo, um
    resultado de caixa), e uma busca no documento todo ora falharia por
    motivo alheio à reserva, ora esconderia o bug quando o valor coincidisse.
    A âncora é o heading estrutural, não a redação de `OQ-21`."""
    secoes: list[str] = re.findall(r"<section>.*?</section>", html, flags=re.DOTALL)
    blocos = [secao for secao in secoes if "Reserva disponível para o plano" in secao]
    assert len(blocos) == 1, (
        f"esperado exatamente 1 bloco de reserva no HTML do plano, encontrados "
        f"{len(blocos)}"
    )
    return blocos[0]


def test_ac70_reserva_desconhecida_nao_exibe_zero_no_bloco_da_reserva() -> None:
    """`AC-70`, `EC-18`, `RF-43` — com `RESERVA_MOBILIZAVEL is DESCONHECIDO`,
    o bloco da reserva NÃO contém `R$ 0,00`.

    É a asserção central da cadeia de exibição: a §13.1 proíbe converter o
    estado desconhecido em zero "como informação", e mostrar `R$ 0,00`
    faria o aluno ler "não tenho reserva" onde o dado real é "ainda não
    decidi". Não depende de `OQ-21`: prova a AUSÊNCIA do zero, não a
    presença de um texto."""
    snapshot = _snapshot_reserva_desconhecida()
    assert snapshot.diagnostico.RESERVA_MOBILIZAVEL is DESCONHECIDO

    bloco = _bloco_da_reserva(_html_do_plano(snapshot))

    assert not _ZERO_MONETARIO.search(bloco), (
        f"o bloco da reserva exibiu zero monetário com RESERVA_MOBILIZAVEL "
        f"DESCONHECIDO — §13.1 proíbe a conversão silenciosa em zero: {bloco!r}"
    )
    # E também não o zero "cru", sem o prefixo monetário — o contexto carrega
    # `valor=""` no ramo pendente, então nenhum número deve chegar ao HTML.
    assert "0,00" not in bloco
    assert "0.00" not in bloco


def test_ac70_reserva_desconhecida_nao_omite_o_item() -> None:
    """`AC-70`, `EC-18`, `RF-43` — com `RESERVA_MOBILIZAVEL is DESCONHECIDO`,
    o bloco da reserva APARECE na saída.

    Omitir seria a mesma conversão silenciosa que exibir zero, só que
    invisível: o aluno não saberia sequer que existe uma decisão pendente.
    A asserção é sobre a presença do bloco e do estado que ele carrega
    (`pendente_de_decisao`), nunca sobre a redação (`OQ-21`)."""
    snapshot = _snapshot_reserva_desconhecida()
    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())

    assert contexto.reserva_mobilizavel.pendente_de_decisao is True
    assert contexto.reserva_mobilizavel.valor == ""

    html = _html_do_plano(snapshot)

    # O bloco existe (o recorte falha se não existir ou se houver mais de um).
    bloco = _bloco_da_reserva(html)
    # E não é uma casca vazia: há conteúdo ALÉM do heading que serviu de
    # âncora ao recorte. Omitir o corpo do bloco pendente seria a mesma
    # conversão silenciosa que exibir zero — o aluno veria um título sobre
    # uma reserva e nada dizendo que a decisão está em aberto. A asserção
    # desconta o heading justamente para que "bloco presente mas mudo" não
    # passe por "item não omitido".
    corpo = re.sub(r"<h2>.*?</h2>", " ", bloco, flags=re.DOTALL)
    corpo_visivel = re.sub(r"<[^>]+>", " ", corpo).strip()
    assert corpo_visivel != "", (
        f"o bloco da reserva apareceu sem nenhum conteúdo além do heading — "
        f"omitir o estado pendente é a mesma conversão silenciosa que a §13.1 "
        f"proíbe: {bloco!r}"
    )
    # O ponto de encaixe da redação de OQ-21 está marcado no HTML, para que
    # a pendência seja rastreável na própria saída — sem que nenhuma asserção
    # dependa do TEXTO que virá ali.
    assert 'data-pendencia-redacao="OQ-21"' in bloco


def test_ec18_nenhum_caminho_de_exibicao_levanta_excecao_com_desconhecido() -> None:
    """`EC-18`, `AC-70`, `RF-43` — nenhum caminho de exibição levanta exceção
    ao encontrar `DESCONHECIDO`.

    Cobre a cadeia inteira: `_reserva_mobilizavel` (leitura pura
    `is DESCONHECIDO`), `montar_contexto_plano` (montagem do
    `ContextoPlano`) e `renderizar_html_do_plano` (Jinja2 sobre
    `reserva_mobilizavel.html`). O ramo desconhecido nunca passa por
    `_formatar_valor_de_apoio`, que faria `str(valor)` e produziria
    `"Desconhecido.DESCONHECIDO"` — asserido abaixo pela ausência desse
    literal na saída."""
    snapshot = _snapshot_reserva_desconhecida()
    assert snapshot.diagnostico.RESERVA_MOBILIZAVEL is DESCONHECIDO

    # Se qualquer etapa levantasse, o teste falharia aqui — sem
    # `pytest.raises`, porque o critério é a AUSÊNCIA de exceção.
    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())
    html = renderizar_html_do_plano(contexto)

    assert isinstance(html, str)
    assert html != ""
    # A convenção da tela do REVISOR (rótulo técnico "DESCONHECIDO",
    # `RF-26`/`AC-29`) não vaza para a tela do ALUNO, e o `str()` do enum
    # tampouco.
    bloco = _bloco_da_reserva(html)
    assert "DESCONHECIDO" not in bloco
    assert "Desconhecido.DESCONHECIDO" not in bloco


def test_ac70_reserva_conhecida_exibe_o_valor() -> None:
    """`AC-70`, `RF-43` — com `RESERVA_MOBILIZAVEL` como `Decimal`, o HTML
    EXIBE o valor.

    O outro ramo da condicional, sem o qual "não mostrar zero" poderia ser
    satisfeito por um template que nunca mostra nada. O valor é o mesmo que o
    aluno declarou (3.000, limitado pela Regra 2 da §13.1 ao total de
    10.000 — limite aplicado pelo MOTOR, jamais reproduzido em `report/`), e
    a igualdade é EXATA: nenhum valor desta fatia é acumulado, então
    `assertar_monetario` (± R$ 0,05) não se aplica."""
    snapshot = _snapshot_reserva_conhecida()
    assert snapshot.diagnostico.RESERVA_MOBILIZAVEL == Decimal("3000")

    contexto = montar_contexto_plano(snapshot, carregar_textos_canonicos())

    assert contexto.reserva_mobilizavel.pendente_de_decisao is False
    assert contexto.reserva_mobilizavel.valor != ""

    bloco = _bloco_da_reserva(_html_do_plano(snapshot))

    assert contexto.reserva_mobilizavel.valor in bloco
    # `T-177`: `R$ 3.000,00`, não `3000.00` — o aluno lê dinheiro escrito
    # como dinheiro. O que `AC-70` exige (valor visível quando conhecido,
    # nunca convertido em zero) continua provado pela asserção acima.
    assert "R$ 3.000,00" in bloco


def test_ac70_os_dois_estados_produzem_saidas_diferentes() -> None:
    """`AC-70`, `EC-18`, `RF-43` — "ainda não decidi" e "decidi 3.000"
    produzem blocos DIFERENTES.

    A prova por contraste de que a distinção da §13.1 sobrevive até a tela: é
    esta asserção que quebraria se alguém "simplificasse" a exibição
    convertendo `DESCONHECIDO` em zero — os dois casos passariam a renderizar
    a mesma coisa, e o aluno perderia justamente a informação de que há uma
    decisão pendente. Estrutural, sem depender de `OQ-21`."""
    pendente = _bloco_da_reserva(_html_do_plano(_snapshot_reserva_desconhecida()))
    decidido = _bloco_da_reserva(_html_do_plano(_snapshot_reserva_conhecida()))

    assert pendente != decidido
    assert not _ZERO_MONETARIO.search(pendente)
