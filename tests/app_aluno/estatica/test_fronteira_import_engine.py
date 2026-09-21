"""Fronteira de import com `engine/` — RF-34, AC-41.

Lei nº 3 (`plans/app-aluno.plan.md` §1): *a aplicação não calcula*. Todo
número, status ou prazo exibido é a leitura de um campo de `SnapshotOrdem` —
nunca um recálculo. `AC-41` torna essa lei uma propriedade verificável por
AST, não uma convenção de code review: `app/`, `collection/` e `report/` só
podem importar de `engine.*` o ponto de entrada (`calcular_plano`), os tipos
de entrada/saída, as portas e `engine.precisao`. Qualquer outro nome de
`engine/` — em especial os módulos internos do cálculo (`engine.gates`,
`engine.ciclo_mensal`, `engine.metodos.*`, `engine.comparacao`,
`engine.ordem`) — é uma violação.

Técnica (decisão de implementação desta tarefa): `ast.parse` sobre o texto de
cada `.py`, nunca `importlib`/exec — os módulos de `app/`, `collection/` e
`report/` não precisam (e não devem) ser importáveis/executáveis para este
teste rodar; ele só lê texto e monta uma árvore sintática. Os nós `Import`/
`ImportFrom` coletados são validados contra a allowlist declarada abaixo.

A lógica de detecção (`verificar_arquivo`) é separada do teste que a aplica
sobre o repositório real (`test_pastas_da_aplicacao_nao_importam_engine_
interno`, que hoje deve dar zero violações — as três pastas ainda estão
vazias) dos testes que a exercitam com casos SINTÉTICOS de violação
(`test_detector_pega_*`): não existe hoje nenhum arquivo violador real no
repo para testar a rejeição, então o caso de violação é construído como
string, parseado isoladamente, e nunca vira código de verdade do projeto.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent
PASTAS_VERIFICADAS: Final[tuple[Path, ...]] = (
    RAIZ_PROJETO / "app",
    RAIZ_PROJETO / "collection",
    RAIZ_PROJETO / "report",
)

# Allowlist declarada aqui, e só aqui — AC-41: "a lista permitida declarada
# no próprio arquivo de teste". Cada entrada é um nome pontilhado completo
# que pode aparecer num `ImportFrom`/`Import` cujo módulo é `engine` ou
# começa por `engine.`.
#
# - `engine.motor.calcular_plano` — o único ponto de entrada do cálculo
#   (engine/motor.py).
# - Tipos de entrada/saída: `EstadoFinanceiro`/`Divida` (engine/estado.py),
#   `SnapshotOrdem` (engine/snapshot.py), `Parametros`/`ErroParametros`
#   (engine/parametros.py) e tudo de `engine.tipos` (domínios fechados e
#   aliases usados para montar/ler esses tipos — `Dinheiro`, `DinheiroTalvez`,
#   `Desconhecido`, `DESCONHECIDO`, os enums de status/método/evento etc.).
# - `engine.estado.TIPO_DIVIDA` — enum que COMPÕE `Divida` (o campo
#   `Divida.TIPO_DIVIDA` é tipado por ele). Adicionado em `T-49`
#   (`app/montagem/estado.py`): sem este nome era IMPOSSÍVEL montar uma
#   `Divida` tipada fora de `engine/`, já que `TIPO_DIVIDA` só existe em
#   `engine/estado.py` (não é redefinido nem reexportado por `engine.tipos`).
#   A lacuna original desta allowlist (que citava só `EstadoFinanceiro`/
#   `Divida`, não os enums que os compõem) bloqueava qualquer implementação
#   de `T-49`/`T-50`/`T-51`.
# - `engine.estado.PerfilComportamental`, `engine.estado.
#   SinaisComportamentais`, `engine.estado.JANELA_NOVA_DIVIDA` e os 7 enums
#   do Bloco 2 (`REGISTRO_GASTOS`, `FREQUENCIA_REGISTRO`,
#   `DEFASAGEM_REGISTRO`, `COBERTURA_PEQUENOS_GASTOS`,
#   `COBERTURA_MEIOS_PAGAMENTO`, `CONHECIMENTO_GASTO`,
#   `GASTOS_NAO_IDENTIFICADOS`, `REVISAO_SEMANAL`) — adicionados em `T-50`
#   (`app/montagem/estado.py`), pelo mesmo critério de `TIPO_DIVIDA`: sem
#   eles é impossível montar `PerfilComportamental`/`SinaisComportamentais`
#   tipados fora de `engine/`. `Oportunidade` permanece fora — nenhuma
#   tarefa até `T-50` precisou importá-la deste módulo; deve ser adicionada
#   pelo mesmo critério quando uma tarefa futura a consumir.
# - `engine.estado.TIPO_RENDA` — adicionado em `T-51`
#   (`app/montagem/estado.py::montar_estado_financeiro`), mesmo critério de
#   `TIPO_DIVIDA`/T-49: o campo `EstadoFinanceiro.TIPO_RENDA` é tipado por
#   este enum (`engine/estado.py`, não redefinido nem reexportado por
#   `engine.tipos`) — sem liberá-lo é impossível montar um
#   `EstadoFinanceiro` tipado fora de `engine/`.
# - Portas: `FonteParametros`/`RepositorioSnapshots` (engine/portas.py) — o
#   contrato que `persistencia/` implementa, do lado do motor.
# - `engine.precisao` inteiro: `dinheiro`, `quantizar_exibicao`,
#   `CONTEXTO_MOTOR` — a fronteira de conversão/exibição que a spec manda
#   reusar (RF-13) em vez de duplicar em `app/montagem/conversao.py`.
# - `engine.ciclo_mensal.ErroInvariante` — adicionado em `T-55`
#   (`app/motor/executor.py`): o tratamento de erro do executor (`EC-03`)
#   precisa CAPTURAR esta exceção especificamente (transicionar o caso para
#   `ERRO_DE_CALCULO` e relançar), não apenas propagá-la sem tratamento como
#   T-54 fazia. É a única exceção de `engine.ciclo_mensal` liberada — nenhum
#   outro nome daquele módulo (`simular_cenario`, `executar_mes`, `Cenario`
#   etc.) entra na allowlist: `ErroInvariante` é um TIPO de exceção, não uma
#   função de cálculo, e capturá-la não é "calcular" (Lei nº 3).
# - `engine.gates.AcaoRequerida` — adicionado em `T-74`
#   (`app/motor/acoes.py::acoes_em_acompanhamento`), mesmo critério de
#   `PosicaoOrdem`/`TIPO_DIVIDA`: é o tipo do ELEMENTO da tupla
#   `SnapshotOrdem.ORDEM_ACOES` (`engine/snapshot.py`), portanto tipo de
#   SAÍDA que compõe um campo do snapshot já liberado — sem liberar este
#   nome não há como tipar `-> tuple[AcaoRequerida, ...]` fora de `engine/`
#   sob `mypy --strict`. Nenhum OUTRO nome de `engine.gates` (os quatro
#   `aplicar_gate_*`, `particionar_elegibilidade`, `ResultadoGates` etc.)
#   entra na allowlist: `AcaoRequerida` é uma dataclass de dados que o motor
#   já produziu, não uma função de gate — lê-la não é "calcular" (Lei nº 3),
#   mesmo raciocínio de `ErroInvariante` acima para exceções.
# - `engine.estado.RESERVA_EXISTE` e `engine.estado.DISPOSICAO_USO_RESERVA` —
#   adicionados em `T-109` (Rodada 2, fatia 2A) para a leitura de reserva do
#   Bloco 4 exigida por `T-110` (`app/montagem/estado.py`), pelo mesmo
#   Critério A de `TIPO_DIVIDA`/`T-49`, dos 8 do Bloco 2/`T-50` e de
#   `TIPO_RENDA`/`T-51`: são os enums que TIPAM campos de `EstadoFinanceiro`
#   — `EstadoFinanceiro.RESERVA_EXISTE` (`engine/estado.py:511`) e
#   `EstadoFinanceiro.DISPOSICAO_USO_RESERVA` (`:513`) — e só existem em
#   `engine/estado.py` (`:181` e `:192`), não sendo redefinidos nem
#   reexportados por `engine.tipos`. Sem liberá-los é impossível montar um
#   `EstadoFinanceiro` tipado fora de `engine/` sob `mypy --strict`.
#   Continuam FORA, pelo mesmo princípio já registrado acima sobre
#   `Oportunidade` (allowlist não contém nome que ninguém importa), os cinco
#   nomes das fatias 2B/2C — `ItemInvestimento`, `ItemAtivo`,
#   `RecursoExtraordinario`, `JANELA_RECURSO_EXTRAORDINARIO` e
#   `CERTEZA_RECURSO_EXTRAORDINARIO`: entram quando a tarefa que os consumir
#   existir, não antes. `CLASSIFICACAO_MOBILIZACAO` e `Desconhecido`, usados
#   na mesma leitura, NÃO precisam de entrada aqui — vivem em `engine.tipos`,
#   já liberado por inteiro em `MODULOS_LIBERADOS_POR_INTEIRO`.
NOMES_PERMITIDOS_DE_ENGINE: Final[frozenset[str]] = frozenset(
    {
        # engine.motor
        "engine.motor.calcular_plano",
        # engine.estado — tipos de entrada
        "engine.estado.EstadoFinanceiro",
        "engine.estado.Divida",
        "engine.estado.TIPO_DIVIDA",
        # engine.estado — enums/tipos do Bloco 2 e sinais comportamentais
        # (T-50, AC-13): compõem PerfilComportamental/SinaisComportamentais.
        "engine.estado.PerfilComportamental",
        "engine.estado.SinaisComportamentais",
        "engine.estado.JANELA_NOVA_DIVIDA",
        "engine.estado.REGISTRO_GASTOS",
        "engine.estado.FREQUENCIA_REGISTRO",
        "engine.estado.DEFASAGEM_REGISTRO",
        "engine.estado.COBERTURA_PEQUENOS_GASTOS",
        "engine.estado.COBERTURA_MEIOS_PAGAMENTO",
        "engine.estado.CONHECIMENTO_GASTO",
        "engine.estado.GASTOS_NAO_IDENTIFICADOS",
        "engine.estado.REVISAO_SEMANAL",
        # engine.estado — TIPO_RENDA (T-51, AC-18): compõe EstadoFinanceiro.
        "engine.estado.TIPO_RENDA",
        # engine.estado — reserva do Bloco 4 (T-109 p/ T-110, AC-63/AC-64):
        # tipam EstadoFinanceiro.RESERVA_EXISTE (:511) e
        # .DISPOSICAO_USO_RESERVA (:513). Critério A, como TIPO_DIVIDA.
        "engine.estado.RESERVA_EXISTE",
        "engine.estado.DISPOSICAO_USO_RESERVA",
        # engine.snapshot — tipo de saída
        "engine.snapshot.SnapshotOrdem",
        # engine.parametros
        "engine.parametros.Parametros",
        "engine.parametros.ErroParametros",
        # engine.ciclo_mensal — só a exceção (T-55, EC-03), nunca cálculo.
        "engine.ciclo_mensal.ErroInvariante",
        # engine.gates — só o tipo de dado da ORDEM_ACOES (T-74), nunca gate.
        "engine.gates.AcaoRequerida",
        # engine.portas — as duas portas
        "engine.portas.FonteParametros",
        "engine.portas.RepositorioSnapshots",
        # engine.comportamento — as DUAS derivações comportamentais do
        # Bloco 2, e só elas (`T-176`).
        #
        # **Por que entram, depois de terem sido deliberadamente deixadas
        # de fora.** `CONFIABILIDADE_DADOS` é o último parâmetro que
        # `montar_estado_financeiro` recebia de fora sem ter fonte
        # (`T-106`), e a implementação padrão de
        # `obter_parametros_externos_do_bloco6` BLOQUEAVA o cálculo com
        # `503` em vez de inventar um valor — corretamente, porque o enum
        # `ALTA`/`MEDIA`/`BAIXA` não tem membro neutro e qualquer default
        # fixo seria uma afirmação sobre confiabilidade que ninguém
        # calculou (`sdd.config.md` §4, "não inventar dado").
        #
        # O resultado era que o Bloco 6 não podia ser disparado por
        # NENHUM caminho HTTP: com a coleta inteira respondida, `POST
        # /caso/{id}/calculo` respondia `503` para sempre.
        #
        # **Onde a derivação passa a acontecer decide se isto é violação
        # ou não.** `app/montagem/estado.py` já dizia qual era o caminho
        # certo: *"A chamadora (Bloco 6) é responsável por invocar a
        # derivação de dentro do motor, nunca de `app/`"*. É exatamente o
        # que `app/motor/executor.py` faz — ele É o Bloco 6, o módulo cujo
        # trabalho é orquestrar o motor, e a derivação roda no mesmo fluxo
        # de `calcular_plano`, antes dele. `RF-16` proíbe *reproduzir* um
        # passo do cálculo na aplicação; chamar a função do próprio motor,
        # sem reimplementar nada, é o oposto disso.
        #
        # Nenhum outro nome de `engine.comportamento` entra: as duas
        # derivações do Bloco 2, e nada mais. Os gates, as fórmulas
        # financeiras e o ciclo mensal continuam inalcançáveis de `app/`.
        "engine.comportamento.derivar_NIVEL_CONTROLE",
        "engine.comportamento.derivar_CONFIABILIDADE_DADOS",
        # engine.precisao — módulo inteiro
        "engine.precisao",
        "engine.precisao.dinheiro",
        "engine.precisao.quantizar_exibicao",
        "engine.precisao.CONTEXTO_MOTOR",
    }
)

# Módulos cujo CONTEÚDO inteiro é permitido — `from engine.tipos import X`
# é permitido para qualquer `X` (tipos e enums de engine/tipos.py, RF-34).
# `engine.precisao` também está aqui: além do módulo (`import engine.precisao`),
# qualquer atributo seu é permitido, já que a spec autoriza "engine.precisao"
# como um todo, sem enumerar cada nome do módulo.
MODULOS_LIBERADOS_POR_INTEIRO: Final[frozenset[str]] = frozenset(
    {
        "engine.tipos",
        "engine.precisao",
    }
)


@dataclass(frozen=True, slots=True)
class ViolacaoImportEngine:
    arquivo: str
    linha: int
    descricao: str


def _e_import_de_engine(modulo: str) -> bool:
    return modulo == "engine" or modulo.startswith("engine.")


def _nome_liberado(nome_completo: str) -> bool:
    """`nome_completo` é o caminho pontilhado completo já resolvido (módulo +
    nome importado, para `ImportFrom`; ou o próprio módulo, para `Import`)."""
    if nome_completo in NOMES_PERMITIDOS_DE_ENGINE:
        return True
    return any(
        nome_completo == modulo_liberado or nome_completo.startswith(modulo_liberado + ".")
        for modulo_liberado in MODULOS_LIBERADOS_POR_INTEIRO
    )


def verificar_arquivo(codigo_fonte: str, nome_arquivo: str) -> list[ViolacaoImportEngine]:
    """Percorre a AST de `codigo_fonte` e devolve toda violação da fronteira
    de import com `engine/` (AC-41). Nunca importa o arquivo — só o parseia.

    Cobre três formas de import:
    - `import engine.gates` / `import engine.gates as g` — módulo interno
      inteiro, sempre violação (não há módulo interno na allowlist).
    - `from engine.motor import calcular_plano` — permitido só se o nome
      pontilhado completo (`engine.motor.calcular_plano`) estiver na
      allowlist, ou pertencer a um módulo liberado por inteiro.
    - `from engine import *` / `from engine import gates` — `import *` é
      sempre violação (nenhum uso de `*` permite provar o que foi trazido);
      `from engine import <nome>` só é permitido se `engine.<nome>` estiver
      liberado (não há caso hoje: os nomes permitidos sempre pertencem a um
      submódulo, nunca a `engine/__init__.py` diretamente).
    """
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoImportEngine] = []

    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for alias in no.names:
                if not _e_import_de_engine(alias.name):
                    continue
                if not _nome_liberado(alias.name):
                    violacoes.append(
                        ViolacaoImportEngine(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao=(
                                f"import de módulo interno não permitido: `import {alias.name}`"
                            ),
                        )
                    )
        elif isinstance(no, ast.ImportFrom):
            modulo = no.module or ""
            if not _e_import_de_engine(modulo) and modulo != "engine":
                continue
            if not _e_import_de_engine(modulo):
                continue
            for alias in no.names:
                if alias.name == "*":
                    violacoes.append(
                        ViolacaoImportEngine(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao=(
                                f"`from {modulo} import *` — allowlist inexprimível com wildcard"
                            ),
                        )
                    )
                    continue
                nome_completo = f"{modulo}.{alias.name}"
                if not _nome_liberado(nome_completo):
                    violacoes.append(
                        ViolacaoImportEngine(
                            arquivo=nome_arquivo,
                            linha=no.lineno,
                            descricao=(
                                f"import não permitido de engine/: "
                                f"`from {modulo} import {alias.name}` "
                                f"({nome_completo!r} fora da allowlist)"
                            ),
                        )
                    )

    return violacoes


def _mensagem(violacoes: list[ViolacaoImportEngine]) -> str:
    return "import proibido de engine/ interno (AC-41):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )


def test_pastas_da_aplicacao_nao_importam_engine_interno_ac_41() -> None:
    """`app/`, `collection/` e `report/` só importam de `engine/` o que a
    allowlist permite. Passa com as três pastas ainda vazias (só
    `__init__.py`, sem import de `engine`)."""
    violacoes: list[ViolacaoImportEngine] = []
    for pasta in PASTAS_VERIFICADAS:
        for arquivo in sorted(pasta.rglob("*.py")):
            codigo_fonte = arquivo.read_text(encoding="utf-8")
            violacoes.extend(verificar_arquivo(codigo_fonte, str(arquivo)))

    assert not violacoes, _mensagem(violacoes)


def test_detector_pega_import_de_engine_gates_ac_41() -> None:
    """`import engine.gates` — módulo interno do cálculo, nunca permitido."""
    codigo_com_violacao = """
