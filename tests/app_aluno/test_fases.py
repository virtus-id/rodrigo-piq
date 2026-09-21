"""Testes de `app/casos/fases.py` — as cinco fases do aluno (`RF-61`,
`AC-89`, `EC-25`, T-146).

Os doze membros de `ESTADO_CASO` colapsam nas cinco fases de `renderInicio`
do protótipo validado. Este módulo prova três coisas distintas:

1. **`AC-89`** — todo membro de `ESTADO_CASO` tem fase. A enumeração é feita
   **a partir do próprio enum** (`for estado in ESTADO_CASO:`), nunca de uma
   lista transcrita: uma lista transcrita envelheceria junto com o código que
   deveria vigiar, e um membro novo sem fase passaria despercebido. Com a
   enumeração viva, o membro novo faz `fase_do_estado` cair no
   `UnboundLocalError`/`None` do `match` sem `case _` — que é exatamente o
   comportamento correto, e o mesmo defeito que `mypy --strict` pega antes.
2. **`EC-25`** — `CALCULANDO`, `ERRO_DE_CALCULO` e `ENCERRADO` têm fase, e
   nenhum deles inventou uma fase própria. `FASE_INICIO` tem exatamente cinco
   membros.
3. **Pureza** — `app/casos/fases.py` não importa `engine/`, `persistencia/`
   nem `fastapi`. Teste estático por `ast.parse`, mesma técnica de
   `tests/app_aluno/estatica/test_fronteira_import_engine.py`: o arquivo é
   parseado, nunca importado para descobrir seus imports.

REGRAS: `RF-58`, `RF-61`, `AC-81`, `AC-89`, `EC-25`
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from app.casos.fases import FASE_INICIO, fase_do_estado, fase_do_plano_liberado
from app.casos.maquina import ESTADO_CASO

RAIZ_PROJETO: Final[Path] = Path(__file__).resolve().parent.parent.parent
ARQUIVO_FASES: Final[Path] = RAIZ_PROJETO / "app" / "casos" / "fases.py"

# Os prefixos de módulo que `app/casos/fases.py` NÃO pode importar. `engine/`
# e `persistencia/` fariam o módulo deixar de ser puro (o motor e o I/O);
# `fastapi` o prenderia à camada HTTP, e a fase passaria a não poder ser
# decidida fora de uma requisição.
PREFIXOS_PROIBIDOS: Final[frozenset[str]] = frozenset(
    {"engine", "persistencia", "fastapi", "starlette"}
)


# ---------------------------------------------------------------------------
# `AC-89` — a trava do `match` exaustivo: TODO membro de `ESTADO_CASO` tem
# fase, e a lista de membros vem do enum, nunca de uma transcrição.
# ---------------------------------------------------------------------------


def test_ac89_todo_membro_de_estado_caso_tem_uma_fase() -> None:
    """`AC-89` — enumerando `ESTADO_CASO` (a fonte viva, não uma lista
    escrita à mão), `fase_do_estado` devolve um `FASE_INICIO` para cada
    membro.

    Um membro novo sem `case` declarado faz este teste falhar — por
    `UnboundLocalError` do `match` sem `case _`, ou por retorno `None` —, que
    é o comportamento correto: a alternativa (um `case _` default) mandaria o
    aluno silenciosamente para a tela errada."""
    for estado in ESTADO_CASO:
        fase = fase_do_estado(estado)

        assert isinstance(fase, FASE_INICIO), (
            f"{estado.name} não devolveu um FASE_INICIO — o `match` de "
            "`fase_do_estado` deixou de ser exaustivo (AC-89)"
        )


def test_ac89_os_doze_membros_de_estado_caso_estao_cobertos() -> None:
    """`AC-89` — a máquina tem doze estados, e os doze aparecem na varredura
    acima. A contagem é lida do enum: se a máquina ganhar um décimo terceiro
    estado, é o teste anterior que precisa continuar verde, não este número
    que precisa ser reescrito às pressas."""
    fases_por_estado = {estado: fase_do_estado(estado) for estado in ESTADO_CASO}

    assert len(fases_por_estado) == len(ESTADO_CASO)
    assert len(ESTADO_CASO) == 12


# ---------------------------------------------------------------------------
# `RF-61` — o mapa da tabela de `plans/app-aluno.plan.md` §R5.1.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("estado", "fase_esperada"),
    [
        (ESTADO_CASO.CADASTRADO, FASE_INICIO.COLETA),
        (ESTADO_CASO.CONSENTIMENTO_REGISTRADO, FASE_INICIO.COLETA),
        (ESTADO_CASO.COLETA_INICIAL, FASE_INICIO.COLETA),
        (ESTADO_CASO.COLETA_DIRIGIDA, FASE_INICIO.COLETA),
        (ESTADO_CASO.CALCULANDO, FASE_INICIO.REVISAO),
        (ESTADO_CASO.ERRO_DE_CALCULO, FASE_INICIO.REVISAO),
        (ESTADO_CASO.AGUARDANDO_REVISAO, FASE_INICIO.REVISAO),
        (ESTADO_CASO.REPROVADO_EM_REVISAO, FASE_INICIO.REPROVADO),
        (ESTADO_CASO.PLANO_LIBERADO, FASE_INICIO.PLANO),
        (ESTADO_CASO.CONFIRMACAO_ATAQUE, FASE_INICIO.PLANO),
        (ESTADO_CASO.ACOMPANHAMENTO, FASE_INICIO.ACOMPANHAMENTO),
        (ESTADO_CASO.ENCERRADO, FASE_INICIO.ACOMPANHAMENTO),
    ],
)
def test_rf61_mapeamento_de_cada_estado_para_a_sua_fase(
    estado: ESTADO_CASO, fase_esperada: FASE_INICIO
) -> None:
    """`RF-61` — a tabela de `plans/app-aluno.plan.md` §R5.1, linha a linha.

    `CADASTRADO` é `coleta` porque o consentimento, do ponto de vista do
    aluno, é o começo da coleta; `ERRO_DE_CALCULO` é `revisao` porque o erro
    técnico nunca chega a ele; `ENCERRADO` é `acompanhamento` com ações
    vazias."""
    assert fase_do_estado(estado) is fase_esperada


def test_rf61_os_valores_das_fases_sao_os_do_prototipo() -> None:
    """`RF-61` — os `value` atravessam a fronteira HTTP no campo `fase` e o
    cliente os consome como união de literais. São os cinco ramos de
    `renderInicio`, caractere por caractere."""
    valores = {fase.value for fase in FASE_INICIO}

    assert valores == {"coleta", "revisao", "reprovado", "plano", "acompanhamento"}


# ---------------------------------------------------------------------------
# `EC-25` — estado sem etapa óbvia tem fase, e nenhuma fase nova foi criada.
# ---------------------------------------------------------------------------


def test_ec25_nenhuma_sexta_fase_foi_criada() -> None:
    """`EC-25` — `FASE_INICIO` tem **exatamente cinco** membros.

    As duas tentações recusadas moram aqui: uma tela de erro para
    `ERRO_DE_CALCULO` e uma fase "encerrado" para `ENCERRADO`. Qualquer uma
    delas faria este teste falhar antes de chegar ao aluno."""
    assert len(FASE_INICIO) == 5


@pytest.mark.parametrize(
    "estado",
    [ESTADO_CASO.CALCULANDO, ESTADO_CASO.ERRO_DE_CALCULO, ESTADO_CASO.ENCERRADO],
)
def test_ec25_estado_sem_etapa_obvia_cai_numa_das_cinco_fases(
    estado: ESTADO_CASO,
) -> None:
    """`EC-25` — os três estados "sem etapa óbvia para o aluno" têm fase, e é
    uma das cinco. Nenhum cai numa fase própria nem fica sem resposta."""
    fase = fase_do_estado(estado)

    assert fase in set(FASE_INICIO)


def test_ec25_calculando_e_erro_de_calculo_compartilham_a_mesma_fase() -> None:
    """`EC-25` — *"é com a gente, você não faz nada"* é a mesma resposta nos
    dois casos. Separá-los em fases distintas exporia ao aluno a diferença
    entre "calculando" e "falhou", que é justamente o que não deve chegar a
    ele."""
    assert fase_do_estado(ESTADO_CASO.CALCULANDO) is fase_do_estado(
        ESTADO_CASO.ERRO_DE_CALCULO
    )
    assert fase_do_estado(ESTADO_CASO.ERRO_DE_CALCULO) is FASE_INICIO.REVISAO


def test_ec25_encerrado_compartilha_a_fase_de_acompanhamento() -> None:
    """`EC-25` — `ENCERRADO` **não** é uma sexta fase: é `acompanhamento`.
    O que muda é o conteúdo do cartão, não o que o aluno faz agora."""
    assert fase_do_estado(ESTADO_CASO.ENCERRADO) is fase_do_estado(
        ESTADO_CASO.ACOMPANHAMENTO
    )


# ---------------------------------------------------------------------------
# `RF-61` — a exceção declarada: `PLANO_LIBERADO` depende do snapshot.
# ---------------------------------------------------------------------------


def test_rf61_plano_liberado_com_ataque_a_decidir_e_fase_plano() -> None:
    """`RF-61` — havendo ataque imediato a decidir, a próxima etapa é o
    Bloco 10: fase `plano`."""
    assert fase_do_plano_liberado(tem_ataque_a_decidir=True) is FASE_INICIO.PLANO


def test_rf61_plano_liberado_sem_ataque_a_decidir_e_fase_acompanhamento() -> None:
    """`RF-61` — sem ataque imediato recomendado não há decisão nenhuma a
    tomar. Oferecer "Decidir agora" mandaria o aluno a uma tela que o
    servidor fecha com `409`; a próxima etapa é *"ver o que fazer agora"*."""
    assert (
        fase_do_plano_liberado(tem_ataque_a_decidir=False)
        is FASE_INICIO.ACOMPANHAMENTO
    )


def test_rf61_fase_do_plano_liberado_devolve_sempre_uma_das_cinco_fases() -> None:
    """`RF-61` — a exceção do `PLANO_LIBERADO` não abre uma sexta fase: as
    duas saídas possíveis já existem em `FASE_INICIO`."""
    saidas = {
        fase_do_plano_liberado(tem_ataque_a_decidir=True),
        fase_do_plano_liberado(tem_ataque_a_decidir=False),
    }

    assert saidas <= set(FASE_INICIO)


# ---------------------------------------------------------------------------
# Pureza do módulo — teste estático por AST, nunca por import.
# ---------------------------------------------------------------------------


def _modulos_importados(codigo_fonte: str, nome_arquivo: str) -> set[str]:
    """Os módulos de topo importados pelo arquivo, por `ast.parse`.

    `import a.b.c` e `from a.b import c` contam ambos como `a` — é o prefixo
    de topo que determina de qual camada o módulo depende."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    modulos: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for alias in no.names:
                modulos.add(alias.name.split(".")[0])
        elif isinstance(no, ast.ImportFrom) and no.module is not None:
            modulos.add(no.module.split(".")[0])
    return modulos


