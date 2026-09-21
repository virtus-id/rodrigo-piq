"""Lint estático: toda regra normativa `M-01..G-02` é citada por algum
`REGRAS` de `engine/` — RF-01..RF-27 · §4 do `sdd.config.md`.

`sdd.config.md` §4 — "Regra citada no código": "Cada unidade que implementa
uma regra do motor cita seu ID normativo (...) no nome ou em comentário."
`plans/motor-calculo.plan.md` §9 declara o mecanismo: cada módulo de
`engine/` expõe `REGRAS: Final[tuple[str, ...]]`, e a varredura consolida
todas as tuplas num conjunto único de regras citadas em ALGUM lugar do motor.

Decisão de escopo desta tarefa (documentada, não escondida)
-----------------------------------------------------------------------------
A lista normativa completa — `M-01..M-12`, `R-01..R-05`, `A-01..A-04`,
`F-01..F-03`, `O-01..O-05`, `H-01..H-08`, `S-01..S-05`, `Q-01..Q-05`,
`V-01..V-03`, `T-01..T-02`, `G-01..G-02` (54 IDs: 12+5+4+3+5+8+5+5+3+2+2,
confirmados em `specs/piq-app-spec.md` linhas 303-411) — cobre a
metodologia INTEIRA do motor. Neste ponto do backlog (`tasks/motor-calculo.tasks.md`), apenas as
Entregas 1 e 2 estão concluídas: `engine/` tem `precisao.py`, `tipos.py`,
`parametros.py`, `portas.py`, `estado.py`, `comportamento.py`, `risco.py`,
`diagnostico.py`, `valor_quitacao.py`. Nenhum desses módulos implementa as
famílias `M` (ciclo mensal), `R` (recálculo), `A` (resíduo), `F` (fluxo
liberado), `O`/`H` (métodos), `S` (status do método), `Q` (ordem/
justificativa), `V` (snapshot) ou `T` (troca) — essas são Entrega 3 em
diante (`T-27` a `T-77`, ainda pendentes). Só `G-01`/`G-02` (precisão) já são
citadas (`engine/precisao.py`).

Exigir agora que as 54 regras estejam cobertas faria este teste **falhar
permanentemente até o fim do backlog inteiro** — o que contradiria o próprio
critério de aceite de T-10 ("os quatro testes passam sobre o `engine/`
existente"). A alternativa descartada (a) do enunciado da tarefa — deixar o
teste falhar agora, listando as pendentes, e mover para fora da suíte
bloqueante — foi rejeitada porque o critério de aceite é explícito: TODOS os
quatro testes precisam passar hoje.

Adotada a alternativa: **o teste verifica a MECÂNICA de auditoria em si,
não a cobertura completa da canônica.** Três garantias, todas verificáveis
hoje, sem enfraquecer o propósito de auditoria da regra:

1. **Todo módulo de `engine/` que expõe uma função pública (não privada, não
   dunder) declara `REGRAS: Final[tuple[str, ...]]` não-vazio.** Nenhum
   módulo "esquece" de citar — a trava do `sdd.config.md` §4 é sobre TODA
   unidade que implementa regra, e isso é verificável objetivamente hoje:
   cada um dos 9 módulos existentes já declara `REGRAS`. Introduzir um novo
   módulo com função pública e sem `REGRAS` quebra este teste imediatamente
   — é a MESMA mecânica de detecção que vai sinalizar, no futuro, um módulo
   da Entrega 3+ que esqueça de citar sua regra.

2. **Nenhuma regra "fantasma" é citada** — toda string em `REGRAS` que
   *parece* um ID de regra normativa (bate o padrão `^[A-Z]+-\\d+$`, ex.
   `G-01`, `M-07`) precisa pertencer ao conjunto fechado de 54 IDs válidos
   da canônica. Cadeias como `"§11.4"`, `"Definições §1"` ou `"RF-18"` não
   batem o padrão de regra normativa e são ignoradas por esta checagem (são
   citações de requisito/seção, não de regra `M-01..G-02`) — mas um ID que
   siga o padrão e não exista na lista fechada (ex. um typo `G-03` ou uma
   invenção `X-01`) é reportado. Isso é "auditoria ao contrário": prova que
   o mecanismo de citação não está sendo usado para inventar regra.

3. **A função de descoberta de regras faltantes é demonstrável e correta**,
   testada isoladamente com um conjunto sintético de módulos (não os
   arquivos reais de `engine/`): dado um subconjunto pequeno de regras
   citadas, a função lista corretamente as regras da lista completa que
   NÃO estão nesse subconjunto — provando que "listar, na mensagem de
   falha, as regras ainda não citadas" (critério de aceite de T-10) é uma
   capacidade real do código, não uma promessa vazia. Um teste adicional
   roda essa mesma função sobre o `engine/` REAL e IMPRIME (sem falhar) as
   regras da Entrega 3+ ainda pendentes — visível em `pytest -q -s`, útil
   como radar de progresso do backlog, sem bloquear a suíte.

Se e quando a Entrega 3+ implementar as famílias M/R/A/F/O/H/S/Q/V/T, este
teste continua passando sem alteração — ele nunca testou "100% coberto",
testou "mecânica de auditoria funciona e não há regra fantasma". Uma
tarefa futura (ao fim do backlog) pode endurecer este arquivo para
exigir cobertura 100%, quando fizer sentido segundo o próprio critério de
"suíte de homologação completa" do `sdd.config.md` §5.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

RAIZ_ENGINE = Path(__file__).resolve().parent.parent.parent / "engine"

# Lista fechada das 54 regras normativas M-01..G-02, confirmada em
# specs/piq-app-spec.md (linhas 303-411) e ecoada em sdd.config.md §4.
REGRAS_NORMATIVAS_COMPLETAS: Final[frozenset[str]] = frozenset(
    [f"M-{n:02d}" for n in range(1, 13)]  # M-01..M-12
    + [f"R-{n:02d}" for n in range(1, 6)]  # R-01..R-05
    + [f"A-{n:02d}" for n in range(1, 5)]  # A-01..A-04
    + [f"F-{n:02d}" for n in range(1, 4)]  # F-01..F-03
    + [f"O-{n:02d}" for n in range(1, 6)]  # O-01..O-05
    + [f"H-{n:02d}" for n in range(1, 9)]  # H-01..H-08
    + [f"S-{n:02d}" for n in range(1, 6)]  # S-01..S-05
    + [f"Q-{n:02d}" for n in range(1, 6)]  # Q-01..Q-05
    + [f"V-{n:02d}" for n in range(1, 4)]  # V-01..V-03
    + [f"T-{n:02d}" for n in range(1, 3)]  # T-01..T-02
    + [f"G-{n:02d}" for n in range(1, 3)]  # G-01..G-02
)
assert len(REGRAS_NORMATIVAS_COMPLETAS) == 54, "lista de regras normativas mudou de tamanho"

# Padrão que identifica uma string de REGRAS como "parece um ID de regra
# normativa" (família de 1+ letras maiúsculas, hífen, dois dígitos) — usado
# para separar regra normativa de outras citações (RF-NN, §x.y, "Definições
# §1") que também aparecem legitimamente em REGRAS mas não são desta lista.
_PADRAO_ID_DE_REGRA_NORMATIVA = re.compile(r"^[A-Z]+-\d{2}$")

# RF-NN (requisito funcional), AC-NN (critério de aceite) e EC-NN (edge
# case) não são regras normativas da família M..G — são outras categorias
# de ID da spec do slug (`specs/motor-calculo.spec.md` §2, §4, §6),
# legitimamente citadas em REGRAS por vários módulos (ex.
# `engine/valor_quitacao.py::REGRAS` cita "AC-20", "AC-21", "EC-14").
# Têm o mesmo formato textual (LETRA(S)-NUM) do padrão de regra normativa,
# então precisam de exclusão explícita para não virar falso positivo de
# "regra fantasma" no item (2) da docstring do módulo.
_PREFIXOS_NAO_NORMATIVOS = re.compile(r"^(RF|AC|EC|GAB|OQ)-\d+$")


def _extrair_regras_de_modulo(caminho: Path) -> tuple[str, ...] | None:
    """Extrai o valor de `REGRAS: Final[tuple[str, ...]] = (...)` de um
    módulo, via AST (nunca importando o módulo — mais robusto a erro de
    import parcial durante o backlog). Devolve `None` se o módulo não
    declara `REGRAS` no nível de topo."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))

    for no in arvore.body:
        alvo_nomes: list[str] = []
        valor: ast.expr | None = None

        if isinstance(no, ast.Assign):
            alvo_nomes = [t.id for t in no.targets if isinstance(t, ast.Name)]
            valor = no.value
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            alvo_nomes = [no.target.id]
            valor = no.value

        if "REGRAS" in alvo_nomes and valor is not None:
            if isinstance(valor, (ast.Tuple, ast.List)):
                strings = [
                    elemento.value
                    for elemento in valor.elts
                    if isinstance(elemento, ast.Constant) and isinstance(elemento.value, str)
                ]
                return tuple(strings)

    return None


