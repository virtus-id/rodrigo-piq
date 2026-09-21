"""Adaptador Supabase/Postgres de `RepositorioSnapshots` — RF-10, RF-12,
`V-01..V-03`.

Grava um `SnapshotOrdem` por linha em `motor_calculo.snapshots`: os valores
DECISIVOS do cenário recomendado (`CUSTO_FUTURO_TOTAL`, `PRAZO_TOTAL`,
capacidades) são colunas `numeric`/`integer` de primeira classe — não apenas
campos dentro de um blob `jsonb` (critério de aceite 1 de T-75). O restante
da árvore (`estado_inputs`, `diagnostico`, `cenarios`, `comparacao`,
`ORDEM_QUITACAO`, `ORDEM_ACOES`) vai em `dados_completos jsonb`, serializado
por `engine.snapshot._serializar_canonico` — a MESMA função canônica que
`persistencia/arquivo/repositorio_snapshots.py` já usa, sem uma segunda
fonte de verdade sobre "como serializar o motor".

**Imutabilidade — dupla garantia, não uma só.** No lado do Postgres,
`migracoes/001_inicial.sql` faz `REVOKE UPDATE, DELETE` mais a trigger
`impedir_sobrescrita_v01`. Neste módulo, `anexar` só executa `INSERT` — nunca
`UPDATE`/`DELETE` — e a porta (`engine/portas.py::RepositorioSnapshots`) nem
declara esses verbos (mesmo espírito estrutural de
`RepositorioSnapshotsArquivo`).

**Idempotência de `anexar` (critério de aceite 5).** `SNAPSHOT_ID` já é
derivado de `hash_inputs` + `versao` desde T-67/T-69: o MESMO
`SnapshotOrdem` (mesmo hash_inputs, mesma versao) produz sempre o MESMO
`SNAPSHOT_ID`. A semântica adotada aqui é `INSERT ... ON CONFLICT
("SNAPSHOT_ID") DO NOTHING`: chamar `anexar` duas vezes com o mesmo
`SnapshotOrdem` não duplica a linha nem levanta erro — a segunda chamada é
um no-op silencioso, consistente com "mesmo dado, mesmo ID, já gravado".
Não há verificação de divergência de conteúdo para o mesmo `SNAPSHOT_ID`
porque `SNAPSHOT_ID` é uma função pura de `(hash_inputs, versao)`
(`engine/snapshot.py::montar_SnapshotOrdem`): dois `SnapshotOrdem` com o
mesmo `SNAPSHOT_ID` só podem divergir se `hash_inputs` colidir (sha-256,
probabilidade desprezível) ou se o snapshot foi montado fora de
`montar_SnapshotOrdem` — nenhum dos dois casos é responsabilidade deste
adaptador de persistência resolver.

Direção de dependência: este módulo importa de `engine/` — nunca o
contrário (mesma lei nº 1 de `persistencia/arquivo/repositorio_snapshots.py`).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Final

from engine.portas import RepositorioSnapshots
from engine.snapshot import SnapshotOrdem, _serializar_canonico
from persistencia.arquivo.repositorio_snapshots import _desserializar_snapshot
from persistencia.supabase.conexao import conectar

REGRAS: Final[tuple[str, ...]] = ("RF-10", "RF-12", "V-01", "V-02", "V-03")


class ErroSnapshotNaoEncontrado(Exception):
    """Levantado por `obter()` quando nenhuma linha de `motor_calculo.
    snapshots` tem o `SNAPSHOT_ID` pedido — mesmo espírito de
    `persistencia.arquivo.repositorio_snapshots.ErroSnapshotNaoEncontrado`:
    falha ruidosa, nunca um `None`/objeto fabricado."""


class RepositorioSnapshotsSupabase(RepositorioSnapshots):
    """Implementa `RepositorioSnapshots` (`engine/portas.py`) gravando em
    `motor_calculo.snapshots` — uma linha por `SnapshotOrdem`, sempre via
    `INSERT` (nunca `UPDATE`/`DELETE`, `V-01`).

    Expõe exatamente os três métodos da porta: `anexar`, `obter`,
    `historico`. Não há `atualizar`/`remover` — a violação de `V-01` é
    estruturalmente inexpressável nesta classe, e o banco recusa a operação
    mesmo que um cliente futuro tentasse executar SQL cru (REVOKE + trigger).
    """

    def anexar(self, s: SnapshotOrdem) -> None:
        """`V-01`: grava `s` como uma nova linha em `motor_calculo.snapshots`.

        Idempotente por `SNAPSHOT_ID` (`ON CONFLICT DO NOTHING`, ver
        docstring do módulo). `s` não é mutado em nenhum passo — é `frozen`
        (T-08/T-46) e a serialização só LÊ seus campos.
        """
        cenario_recomendado = s.cenarios[s.METODO_RECOMENDADO_PIQ]
        diagnostico = s.diagnostico

        dados_completos = {
            "estado_inputs": _serializar_canonico(s.estado_inputs),
            "diagnostico": _serializar_canonico(s.diagnostico),
            "cenarios": {
                str(metodo.value): _serializar_canonico(cenario)
                for metodo, cenario in s.cenarios.items()
            },
            "comparacao": _serializar_canonico(s.comparacao),
            "ORDEM_QUITACAO": [_serializar_canonico(p) for p in s.ORDEM_QUITACAO],
            "ORDEM_ACOES": [_serializar_canonico(a) for a in s.ORDEM_ACOES],
        }

        with conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO motor_calculo.snapshots (
                    "SNAPSHOT_ID", versao, snapshot_anterior_id,
                    "DATA_REFERENCIA", "MOTIVO_RECALCULO", "EVENTO_RECALCULO",
                    hash_inputs,
                    "METODO_RECOMENDADO_PIQ", "STATUS_METODO", "ORDEM_STATUS",
                    "REVISAO_HUMANA_OBRIGATORIA", "DIVIDA_ALVO_ATUAL", "PROXIMA_DIVIDA",
                    "CUSTO_FUTURO_TOTAL", "PRAZO_TOTAL",
                    "CAPACIDADE_ATAQUE_ATUAL", "CAPACIDADE_ATAQUE_CONSERVADORA",
                    "CAPACIDADE_ATAQUE_POTENCIAL",
                    "ENGINE_VERSION", "PARAMETROS_VERSION",
                    dados_completos
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s,
                    %s, %s,
                    %s
                )
                ON CONFLICT ("SNAPSHOT_ID") DO NOTHING
                """,
                (
                    s.SNAPSHOT_ID,
                    s.versao,
                    s.snapshot_anterior_id,
                    s.DATA_REFERENCIA,
                    s.MOTIVO_RECALCULO,
                    s.EVENTO_RECALCULO.value if s.EVENTO_RECALCULO is not None else None,
                    s.hash_inputs,
                    s.METODO_RECOMENDADO_PIQ.value,
                    s.STATUS_METODO.value,
                    s.ORDEM_STATUS.value,
                    s.REVISAO_HUMANA_OBRIGATORIA,
                    s.DIVIDA_ALVO_ATUAL,
                    s.PROXIMA_DIVIDA,
                    cenario_recomendado.CUSTO_FUTURO_TOTAL,
                    cenario_recomendado.PRAZO_TOTAL,
                    diagnostico.CAPACIDADE_ATAQUE_ATUAL,
                    diagnostico.CAPACIDADE_ATAQUE_CONSERVADORA,
                    diagnostico.CAPACIDADE_ATAQUE_POTENCIAL,
                    s.ENGINE_VERSION,
                    s.PARAMETROS_VERSION,
                    json.dumps(dados_completos, ensure_ascii=True, sort_keys=True),
                ),
            )

    def obter(self, snapshot_id: str) -> SnapshotOrdem:
        """Busca a linha de `SNAPSHOT_ID = snapshot_id` em `motor_calculo.
        snapshots` e reconstrói o `SnapshotOrdem`. `ErroSnapshotNaoEncontrado`
        se nenhuma linha combinar."""
        with conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute(
                'SELECT * FROM motor_calculo.snapshots WHERE "SNAPSHOT_ID" = %s',
                (snapshot_id,),
            )
            linha = cursor.fetchone()
            if linha is None:
                raise ErroSnapshotNaoEncontrado(
                    f"nenhum snapshot com SNAPSHOT_ID={snapshot_id!r} em "
                    "motor_calculo.snapshots"
                )
            colunas = [descricao.name for descricao in cursor.description or ()]
            bruto = dict(zip(colunas, linha, strict=True))

        return _desserializar_snapshot(_bruto_para_formato_arquivo(bruto))

    def historico(self, caso_id: str) -> Sequence[SnapshotOrdem]:
        """Devolve a cadeia completa de snapshots de `caso_id`, em ordem
        determinística por `versao` crescente.

        Mesmo identificador de caso adotado por `RepositorioSnapshotsArquivo`
        (T-69, ver docstring lá): o `SNAPSHOT_ID` da RAIZ da cadeia — não há
        campo `caso_id` próprio em `SnapshotOrdem`/na tabela.
        """
        with conectar() as conexao, conexao.cursor() as cursor:
            cursor.execute('SELECT * FROM motor_calculo.snapshots')
            colunas = [descricao.name for descricao in cursor.description or ()]
            brutos_por_snapshot_id: dict[str, dict[str, Any]] = {}
            for linha in cursor.fetchall():
                bruto: dict[str, Any] = dict(zip(colunas, linha, strict=True))
                snapshot_id: str = bruto["SNAPSHOT_ID"]
                brutos_por_snapshot_id[snapshot_id] = bruto

        raiz_por_snapshot_id: dict[str, str] = {}

        def _raiz(snapshot_id: str) -> str:
            if snapshot_id in raiz_por_snapshot_id:
                return raiz_por_snapshot_id[snapshot_id]
            anterior_id = brutos_por_snapshot_id[snapshot_id]["snapshot_anterior_id"]
            raiz = snapshot_id if anterior_id is None else _raiz(anterior_id)
            raiz_por_snapshot_id[snapshot_id] = raiz
            return raiz

        pertencentes = [
            bruto
            for snapshot_id, bruto in brutos_por_snapshot_id.items()
            if _raiz(snapshot_id) == caso_id
        ]
        pertencentes.sort(key=lambda bruto: bruto["versao"])
        return tuple(
            _desserializar_snapshot(_bruto_para_formato_arquivo(bruto)) for bruto in pertencentes
        )