def test_rf61_fases_nao_importa_engine_persistencia_nem_fastapi() -> None:
    """`RF-61` — módulo **puro**: sem I/O, sem FastAPI, sem `engine/`, sem
    `persistencia/`.

    A pureza é o que permite decidir a fase fora de uma requisição — e é a
    mesma disciplina de `app/casos/progresso.py` e
    `app/http/mensagens_de_estado.py`. Auditado por `ast.parse` sobre o texto
    do arquivo, técnica de `tests/app_aluno/estatica/
    test_fronteira_import_engine.py`: o arquivo nunca é importado para se
    descobrir o que ele importa."""
    codigo_fonte = ARQUIVO_FASES.read_text(encoding="utf-8")

    importados = _modulos_importados(codigo_fonte, str(ARQUIVO_FASES))

    proibidos_encontrados = importados & PREFIXOS_PROIBIDOS
    assert not proibidos_encontrados, (
        "app/casos/fases.py deixou de ser puro — importa "
        f"{sorted(proibidos_encontrados)} (RF-61)"
    )


def test_detector_de_import_proibido_pega_um_import_sintetico() -> None:
    """Prova de que a auditoria acima não é cosmética: um arquivo sintético
    que importa de `engine/` é detectado."""
    codigo_com_violacao = """
from engine.snapshot import SnapshotOrdem
import persistencia.app_aluno.casos
"""

    importados = _modulos_importados(codigo_com_violacao, "fases_sintetico.py")

    assert importados & PREFIXOS_PROIBIDOS == {"engine", "persistencia"}