import engine.gates

def usar():
    return engine.gates.particionar_elegibilidade
"""
    violacoes = verificar_arquivo(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que o detector pegasse `import engine.gates`"
    assert violacoes[0].linha == 2
    assert "engine.gates" in violacoes[0].descricao


def test_detector_pega_from_import_de_ciclo_mensal_ac_41() -> None:
    """`from engine.ciclo_mensal import simular_cenario` — não está na
    allowlist (só o ponto de entrada `calcular_plano` está)."""
    codigo_com_violacao = "from engine.ciclo_mensal import simular_cenario\n"
    violacoes = verificar_arquivo(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, (
        "esperava que o detector pegasse `from engine.ciclo_mensal import simular_cenario`"
    )
    assert violacoes[0].linha == 1
    assert "engine.ciclo_mensal.simular_cenario" in violacoes[0].descricao


def test_detector_pega_from_import_de_metodos_avalanche_ac_41() -> None:
    """`from engine.metodos.avalanche import ...` — submódulo de
    `engine.metodos`, nunca permitido."""
    codigo_com_violacao = "from engine.metodos.avalanche import criar_selecionar_alvo_avalanche\n"
    violacoes = verificar_arquivo(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que o detector pegasse import de engine.metodos.avalanche"


def test_detector_pega_from_import_de_comparacao_ac_41() -> None:
    """`from engine.comparacao import comparar_cenarios` — proibido."""
    codigo_com_violacao = "from engine.comparacao import comparar_cenarios\n"
    violacoes = verificar_arquivo(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que o detector pegasse import de engine.comparacao"


def test_detector_pega_from_import_de_ordem_ac_41() -> None:
    """`from engine.ordem import publicar_ORDEM_QUITACAO` — proibido."""
    codigo_com_violacao = "from engine.ordem import publicar_ORDEM_QUITACAO\n"
    violacoes = verificar_arquivo(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que o detector pegasse import de engine.ordem"


def test_detector_pega_from_engine_import_estrela_ac_41() -> None:
    """`from engine import *` — wildcard nunca é permitido, mesmo que todo o
    conteúdo real de `engine/__init__.py` seja inócuo: a allowlist é
    inexprimível contra `*`, porque não há como provar o que foi trazido."""
    codigo_com_violacao = "from engine import *\n"
    violacoes = verificar_arquivo(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que o detector pegasse `from engine import *`"
    assert "*" in violacoes[0].descricao


def test_detector_nomeia_arquivo_e_linha_da_violacao_ac_41() -> None:
    """O critério de aceite exige que a falha nomeie arquivo e linha —
    verificado diretamente nos campos de `ViolacaoImportEngine`."""
    codigo_com_violacao = """
