"""Exportação em PDF do plano — `RF-20`, `RF-21`, `AC-14`, `AC-16` (T-63).

WeasyPrint sobre o **MESMO** `plano.html` que a tela usa — nunca uma segunda
redação do texto normativo. `gerar_pdf_do_plano` chama exatamente a mesma
função de renderização Jinja2 que a tela chamaria (`Environment.
get_template("plano.html").render(...)`, o mesmo template já testado por
`tests/app_aluno/test_plano.py`/`test_plano_ec07_ec08_ec09.py`, T-59..T-62) e
entrega o HTML resultante a `weasyprint.HTML(string=...).write_pdf()` — a API
pública documentada da versão instalada (`weasyprint>=63.0`, decidida em
`pyproject.toml` extra `app`, plano §2). Nenhum HTML paralelo é escrito aqui:
o mesmo `report/templates/plano/plano.html` (e seus parciais `posicao.html`,
`ordem_vazia.html`, `estabilizacao.html`, `pendencias.html`) que a rota de
tela (T-64, tarefa seguinte) vai renderizar é o que gera o PDF — "um objeto
revisado, duas apresentações" (`OQ-09`).

**"Liberação registrada" (critério de aceite 4) — decisão de modelagem desta
tarefa.** A fila de revisão humana (`Entrega 8`, `revisoes`/`app/revisao/`)
ainda não existe: nenhuma tarefa concluída até aqui popula
`Caso.snapshot_liberado_id` a partir de uma aprovação humana de fato. Em vez
de inventar um novo conceito de "liberação" paralelo, esta tarefa REAPROVEITA
o campo que já existe (`persistencia/app_aluno/casos.py::Caso.
snapshot_liberado_id`, coluna `app_aluno.casos.snapshot_liberado_id`, T-21/
T-23) com a semântica que `RepositorioCasos.registrar_snapshot_liberado`
já documenta: "o snapshot mais recentemente LIBERADO em revisão (`OQ-09`)".
A regra operacional desta tarefa é, portanto, exatamente:

    snapshot com liberação registrada  <=>  caso.snapshot_liberado_id == snapshot.SNAPSHOT_ID

**Fronteira honesta com a Entrega 8 (ainda não implementada).** Hoje (antes
da Entrega 8) NENHUM caminho de código popula `snapshot_liberado_id` — nem
`app/motor/executor.py` (que só transiciona o caso para `AGUARDANDO_REVISAO`,
nunca grava `snapshot_liberado_id`), nem `app/http/rotas_calculo.py`, nem
qualquer rota de revisão (que não existe ainda). Isso significa que, em
produção, HOJE, nenhum PDF seria gerado por este módulo até que a fila de
revisão (Entrega 8) implemente o fluxo de aprovação humana que chama
`RepositorioCasos.registrar_snapshot_liberado` — comportamento CORRETO e
proposital: `AC-14`/`AC-16` só valem para um snapshot revisado (spec §
"Revisão humana obrigatória no piloto", `sdd.config.md` §6), e este módulo
recusa gerar PDF de qualquer outro. Quando a Entrega 8 existir, ela populará
`snapshot_liberado_id` só APÓS aprovação humana — este módulo não muda nesse
dia, porque já lê exclusivamente esse campo, nunca decide por si só o que
conta como "liberado".

**Determinismo do PDF sobre o mesmo snapshot (critério de aceite 3).** O
snapshot é imutável (append-only, `V-01`, `T-21`/`T-26`): `montar_contexto_
plano` (`report/plano.py`) só LÊ campos do mesmo `SnapshotOrdem`, sem I/O
externo variável (sem data/hora do sistema, sem número aleatório), então
renderizar o MESMO snapshot duas vezes produz o MESMO HTML de entrada —
verificado em `tests/app_aluno/test_pdf.py` por comparação de HTML, nunca de
bytes de PDF: o PDF que o WeasyPrint escreve carrega metadados de geração
(ex.: timestamp de criação do arquivo, no `/CreationDate` do PDF) que podem
variar entre duas chamadas mesmo com entrada idêntica — comparar o HTML de
ENTRADA (determinístico, sob controle deste projeto) é a prova estável do
requisito "regenerar produz o mesmo conteúdo"; comparar bytes exatos do PDF
seria frágil por um detalhe de biblioteca externa que esta tarefa não
controla e que não está entre os critérios de aceite (o critério fala em
"mesmo conteúdo", não "mesmos bytes").

Direção de dependência: este módulo importa de `jinja2`, `weasyprint`,
`pathlib`/stdlib, de `engine.snapshot.SnapshotOrdem` (tipo de E/S já
liberado pela allowlist de `AC-41`) e de `report.plano` (a MESMA montagem de
contexto que a tela usa) — nunca duplica lógica de `report/plano.py`, nunca
importa `engine.gates`/`engine.ciclo_mensal`/`engine.metodos.*`/
`engine.comparacao`/`engine.ordem` (`AC-41`), nenhum identificador `P_*` nem
enunciado de pergunta (`AC-37`).

REGRAS: `RF-20`, `RF-21`, `AC-14`, `AC-16`
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from jinja2 import Environment, FileSystemLoader, select_autoescape

from engine.snapshot import SnapshotOrdem
from persistencia.app_aluno.casos import Caso
from report.plano import ContextoPlano, TextosCanonicosPlano, montar_contexto_plano

REGRAS: Final[tuple[str, ...]] = ("RF-20", "RF-21", "AC-14", "AC-16")

_DIRETORIO_TEMPLATES_PLANO: Final[Path] = Path(__file__).resolve().parent / "templates" / "plano"


class ErroSnapshotNaoLiberado(Exception):
    """`AC-25`-adjacente (o critério pleno de acesso por rota é `T-64`): o
    `SNAPSHOT_ID` recebido não é o `snapshot_liberado_id` do `Caso` — nenhum
    PDF é gerado para um snapshot que ainda não passou por liberação
    registrada (ver a nota extensa na docstring do módulo sobre a fronteira
    com a Entrega 8, fila de revisão)."""

    def __init__(self, caso_id: str, snapshot_id: str) -> None:
        super().__init__(
            f"CASO_ID={caso_id!r}: SNAPSHOT_ID={snapshot_id!r} não é o snapshot liberado"
        )


def snapshot_tem_liberacao_registrada(caso: Caso, snapshot: SnapshotOrdem) -> bool:
    """A ÚNICA leitura, em todo o projeto, do que "liberação registrada"
    significa hoje (ver a nota extensa na docstring do módulo): o
    `SNAPSHOT_ID` do snapshot é exatamente `caso.snapshot_liberado_id` —
    leitura pura de dois campos já existentes, nenhum cálculo, nenhuma
    inferência sobre estado do caso ou histórico de revisão."""
    return caso.snapshot_liberado_id == snapshot.SNAPSHOT_ID


def _ambiente_templates_plano() -> Environment:
    """O MESMO `Environment`/`FileSystemLoader` sobre `report/templates/
    plano/` que os testes de T-59..T-62 já usam (`tests/app_aluno/
    test_plano.py::_renderizar_plano_html_com_contexto`) — nunca uma segunda
    configuração de Jinja2 divergente entre tela e PDF."""
    return Environment(
        loader=FileSystemLoader(str(_DIRETORIO_TEMPLATES_PLANO)),
        autoescape=select_autoescape(["html"]),
    )


def renderizar_html_do_plano(contexto: ContextoPlano) -> str:
    """Renderiza `plano.html` a partir de um `ContextoPlano` já montado —
    a MESMA função de renderização que a tela (T-64) chama. Nenhuma cópia do
    HTML/CSS existe neste módulo: só a passagem do contexto ao template
    único de `report/templates/plano/plano.html`."""
    template = _ambiente_templates_plano().get_template("plano.html")
    return template.render(
        titulo=contexto.titulo,
        corpo=contexto.corpo,
        ordem=contexto.ordem,
        PRAZO_TOTAL=contexto.PRAZO_TOTAL,
        CUSTO_FUTURO_TOTAL=contexto.CUSTO_FUTURO_TOTAL,
        ENGINE_VERSION=contexto.ENGINE_VERSION,
        PARAMETROS_VERSION=contexto.PARAMETROS_VERSION,
        cenario=contexto.cenario,
        acoes=contexto.acoes,
        pendencias=contexto.pendencias,
        MODO_ESTABILIZACAO=contexto.MODO_ESTABILIZACAO,
        RESULTADO_CAIXA_OBSERVADO=contexto.RESULTADO_CAIXA_OBSERVADO,
        # T-116 (RF-43) — `reserva_mobilizavel.html` é incluído por
        # `plano.html` e precisa do contexto tanto na tela quanto no PDF:
        # esta é a ÚNICA função de renderização das duas apresentações.
        reserva_mobilizavel=contexto.reserva_mobilizavel,
    )


def gerar_html_do_plano_liberado(
    caso: Caso, snapshot: SnapshotOrdem, textos: TextosCanonicosPlano
) -> str:
    """Monta o contexto (`report/plano.py::montar_contexto_plano` — a MESMA
    montagem que a tela usa, Lei nº 3: só leitura de campo do snapshot) e
    renderiza `plano.html` — mas SÓ quando `snapshot` tem liberação
    registrada para `caso` (critério de aceite 4). Levanta
    `ErroSnapshotNaoLiberado` caso contrário, sem renderizar nada.

    Determinismo (critério de aceite 3): como `montar_contexto_plano` só lê
    campos do MESMO `SnapshotOrdem` imutável, chamar esta função duas vezes
    com o mesmo `(caso, snapshot, textos)` produz exatamente o mesmo HTML —
    ver a nota extensa na docstring do módulo sobre por que a prova de
    "mesmo conteúdo" compara este HTML, não bytes de PDF."""
    if not snapshot_tem_liberacao_registrada(caso, snapshot):
        raise ErroSnapshotNaoLiberado(caso.CASO_ID, snapshot.SNAPSHOT_ID)

    contexto = montar_contexto_plano(snapshot, textos)
    return renderizar_html_do_plano(contexto)


def gerar_pdf_do_plano(caso: Caso, snapshot: SnapshotOrdem, textos: TextosCanonicosPlano) -> bytes:
    """Gera os bytes do PDF do plano — `weasyprint.HTML(string=...).
    write_pdf()`, a API pública documentada da versão instalada
    (`weasyprint>=63.0`), aplicada sobre o MESMO HTML que `gerar_html_do_
    plano_liberado` produziria para a tela (`OQ-09`: um objeto revisado, duas
    apresentações). Propaga `ErroSnapshotNaoLiberado` sem gerar nenhum byte
    quando o snapshot não tem liberação registrada (critério de aceite 4).

    Import de `weasyprint` feito DENTRO da função, não no topo do módulo: a
    biblioteca nativa (GTK/Pango) que o `weasyprint` carrega via `cffi` é uma
    dependência de SISTEMA, não de `pip` — em ambientes onde ela ainda não
    está instalada, isso permite que `report/plano.py`/`montar_contexto_
    plano`/`gerar_html_do_plano_liberado` continuem plenamente testáveis e
    utilizáveis (inclusive pela tela, T-64) sem que a mera importação deste
    módulo por outro código exija a biblioteca nativa presente."""
    html = gerar_html_do_plano_liberado(caso, snapshot, textos)

    from weasyprint import HTML

    return bytes(HTML(string=html).write_pdf())
