"""Não-modificação de `engine/` e `persistencia/` por esta feature — AC-44.

`AC-44`: "nenhum arquivo de `engine/` ou de `persistencia/supabase/` (exceto a
migração nova) modificado — verificado por hash." A Lei nº 1
(`plans/motor-calculo.plan.md` §1) e a regra deste backlog (cabeçalho de
`tasks/app-aluno.tasks.md`) dizem que **nenhuma tarefa deste slug edita**
`engine/` nem `persistencia/supabase/{conexao,fonte_parametros,
repositorio_snapshots}.py` nem `persistencia/arquivo/`. Este teste é o portão
que torna essa promessa verificável: registra o hash SHA-256 de cada arquivo
do conjunto congelado em `hashes_congelados.json` (versionado) e falha,
nomeando o arquivo, se o conteúdo em disco divergir do hash gravado.

Conjunto congelado
-------------------
- Todo `.py` de `engine/` (recursivo, exceto `__pycache__`).
- Todo `.py` de `persistencia/arquivo/` (recursivo, exceto `__pycache__`).
- Todo `.py` de `persistencia/supabase/` (recursivo, exceto `__pycache__`).
- `persistencia/supabase/migracoes/001_inicial.sql` — a migração que já
  existia antes desta feature.

Fora do conjunto congelado, DELIBERADAMENTE
--------------------------------------------
`persistencia/supabase/migracoes/002_app_aluno.sql` é a migração NOVA desta
feature (`T-21`), que ainda não existe no momento em que este teste foi
escrito. Ela nunca deve entrar em `hashes_congelados.json` — é o próprio
trabalho desta feature, não algo a proteger de edição. Se algum dia um agente
adicionar essa migração ao JSON por engano, `test_migracao_nova_esta_fora_do_conjunto_congelado`
pega o erro.

A exceção normativa prevista, e o procedimento para quando ela chegar
----------------------------------------------------------------------
O cabeçalho de `tasks/app-aluno.tasks.md` e `plans/app-aluno.plan.md` (tabela
da fronteira de pastas) preveem três mudanças futuras em
`engine/gates.py::AcaoRequerida`:

1. os campos novos `ACAO_ID`/`TIPO_ACAO`;
2. o Gate 1 passando a emitir `AcaoRequerida` de tipo informação;
3. a ação de economia emitida fora do fluxo de gates.

As três são trabalho do slug **`motor-calculo`**, nunca deste backlog
(`app-aluno`). Quando esse slug entregar essa mudança, o hash de
`engine/gates.py` registrado aqui ficará desatualizado **de propósito** — este
teste vai falhar, e isso é o comportamento correto, não um bug. O
procedimento nesse momento é:

1. Confirmar que a mudança em `engine/gates.py` veio do slug `motor-calculo`
   (nunca de uma tarefa deste backlog — se vier daqui, é a Lei nº 1 sendo
   violada, e a correção é reverter o arquivo, não o hash).
2. Recalcular o hash SHA-256 do novo `engine/gates.py` e atualizar SÓ essa
   entrada em `hashes_congelados.json`, deliberada e explicitamente (nunca
   regenerando o arquivo inteiro às cegas, para não mascarar uma modificação
   não relacionada em outro arquivo do conjunto).
3. Deixar registrado, na mensagem do commit que atualiza o hash, qual das três
   mudanças previstas motivou a atualização.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

RAIZ_PROJETO: Final[Path] = Path(__file__).resolve().parent.parent.parent.parent
CAMINHO_HASHES: Final[Path] = Path(__file__).resolve().parent / "hashes_congelados.json"

# Migração desta feature (T-21) — deliberadamente FORA do conjunto congelado.
# Ver docstring do módulo. Não deve constar de `hashes_congelados.json`.
MIGRACAO_NOVA_FORA_DO_CONGELAMENTO: Final[str] = (
    "persistencia/supabase/migracoes/002_app_aluno.sql"
)


def _carregar_hashes_gravados() -> dict[str, str]:
    with CAMINHO_HASHES.open(encoding="utf-8") as arquivo:
        return dict(json.load(arquivo))


def _hash_sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _descobrir_conjunto_congelado_em_disco() -> set[str]:
    """Reconstrói, a partir do disco, o conjunto de caminhos que DEVERIAM
    estar congelados hoje: todo `.py` de `engine/` e de `persistencia/`
    (recursivo, exceto `__pycache__`), mais `001_inicial.sql`. Serve só para
    o teste de cobertura do JSON — a verificação de integridade em si usa
    apenas os caminhos gravados em `hashes_congelados.json` (item 3 do
    critério de aceite não exige detectar arquivo NOVO, só arquivo
    MODIFICADO)."""
    caminhos: set[str] = set()

    for raiz in ("engine", "persistencia/arquivo", "persistencia/supabase"):
        base = RAIZ_PROJETO / raiz
        if not base.exists():
            continue
        for arquivo in base.rglob("*.py"):
            if "__pycache__" in arquivo.parts:
                continue
            caminhos.add(arquivo.relative_to(RAIZ_PROJETO).as_posix())

    migracao_antiga = RAIZ_PROJETO / "persistencia/supabase/migracoes/001_inicial.sql"
    if migracao_antiga.exists():
        caminhos.add(migracao_antiga.relative_to(RAIZ_PROJETO).as_posix())

    return caminhos


def test_ac44_hashes_congelados_batem_com_o_conteudo_atual_dos_arquivos() -> None:
    """Recalcula o SHA-256 de cada arquivo listado em `hashes_congelados.json`
    e compara ao valor gravado. Deve passar hoje — nenhum arquivo do conjunto
    congelado foi tocado por este backlog. Se um agente futuro editar um
    byte de qualquer um deles, o hash recalculado diverge e a asserção falha
    nomeando o arquivo culpado."""
    hashes_gravados = _carregar_hashes_gravados()
    divergencias: list[str] = []

    for caminho_relativo, hash_gravado in sorted(hashes_gravados.items()):
        caminho_absoluto = RAIZ_PROJETO / caminho_relativo
        if not caminho_absoluto.exists():
            divergencias.append(
                f"{caminho_relativo}: arquivo ausente (esperava hash {hash_gravado})"
            )
            continue
        hash_atual = _hash_sha256(caminho_absoluto)
        if hash_atual != hash_gravado:
            divergencias.append(
                f"{caminho_relativo}: hash divergente "
                f"(gravado {hash_gravado}, atual {hash_atual}) — arquivo do conjunto "
                f"congelado (AC-44) foi modificado"
            )

    mensagem = "arquivo(s) congelado(s) modificado(s) (AC-44):\n" + "\n".join(
        f"  {linha}" for linha in divergencias
    )
    assert not divergencias, mensagem


def test_ac44_json_cobre_todo_py_de_engine_e_persistencia_e_a_migracao_antiga() -> None:
    """O JSON não pode ficar para trás: todo `.py` de `engine/`, de
    `persistencia/arquivo/`, de `persistencia/supabase/` e a migração
    `001_inicial.sql` precisam estar listados em `hashes_congelados.json`."""
    hashes_gravados = _carregar_hashes_gravados()
    esperado = _descobrir_conjunto_congelado_em_disco()

    faltando_no_json = esperado - set(hashes_gravados)
    assert not faltando_no_json, (
        "arquivo(s) do conjunto congelado (AC-44) ausente(s) de "
        f"hashes_congelados.json: {sorted(faltando_no_json)}"
    )


def test_ac44_migracao_nova_desta_feature_esta_fora_do_conjunto_congelado() -> None:
    """`persistencia/supabase/migracoes/002_app_aluno.sql` (T-21, ainda não
    escrita no momento desta tarefa) nunca deve constar de
    `hashes_congelados.json` — ela é o trabalho desta feature, não algo a
    proteger de edição."""
    hashes_gravados = _carregar_hashes_gravados()
    assert MIGRACAO_NOVA_FORA_DO_CONGELAMENTO not in hashes_gravados, (
        f"{MIGRACAO_NOVA_FORA_DO_CONGELAMENTO} é a migração nova desta feature "
        "(T-21) e não deve fazer parte do conjunto congelado (AC-44)"
    )


def test_ac44_alterar_um_byte_muda_o_hash_e_seria_detectado() -> None:
    """Prova sintética de que a detecção funciona, sem tocar em nenhum
    arquivo real de `engine/`/`persistencia/`: lê um arquivo real do conjunto
    congelado, calcula seu hash a partir dos bytes em memória, altera 1 byte
    **apenas na cópia em memória** e mostra que o hash resultante diverge do
    hash gravado — exatamente o sinal que faria o primeiro teste deste
    módulo falhar, nomeando o arquivo, se a modificação fosse real."""
    hashes_gravados = _carregar_hashes_gravados()
    caminho_relativo = "engine/gates.py"
    assert caminho_relativo in hashes_gravados, (
        f"{caminho_relativo} deveria estar no conjunto congelado para esta prova"
    )

    conteudo_original = (RAIZ_PROJETO / caminho_relativo).read_bytes()
    hash_original = hashlib.sha256(conteudo_original).hexdigest()
    assert hash_original == hashes_gravados[caminho_relativo]

    # Altera 1 byte só na cópia em memória — o arquivo real em disco nunca é
    # escrito.
    primeiro_byte = conteudo_original[0]
    byte_alterado = (primeiro_byte + 1) % 256
    conteudo_com_um_byte_alterado = bytes([byte_alterado]) + conteudo_original[1:]
    hash_com_um_byte_alterado = hashlib.sha256(conteudo_com_um_byte_alterado).hexdigest()

    assert hash_com_um_byte_alterado != hashes_gravados[caminho_relativo], (
        "esperava que alterar 1 byte mudasse o hash SHA-256 — a detecção de "
        "modificação (AC-44) depende dessa propriedade"
    )