def _bruto_para_formato_arquivo(bruto: dict[str, Any]) -> dict[str, Any]:
    """Reconcilia a linha da tabela (colunas decisivas + `dados_completos`
    jsonb) com o formato que `persistencia.arquivo.repositorio_snapshots.
    _desserializar_snapshot` espera (o mesmo dict que uma linha de
    `snapshots.jsonl` produz) — reaproveita a desserialização já existente
    em vez de escrever uma segunda travessia divergente.

    `dados_completos` (jsonb) já chega desserializado como `dict`/`list`
    Python puro pelo `psycopg 3` (não é string JSON) — os `Decimal`
    aninhados foram serializados como `str` por `_serializar_canonico` na
    escrita, e `_desserializar_snapshot` já sabe reconstituí-los com
    `Decimal(str)`, nunca via `float` (RF-12).
    """
    dados_completos = bruto["dados_completos"]
    return {
        "SNAPSHOT_ID": bruto["SNAPSHOT_ID"],
        "versao": bruto["versao"],
        "snapshot_anterior_id": bruto["snapshot_anterior_id"],
        "DATA_REFERENCIA": bruto["DATA_REFERENCIA"].isoformat(),
        "MOTIVO_RECALCULO": bruto["MOTIVO_RECALCULO"],
        "EVENTO_RECALCULO": bruto["EVENTO_RECALCULO"],
        "hash_inputs": bruto["hash_inputs"],
        "estado_inputs": dados_completos["estado_inputs"],
        "diagnostico": dados_completos["diagnostico"],
        "cenarios": dados_completos["cenarios"],
        "comparacao": dados_completos["comparacao"],
        "METODO_RECOMENDADO_PIQ": bruto["METODO_RECOMENDADO_PIQ"],
        "STATUS_METODO": bruto["STATUS_METODO"],
        "ORDEM_STATUS": bruto["ORDEM_STATUS"],
        "REVISAO_HUMANA_OBRIGATORIA": bruto["REVISAO_HUMANA_OBRIGATORIA"],
        "DIVIDA_ALVO_ATUAL": bruto["DIVIDA_ALVO_ATUAL"],
        "PROXIMA_DIVIDA": bruto["PROXIMA_DIVIDA"],
        "ORDEM_QUITACAO": dados_completos["ORDEM_QUITACAO"],
        "ORDEM_ACOES": dados_completos["ORDEM_ACOES"],
        "ENGINE_VERSION": bruto["ENGINE_VERSION"],
        "PARAMETROS_VERSION": bruto["PARAMETROS_VERSION"],
    }