def a():
    pass


import engine.gates
"""
    violacoes = verificar_arquivo(codigo_com_violacao, "app/exemplo.py")

    assert len(violacoes) == 1
    assert violacoes[0].arquivo == "app/exemplo.py"
    assert violacoes[0].linha == 6


def test_detector_aceita_calcular_plano_e_tipos_permitidos_ac_41() -> None:
    """Prova negativa: os imports que a allowlist explicitamente autoriza não
    geram violação — evita que o detector seja tão restritivo a ponto de
    barrar o próprio uso legítimo previsto pela Lei nº 3."""
    codigo_permitido = """
from engine.motor import calcular_plano
from engine.estado import EstadoFinanceiro, Divida, TIPO_DIVIDA
from engine.estado import PerfilComportamental, SinaisComportamentais, JANELA_NOVA_DIVIDA
from engine.estado import REGISTRO_GASTOS, FREQUENCIA_REGISTRO, DEFASAGEM_REGISTRO
from engine.estado import COBERTURA_PEQUENOS_GASTOS, COBERTURA_MEIOS_PAGAMENTO
from engine.estado import CONHECIMENTO_GASTO, GASTOS_NAO_IDENTIFICADOS, REVISAO_SEMANAL
from engine.snapshot import SnapshotOrdem
from engine.parametros import Parametros
from engine.gates import AcaoRequerida
from engine.portas import FonteParametros, RepositorioSnapshots
from engine.tipos import Dinheiro, DinheiroTalvez, DESCONHECIDO, METODO
from engine.precisao import dinheiro, quantizar_exibicao
import engine.precisao
"""
    violacoes = verificar_arquivo(codigo_permitido, "caso_permitido.py")

    assert not violacoes, _mensagem(violacoes)


def test_detector_pega_import_simples_de_engine_sem_submodulo_ac_41() -> None:
    """`import engine` sozinho não dá acesso a nenhum nome liberado por
    caminho pontilhado — tratado como violação, pois não há uso de `engine`
    "puro" na allowlist (todo nome permitido pertence a um submódulo)."""
    codigo_com_violacao = "import engine\n"
    violacoes = verificar_arquivo(codigo_com_violacao, "caso_proposital.py")

    assert violacoes, "esperava que `import engine` sozinho fosse pego como violação"
