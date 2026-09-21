"""Nenhuma escrita de snapshot fora de `RepositorioSnapshots.anexar` — RF-19,
AC-43.

`AC-43`: "o teste estático falha se qualquer SQL desta feature mencionar a
tabela de snapshots com verbo de mutação." A única porta de escrita de
snapshot é `RepositorioSnapshots.anexar` (`engine/portas.py`), sobre
`motor_calculo.snapshots` — e essa porta é implementada e chamada de dentro do
slug `motor-calculo`, fora do escopo deste backlog (`app-aluno`). Nenhuma
tarefa de `app-aluno` deveria conter, em código Python OU em SQL de migração,
um `INSERT`/`UPDATE`/`DELETE` que mute `motor_calculo.snapshots` diretamente.

Dois alvos, duas técnicas — a mesma dualidade de `test_sem_conteudo_de_
questionario_no_codigo.py` (T-08): AST para `.py`, varredura textual para
`.sql` (AST Python não se aplica a SQL).

(a) Python (`app/`, `collection/`, `report/`, `persistencia/app_aluno/`) —
AST via `ast.parse`. Procura por qualquer string literal que pareça um
comando SQL de mutação (`INSERT`/`UPDATE`/`DELETE`) referenciando a tabela de
snapshot, dentro de `ast.Constant`. Cobre tanto SQL escrito inline quanto
montado por f-string simples (o nó `ast.Constant` de cada pedaço literal da
f-string ainda é visitado por `ast.walk`).

(b) SQL (`persistencia/supabase/migracoes/001_inicial.sql` e
`persistencia/supabase/migracoes/002_app_aluno.sql`) — regex sobre o texto do
arquivo, com os comentários SQL removidos ANTES da busca (ver
`_remover_comentarios_sql` abaixo). Sem essa remoção, um comentário narrativo
que apenas MENCIONA "não fazemos UPDATE em snapshots" already contém as
palavras `UPDATE` e `snapshots` lado a lado e produziria falso positivo — as
docstrings de `001_inicial.sql`/`002_app_aluno.sql` fazem exatamente esse tipo
de comentário. A limitação documentada: comentários que quebram o padrão
`-- ...` de forma incomum (ex.: `/* ... */` aninhado de forma exótica) não são
o padrão usado neste projeto (confirmado nas duas migrações existentes, que
usam só `--`) e não são tratados — se o projeto um dia adotar `/* */`, este
removedor precisa ser estendido.

Verbo de mutação sobre a tabela de snapshot: a regex casa `INSERT INTO`,
`UPDATE` e `DELETE FROM` (com variação de espaço em branco) imediatamente
seguidos do nome qualificado `motor_calculo.snapshots` (com ou sem aspas
duplas no nome da tabela, já que SQL não exige aspas para um identificador em
minúsculas). Isso NÃO inclui `REVOKE UPDATE, DELETE ON motor_calculo.snapshots`
nem `BEFORE UPDATE OR DELETE ON motor_calculo.snapshots` (a trigger de
`001_inicial.sql`) — ambos são declarações de PERMISSÃO/GATILHO, não comandos
de mutação; a regex exige o verbo em posição de COMANDO (`INSERT INTO`/
`UPDATE <tabela> SET`/`DELETE FROM`), nunca em posição de cláusula
(`REVOKE ... ON`, `BEFORE ... ON`).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

RAIZ_PROJETO: Final[Path] = Path(__file__).resolve().parent.parent.parent.parent
PASTAS_PY_AUDITADAS: Final[tuple[str, ...]] = (
    "app",
    "collection",
    "report",
    "persistencia/app_aluno",
)
ARQUIVOS_SQL_AUDITADOS: Final[tuple[str, ...]] = (
    "persistencia/supabase/migracoes/001_inicial.sql",
    "persistencia/supabase/migracoes/002_app_aluno.sql",
)

# Nome qualificado da tabela de snapshot (confirmado em 001_inicial.sql):
# `motor_calculo.snapshots`. Aceita variação de aspas duplas no identificador.
_NOME_TABELA_SNAPSHOT: Final[str] = r'"?motor_calculo"?\."?snapshots"?'

# Padrões de MUTAÇÃO real sobre a tabela — verbo em posição de COMANDO, nunca
# em cláusula de permissão (`REVOKE ... ON`) ou de gatilho (`BEFORE ... ON`).
PADRAO_INSERT: Final[re.Pattern[str]] = re.compile(
    rf"INSERT\s+INTO\s+{_NOME_TABELA_SNAPSHOT}", re.IGNORECASE
)
PADRAO_UPDATE: Final[re.Pattern[str]] = re.compile(
    rf"UPDATE\s+{_NOME_TABELA_SNAPSHOT}\s+SET", re.IGNORECASE
)
PADRAO_DELETE: Final[re.Pattern[str]] = re.compile(
    rf"DELETE\s+FROM\s+{_NOME_TABELA_SNAPSHOT}", re.IGNORECASE
)
PADROES_MUTACAO: Final[tuple[re.Pattern[str], ...]] = (
    PADRAO_INSERT,
    PADRAO_UPDATE,
    PADRAO_DELETE,
)


@dataclass(frozen=True, slots=True)
class ViolacaoEscritaSnapshot:
    arquivo: str
    linha: int
    descricao: str


def _remover_comentarios_sql(texto_sql: str) -> str:
    """Remove todo comentário de linha `-- ...` ANTES da varredura por regex,
    para que um comentário narrativo que apenas MENCIONA os verbos de
    mutação e o nome da tabela (ex.: a docstring desta própria migração,
    explicando por que ela NÃO grava snapshot) não produza falso positivo.

    Limitação documentada: só trata o estilo de comentário `--` até o fim da
    linha, que é o único estilo usado nas migrações deste projeto
    (`001_inicial.sql`, `002_app_aluno.sql`). Comentário em bloco `/* ... */`
    não é removido — não há caso desse estilo no projeto hoje."""
    linhas_sem_comentario = []
    for linha in texto_sql.splitlines():
        posicao_comentario = linha.find("--")
        if posicao_comentario == -1:
            linhas_sem_comentario.append(linha)
        else:
            linhas_sem_comentario.append(linha[:posicao_comentario])
    return "\n".join(linhas_sem_comentario)


def _detectar_mutacao_sql(texto_sql: str, nome_arquivo: str) -> list[ViolacaoEscritaSnapshot]:
    """(b) — varre o SQL (comentários já removidos) linha a linha, para que
    a mensagem de violação nomeie a linha correta do arquivo ORIGINAL."""
    texto_sem_comentarios = _remover_comentarios_sql(texto_sql)
    violacoes: list[ViolacaoEscritaSnapshot] = []

    for numero_linha, linha in enumerate(texto_sem_comentarios.splitlines(), start=1):
        for padrao in PADROES_MUTACAO:
            if padrao.search(linha):
                violacoes.append(
                    ViolacaoEscritaSnapshot(
                        arquivo=nome_arquivo,
                        linha=numero_linha,
                        descricao=(
                            f"comando SQL de mutação sobre tabela de snapshot: {linha.strip()!r}"
                        ),
                    )
                )

    return violacoes


def _detectar_mutacao_python(codigo_fonte: str, nome_arquivo: str) -> list[ViolacaoEscritaSnapshot]:
    """(a) — qualquer literal de string em `.py` que contenha um dos padrões
    de mutação SQL sobre a tabela de snapshot. Não distingue string
    "executável de fato" de string qualquer: uma string LITERAL que contém o
    padrão já é reportada, mesmo que nunca chegue a ser executada — o
    critério de aceite é sobre o que o SQL desta feature MENCIONA, não sobre
    fluxo de execução."""
    arvore = ast.parse(codigo_fonte, filename=nome_arquivo)
    violacoes: list[ViolacaoEscritaSnapshot] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
            continue
        texto_sem_comentarios = _remover_comentarios_sql(no.value)
        for padrao in PADROES_MUTACAO:
            if padrao.search(texto_sem_comentarios):
                violacoes.append(
                    ViolacaoEscritaSnapshot(
                        arquivo=nome_arquivo,
                        linha=no.lineno,
                        descricao=(
                            "literal de string com comando SQL de mutação sobre "
                            f"tabela de snapshot: {no.value!r}"
                        ),
                    )
                )
                break

    return violacoes


def _arquivos_py_das_pastas_auditadas() -> list[Path]:
    arquivos: list[Path] = []
    for nome_pasta in PASTAS_PY_AUDITADAS:
        pasta = RAIZ_PROJETO / nome_pasta
        if pasta.is_dir():
            arquivos.extend(sorted(pasta.rglob("*.py")))
    return arquivos


def test_ac43_nenhum_py_da_feature_contem_sql_de_mutacao_sobre_snapshot() -> None:
    """AC-43: nenhum `.py` de `app/`, `collection/`, `report/` ou
    `persistencia/app_aluno/` contém, como literal de string, um comando SQL
    de `INSERT`/`UPDATE`/`DELETE` sobre `motor_calculo.snapshots`."""
    violacoes: list[ViolacaoEscritaSnapshot] = []
    for arquivo in _arquivos_py_das_pastas_auditadas():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(
            _detectar_mutacao_python(codigo_fonte, str(arquivo.relative_to(RAIZ_PROJETO)))
        )

    mensagem = "escrita de snapshot fora da porta RepositorioSnapshots (AC-43):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )
    assert not violacoes, mensagem


def test_ac43_nenhuma_migracao_desta_feature_contem_sql_de_mutacao_sobre_snapshot() -> None:
    """AC-43: nem `001_inicial.sql` nem `002_app_aluno.sql` contêm um
    `INSERT`/`UPDATE`/`DELETE` de comando (fora de comentário) sobre
    `motor_calculo.snapshots`. A única exceção normativa conhecida —
    `REVOKE UPDATE, DELETE ON motor_calculo.snapshots FROM PUBLIC` e a
    trigger `BEFORE UPDATE OR DELETE ON motor_calculo.snapshots` de
    `001_inicial.sql` — não é uma mutação, é a própria defesa contra
    mutação, e não casa com os padrões de comando usados aqui (ver docstring
    do módulo)."""
    violacoes: list[ViolacaoEscritaSnapshot] = []
    for caminho_relativo in ARQUIVOS_SQL_AUDITADOS:
        caminho_absoluto = RAIZ_PROJETO / caminho_relativo
        assert caminho_absoluto.exists(), f"migração esperada ausente: {caminho_relativo}"
        texto_sql = caminho_absoluto.read_text(encoding="utf-8")
        violacoes.extend(_detectar_mutacao_sql(texto_sql, caminho_relativo))

    mensagem = "escrita de snapshot em migração SQL da feature (AC-43):\n" + "\n".join(
        f"  {v.arquivo}:{v.linha} — {v.descricao}" for v in violacoes
    )
    assert not violacoes, mensagem


def test_detector_pega_insert_proposital_em_sql(tmp_path: Path) -> None:
    """Prova sintética: um `INSERT INTO motor_calculo.snapshots` fabricado é
    detectado pelo removedor de comentários + regex, sem depender de um
    arquivo real violador (as migrações reais não têm essa violação)."""
    sql_com_violacao = (
        "-- comentário legítimo sobre snapshots, não é mutação\n"
        "INSERT INTO motor_calculo.snapshots (\"SNAPSHOT_ID\") VALUES ('X');\n"
    )
    caminho = tmp_path / "caso_proposital.sql"
    caminho.write_text(sql_com_violacao, encoding="utf-8")

    violacoes = _detectar_mutacao_sql(sql_com_violacao, str(caminho))

    assert violacoes, "esperava que o detector pegasse o INSERT proposital"
    assert violacoes[0].linha == 2


def test_detector_pega_update_proposital_em_sql(tmp_path: Path) -> None:
    """Prova sintética: `UPDATE motor_calculo.snapshots SET ...` é
    detectado."""
    sql_com_violacao = 'UPDATE motor_calculo.snapshots SET "MOTIVO_RECALCULO" = \'x\';\n'
    caminho = tmp_path / "caso_proposital.sql"
    caminho.write_text(sql_com_violacao, encoding="utf-8")

    violacoes = _detectar_mutacao_sql(sql_com_violacao, str(caminho))

    assert violacoes, "esperava que o detector pegasse o UPDATE proposital"


def test_detector_pega_delete_proposital_em_sql(tmp_path: Path) -> None:
    """Prova sintética: `DELETE FROM motor_calculo.snapshots` é detectado."""
    sql_com_violacao = "DELETE FROM motor_calculo.snapshots WHERE \"SNAPSHOT_ID\" = 'X';\n"
    caminho = tmp_path / "caso_proposital.sql"
    caminho.write_text(sql_com_violacao, encoding="utf-8")

    violacoes = _detectar_mutacao_sql(sql_com_violacao, str(caminho))

    assert violacoes, "esperava que o detector pegasse o DELETE proposital"


def test_detector_pega_insert_proposital_em_string_python(tmp_path: Path) -> None:
    """Prova sintética: um literal de string em `.py` contendo
    `INSERT INTO motor_calculo.snapshots` é detectado — cobre o caso de um
    agente futuro montar SQL de mutação diretamente em código de
    `app/`/`collection/`/`report/`/`persistencia/app_aluno/`."""
    codigo_com_violacao = '''
def gravar_snapshot_por_engano() -> str:
    return "INSERT INTO motor_calculo.snapshots (\\"SNAPSHOT_ID\\") VALUES ('X')"
'''
    caminho = tmp_path / "caso_proposital.py"
    caminho.write_text(codigo_com_violacao, encoding="utf-8")

    violacoes = _detectar_mutacao_python(codigo_com_violacao, str(caminho))

    assert violacoes, "esperava que o detector pegasse o INSERT proposital em string Python"


def test_detector_nao_acusa_comentario_narrativo_sobre_snapshot(tmp_path: Path) -> None:
    """Prova de ausência de falso positivo: um comentário que MENCIONA
    "UPDATE" e "motor_calculo.snapshots" lado a lado, em prosa narrativa
    (exatamente o estilo das docstrings de 001_inicial.sql/002_app_aluno.sql),
    não é reportado — porque comentários são removidos antes da busca."""
    sql_valido = (
        "-- Esta migração nunca faz UPDATE ou DELETE em motor_calculo.snapshots:\n"
        "-- a única porta de escrita é RepositorioSnapshots.anexar.\n"
        "CREATE SCHEMA IF NOT EXISTS app_aluno;\n"
    )
    caminho = tmp_path / "caso_comentario_narrativo.sql"
    caminho.write_text(sql_valido, encoding="utf-8")

    violacoes = _detectar_mutacao_sql(sql_valido, str(caminho))

    assert not violacoes, f"comentário narrativo não deveria ser reportado: {violacoes}"


def test_detector_nao_acusa_revoke_nem_trigger_sobre_snapshot(tmp_path: Path) -> None:
    """Prova de ausência de falso positivo: `REVOKE UPDATE, DELETE ON
    motor_calculo.snapshots FROM PUBLIC` e `BEFORE UPDATE OR DELETE ON
    motor_calculo.snapshots` (a defesa de V-01, não uma mutação) não são
    reportados — o verbo aparece em posição de cláusula de permissão/gatilho,
    nunca em posição de comando (`INSERT INTO`/`UPDATE ... SET`/
    `DELETE FROM`)."""
    sql_valido = (
        "REVOKE UPDATE, DELETE ON motor_calculo.snapshots FROM PUBLIC;\n"
        "CREATE TRIGGER impedir_sobrescrita_v01\n"
        "    BEFORE UPDATE OR DELETE ON motor_calculo.snapshots\n"
        "    FOR EACH ROW\n"
        "    EXECUTE FUNCTION motor_calculo.impedir_sobrescrita_v01();\n"
    )
    caminho = tmp_path / "caso_revoke_trigger.sql"
    caminho.write_text(sql_valido, encoding="utf-8")

    violacoes = _detectar_mutacao_sql(sql_valido, str(caminho))

    assert not violacoes, f"REVOKE/trigger não deveriam ser reportados: {violacoes}"


def test_ac43_pastas_ainda_ausentes_ou_vazias_nao_produzem_violacao() -> None:
    """AC-43: o teste não quebra se `persistencia/app_aluno/` (ou outra
    pasta auditada) estiver ausente ou vazia — mesma tolerância de
    `test_sem_conteudo_de_questionario_no_codigo.py`."""
    violacoes: list[ViolacaoEscritaSnapshot] = []
    for arquivo in _arquivos_py_das_pastas_auditadas():
        codigo_fonte = arquivo.read_text(encoding="utf-8")
        violacoes.extend(_detectar_mutacao_python(codigo_fonte, str(arquivo)))

    assert not violacoes, f"não deveria haver violação real hoje, obteve: {violacoes}"