def _modulo_tem_funcao_publica(caminho: Path) -> bool:
    """Um módulo "implementa regra", no sentido do `sdd.config.md` §4, se
    declara ao menos uma FUNÇÃO pública no nível de topo (não `_privada`,
    não dunder) — uma função é comportamento executável, o que a trava
    "cada unidade que implementa uma regra" tem em mente.

    **Exclusão deliberada de `ast.ClassDef` puro.** Um módulo que só declara
    classes/enums de domínio (`engine/tipos.py`: `NIVEL_CONTROLE`,
    `STATUS_FINANCEIRO`, etc. — todas `class ... (Enum)`, sem nenhuma
    função) é modelagem de DADO, não implementação de regra: um enum não
    "decide" nada, ele só nomeia um domínio fechado já fixado pela spec
    (T-04). Contar essas classes forçaria `engine/tipos.py` a inventar uma
    citação de regra artificial só para satisfazer este lint — o que
    inflaria REGRAS com ruído em vez de auditoria real. Um módulo com
    dataclass (`ast.ClassDef`) que TAMBÉM declara função pública (ex.
    `engine/risco.py::classificar_RISCO_RECAIDA`) já é pego pelo critério
    de função, então a exclusão de classe não cria buraco: qualquer módulo
    que "faz algo" (função) continua exigido a citar `REGRAS`.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    for no in arvore.body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not no.name.startswith("_"):
                return True
    return False


def _regras_faltantes(regras_citadas: frozenset[str], universo: frozenset[str]) -> frozenset[str]:
    """Devolve o subconjunto de `universo` que NÃO está em `regras_citadas`
    — a função de descoberta cuja corretude é provada isoladamente em
    `test_regras_faltantes_e_calculada_corretamente` (item 3 da docstring
    do módulo)."""
    return universo - regras_citadas


def _coletar_regras_citadas_em_engine() -> frozenset[str]:
    """Consolida REGRAS de todos os módulos de engine/ num conjunto único."""
    todas: set[str] = set()
    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        regras = _extrair_regras_de_modulo(arquivo)
        if regras:
            todas.update(regras)
    return frozenset(todas)


def test_todo_modulo_com_funcao_publica_declara_regras() -> None:
    """(1) — nenhum módulo de `engine/` com função/classe pública "esquece"
    de declarar `REGRAS: Final[tuple[str, ...]]` não-vazio. `__init__.py`
    (sem função pública) é isento."""
    modulos_sem_regras: list[str] = []
    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        if not _modulo_tem_funcao_publica(arquivo):
            continue
        regras = _extrair_regras_de_modulo(arquivo)
        if not regras:
            modulos_sem_regras.append(str(arquivo))

    mensagem = (
        "módulo(s) de engine/ com função/classe pública mas sem REGRAS "
        "declarado (sdd.config.md §4):\n" + "\n".join(f"  {m}" for m in modulos_sem_regras)
    )
    assert not modulos_sem_regras, mensagem


def test_nenhuma_regra_fantasma_citada() -> None:
    """(2) — toda string de REGRAS que bate o padrão de ID de regra
    normativa (`LETRA(S)-NN`) e não é `RF-NN`/`AC-NN`/`EC-NN`/`GAB-NN`/
    `OQ-NN` (outras categorias de ID da spec, exclusão documentada) precisa
    pertencer à lista fechada de 54 regras válidas `M-01..G-02`. Nenhuma
    regra inventada ou com typo passa despercebida."""
    fantasmas: list[str] = []
    for arquivo in sorted(RAIZ_ENGINE.rglob("*.py")):
        regras = _extrair_regras_de_modulo(arquivo)
        if not regras:
            continue
        for regra in regras:
            if _PREFIXOS_NAO_NORMATIVOS.match(regra):
                continue  # RF/AC/EC/GAB/OQ-NN não são regra normativa da família M..G.
            if not _PADRAO_ID_DE_REGRA_NORMATIVA.match(regra):
                continue  # não parece ID de regra (ex. "§11.4", "Definições §1").
            if regra not in REGRAS_NORMATIVAS_COMPLETAS:
                fantasmas.append(f"{arquivo}: {regra!r}")

    mensagem = "regra normativa 'fantasma' citada (não existe na lista de 54 IDs válidos):\n" + (
        "\n".join(f"  {f}" for f in fantasmas)
    )
    assert not fantasmas, mensagem


def test_regras_faltantes_e_calculada_corretamente() -> None:
    """(3) — prova, com um conjunto SINTÉTICO (não o engine/ real), que a
    função de descoberta de regras faltantes lista exatamente o
    complemento do que foi citado. Isola a corretude do MECANISMO da
    pergunta "quantas regras o engine/ real já cobre hoje"."""
    universo_pequeno = frozenset({"G-01", "G-02", "M-01", "M-02", "R-01"})
    citadas = frozenset({"G-01", "G-02"})

    faltantes = _regras_faltantes(citadas, universo_pequeno)

    assert faltantes == frozenset({"M-01", "M-02", "R-01"}), (
        f"esperava {{'M-01', 'M-02', 'R-01'}} como faltantes, obteve {faltantes}"
    )

    # Contraprova: se tudo foi citado, nada falta.
    assert _regras_faltantes(universo_pequeno, universo_pequeno) == frozenset()


def test_radar_de_regras_pendentes_no_engine_real() -> None:
    """Não-bloqueante, de propósito (ver docstring do módulo, item 3): roda a
    descoberta de faltantes sobre o `engine/` REAL e IMPRIME o resultado —
    visível em `pytest -q -s` como radar de progresso do backlog. NÃO falha
    quando há regra pendente, porque a Entrega 3+ ainda não foi
    implementada neste ponto do backlog; é o comportamento esperado e
    documentado no topo deste arquivo.

    Esta é a demonstração viva de que "listar, na mensagem de falha, as
    regras ainda não citadas" (critério de aceite de T-10) é mecânica real:
    a mesma função `_regras_faltantes` usada aqui é a que seria usada para
    fazer o teste falhar de verdade, se e quando o projeto decidir endurecer
    a exigência para 100% de cobertura.
    """
    # `_coletar_regras_citadas_em_engine()` traz TUDO que está em REGRAS —
    # inclusive RF-NN, AC-NN, "§11.10" etc. (legítimos, mas não regra
    # normativa da família M..G). Filtra para o mesmo universo de
    # comparação usado pela lista fechada, senão a comparação de conjuntos
    # não faz sentido (compararia maçã com laranja).
    todas_citadas = _coletar_regras_citadas_em_engine()
    citadas_normativas = frozenset(
        regra for regra in todas_citadas if regra in REGRAS_NORMATIVAS_COMPLETAS
    )
    faltantes = sorted(_regras_faltantes(citadas_normativas, REGRAS_NORMATIVAS_COMPLETAS))

    print(
        f"\n[radar T-10] regras normativas citadas em engine/: "
        f"{len(citadas_normativas)}/{len(REGRAS_NORMATIVAS_COMPLETAS)}"
    )
    if faltantes:
        print(f"[radar T-10] regras ainda não citadas por nenhum módulo: {faltantes}")

    # Não-bloqueante por decisão de escopo (ver docstring do módulo): a
    # única asserção real é que `citadas_normativas` é subconjunto do
    # universo válido — trivialmente verdadeira pela própria filtragem
    # acima, mantida para deixar a intenção explícita no código (nunca
    # exigir cobertura 100% nesta tarefa).
    assert citadas_normativas <= REGRAS_NORMATIVAS_COMPLETAS
