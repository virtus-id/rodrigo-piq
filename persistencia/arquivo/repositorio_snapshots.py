"""Adaptador de arquivo de `RepositorioSnapshots` — RF-10, RF-12, `V-01..V-03`.

Grava uma linha JSON por `SnapshotOrdem` em um arquivo `.jsonl` (JSON Lines),
sempre em modo *append* (`open(..., "a")`) — nunca reescreve nem trunca o
arquivo, condição estrutural de `V-01` (histórico nunca sobrescrito) no lado
do adaptador, somada à ausência de `atualizar`/`remover` na porta (`engine/
portas.py::RepositorioSnapshots`). Padrão em testes e dev
(`plans/motor-calculo.plan.md` §6, linha 759: "Adaptador de arquivo —
`snapshots.jsonl` | append-only; uma linha por snapshot; `Decimal`
serializado como string").

Direção de dependência: este módulo importa de `engine/` — nunca o
contrário (mesma lei nº 1 de `persistencia/arquivo/fonte_parametros.py`).

**Serialização — `Decimal` sempre vira string (§6 do plano, "Regra de
serialização").** `SnapshotOrdem` é uma árvore de `dataclass` frozen,
`Enum`, `Mapping`, `tuple`/`frozenset` e `Decimal`. Em vez de reinventar essa
travessia, este módulo reusa `engine.snapshot._serializar_canonico` — a
MESMA função que `_calcular_hash_inputs` já usa para produzir uma
representação determinística e completa de qualquer valor do motor
(`Decimal -> str`, `Enum -> .value`, `date -> isoformat`, `dataclass -> dict`
por nome de campo, `tuple/list` preservando ordem, `frozenset/set -> lista
ordenada`, `Mapping -> dict` com chaves stringificadas). Não duplica essa
lógica aqui: um segundo serializador divergente seria uma segunda fonte de
verdade sobre "como serializar o motor" — exatamente o tipo de duplicação
que a spec pede para evitar. A DESSERIALIZAÇÃO (linha JSON -> `SnapshotOrdem`
de volta), por outro lado, é escopo NOVO desta tarefa: `_serializar_canonico`
não tem um inverso (não precisa — só alimenta um hash unidirecional), então
`_desserializar_snapshot` (abaixo) é escrito aqui, campo a campo, conhecendo
o schema de `SnapshotOrdem` e de cada dataclass que ele compõe.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from engine.ciclo_mensal import (
    AplicacaoResiduo,
    Cenario,
    EstadoSimulacao,
    Reranqueamento,
    ResultadoMes,
)
from engine.comparacao import ComparacaoCenarios
from engine.diagnostico import Diagnostico
from engine.estado import (
    CERTEZA_RECURSO_EXTRAORDINARIO,
    COBERTURA_MEIOS_PAGAMENTO,
    COBERTURA_PEQUENOS_GASTOS,
    CONHECIMENTO_GASTO,
    DEFASAGEM_REGISTRO,
    DISPOSICAO_USO_INVESTIMENTO,
    DISPOSICAO_USO_RESERVA,
    ESSENCIALIDADE,
    FREQUENCIA_REGISTRO,
    GASTOS_NAO_IDENTIFICADOS,
    JANELA_NOVA_DIVIDA,
    JANELA_RECURSO_EXTRAORDINARIO,
    LIQUIDEZ_INVESTIMENTOS,
    POSSIBILIDADE_VENDA,
    REGISTRO_GASTOS,
    RESERVA_EXISTE,
    REVISAO_SEMANAL,
    TIPO_ATIVO_FISICO,
    TIPO_DIVIDA,
    TIPO_RENDA,
    Divida,
    EstadoFinanceiro,
    ItemAtivo,
    ItemInvestimento,
    Oportunidade,
    PerfilComportamental,
    RecursoExtraordinario,
    SinaisComportamentais,
)
from engine.gates import AcaoRequerida
from engine.ordem import PosicaoOrdem
from engine.portas import RepositorioSnapshots
from engine.risco import ClassificacaoRisco, SinalD4
from engine.snapshot import SnapshotOrdem, _serializar_canonico
from engine.tipos import (
    CLASSIFICACAO_CENARIO,
    CONFIABILIDADE_DADOS,
    DESCONHECIDO,
    EVENTO_RECALCULO,
    METODO,
    NIVEL_CONTROLE,
    NIVEL_RISCO,
    ORDEM_STATUS,
    STATUS_DIVIDA,
    STATUS_FINANCEIRO,
    STATUS_METODO,
    STATUS_VALIDADE_PROPOSTA,
    Desconhecido,
    SimNaoTalvez,
)

REGRAS: Final[tuple[str, ...]] = ("RF-10", "RF-12", "V-01", "V-02", "V-03")

_NOME_ARQUIVO_PADRAO: Final[str] = "snapshots.jsonl"


class ErroSnapshotNaoEncontrado(Exception):
    """Levantado por `obter()` quando nenhum snapshot do arquivo tem o
    `SNAPSHOT_ID` pedido — mesmo espírito de `engine.parametros.
    ErroParametros`: falha ruidosa, nunca um `None`/objeto fabricado."""


class RepositorioSnapshotsArquivo(RepositorioSnapshots):
    """Implementa `RepositorioSnapshots` (`engine/portas.py`) gravando
    `snapshots.jsonl` — uma linha JSON por `SnapshotOrdem`, sempre anexada
    ao final do arquivo (`V-01`).

    `caminho_arquivo` é injetável para teste (arquivo temporário, simulação
    de erro de I/O) — mesmo padrão de `diretorio_parametros`/`caminho_esquema`
    em `FonteParametrosArquivo`.
    """

    def __init__(self, caminho_arquivo: Path | None = None) -> None:
        self._caminho_arquivo = caminho_arquivo or Path(_NOME_ARQUIVO_PADRAO)

    def anexar(self, s: SnapshotOrdem) -> None:
        """`V-01`: serializa `s` para uma linha JSON e ANEXA ao arquivo —
        nunca lê, reescreve nem trunca as linhas já existentes.

        `s` não é mutado em nenhum passo: a serialização (`_serializar_
        canonico`) só LÊ os campos de `s` e constrói uma estrutura NOVA
        (dict/list/str), nunca escreve de volta em `s` (que é `frozen`,
        T-08/T-46, e recusaria a escrita mesmo que este código tentasse).
        Se `open`/`write` falhar (disco cheio, permissão, caminho
        inexistente), a exceção do sistema de arquivos é PROPAGADA tal como
        veio — nenhum `try/except` aqui a absorve — e `s`, em memória no
        chamador, permanece exatamente o objeto que já era antes da
        chamada: o chamador pode reter a referência e tentar `anexar`
        de novo, ou tratar o erro, sem qualquer perda ou corrupção
        (critério de aceite 5 de `T-69`).
        """
        linha = json.dumps(_serializar_canonico(s), ensure_ascii=True, sort_keys=True)
        self._caminho_arquivo.parent.mkdir(parents=True, exist_ok=True)
        with self._caminho_arquivo.open("a", encoding="utf-8") as arquivo:
            arquivo.write(linha)
            arquivo.write("\n")

    def obter(self, snapshot_id: str) -> SnapshotOrdem:
        """Percorre o arquivo linha a linha e devolve o `SnapshotOrdem` cujo
        `SNAPSHOT_ID` combina com `snapshot_id`. `ErroSnapshotNaoEncontrado`
        se nenhuma linha combinar (ou se o arquivo não existir ainda)."""
        for bruto in self._ler_linhas():
            if bruto["SNAPSHOT_ID"] == snapshot_id:
                return _desserializar_snapshot(bruto)
        raise ErroSnapshotNaoEncontrado(
            f"nenhum snapshot com SNAPSHOT_ID={snapshot_id!r} em {self._caminho_arquivo}"
        )

    def historico(self, caso_id: str) -> Sequence[SnapshotOrdem]:
        """Devolve a cadeia completa de snapshots de `caso_id`, em ordem
        determinística.

        **Identificador de caso adotado — decisão documentada desta tarefa.**
        `SnapshotOrdem` (`engine/snapshot.py`, T-67) não modela um campo
        `caso_id`/`CASO_ID` próprio: o conceito de "caso" (um usuário/carteira
        cuja cadeia de snapshots se acumula ao longo do tempo) pertence a um
        slug de coleta/cadastro que ainda não existe neste projeto (ver
        `sdd.config.md` §3: `collection/` está listado como pasta de destino,
        vazia). Diante da ambiguidade, o identificador adotado é o
        `SNAPSHOT_ID` da RAIZ da cadeia — o primeiro snapshot
        (`snapshot_anterior_id is None`) do qual `caso_id` desce por
        `snapshot_anterior_id` sucessivos: é o único identificador ESTÁVEL já
        disponível hoje que naturalmente agrupa "todas as versões do mesmo
        caso" (`V-01`, cadeia tipo blockchain simples), sem inventar um
        campo novo em `SnapshotOrdem` fora do escopo desta tarefa (T-69 só
        estende `engine/portas.py` e `persistencia/arquivo/`, não
        `engine/snapshot.py`). Se uma tarefa futura de `collection/` adotar
        um `CASO_ID` explícito, este método deve ser revisitado (§6 do
        sdd.config.md).

        **Ordem determinística adotada.** A cadeia é devolvida ordenada por
        `versao` crescente (`1, 2, 3, ...`) — a MESMA ordem em que os
        snapshots foram necessariamente escritos, porque `versao =
        anterior.versao + 1` (`engine/snapshot.py::montar_SnapshotOrdem`,
        `V-01`) torna `versao` uma sequência estritamente crescente dentro
        de uma cadeia. Ordenar explicitamente por `versao` (em vez de
        confiar na ordem de escrita do arquivo) é mais robusto: continua
        determinístico mesmo se `anexar` for chamado fora de ordem por um
        cliente concorrente ou se o arquivo for reconstruído a partir de um
        backup com ordem de linha diferente.
        """
        raiz_por_snapshot_id: dict[str, str] = {}
        brutos_por_snapshot_id: dict[str, dict[str, Any]] = {}

        for bruto in self._ler_linhas():
            snapshot_id = bruto["SNAPSHOT_ID"]
            brutos_por_snapshot_id[snapshot_id] = bruto

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
        return tuple(_desserializar_snapshot(bruto) for bruto in pertencentes)

    def _ler_linhas(self) -> list[dict[str, Any]]:
        if not self._caminho_arquivo.is_file():
            return []
        linhas: list[dict[str, Any]] = []
        with self._caminho_arquivo.open(encoding="utf-8") as arquivo:
            for linha_bruta in arquivo:
                linha_bruta = linha_bruta.strip()
                if not linha_bruta:
                    continue
                linhas.append(json.loads(linha_bruta))
        return linhas


# ---------------------------------------------------------------------------
# Desserialização — linha JSON (dict Python puro, strings/listas/dicts) de
# volta para `SnapshotOrdem` real, com todo `Decimal` reconstruído EXATO
# (nunca via `float`, RF-12) e todo `Enum`/`dataclass` do motor recriado.
# Espelha, campo a campo, a árvore de tipos que `SnapshotOrdem` compõe (ver
# `engine/snapshot.py`, `engine/diagnostico.py`, `engine/ciclo_mensal.py`,
# `engine/comparacao.py`, `engine/status_metodo.py`, `engine/ordem.py`,
# `engine/gates.py`, `engine/estado.py`).
# ---------------------------------------------------------------------------


def _decimal(bruto: object) -> Decimal:
    """`str` -> `Decimal` exato, NUNCA passando por `float` (RF-12) — mesma
    garantia de round-trip bit a bit que `_serializar_canonico` promete na
    ida (`Decimal -> str`)."""
    assert isinstance(bruto, str), f"esperava string serializada de Decimal, recebeu {bruto!r}"
    return Decimal(bruto)


def _dinheiro_talvez(bruto: object) -> Any:
    if bruto == "DESCONHECIDO":
        return DESCONHECIDO
    return _decimal(bruto)


def _taxa_talvez(bruto: object) -> Any:
    return _dinheiro_talvez(bruto)


def _int_ou_desconhecido(bruto: object) -> int | Desconhecido:
    if bruto == "DESCONHECIDO":
        return DESCONHECIDO
    assert isinstance(bruto, int)
    return bruto


def _mecanismo_deficit(bruto: object) -> frozenset[str] | Desconhecido:
    if bruto == "DESCONHECIDO":
        return DESCONHECIDO
    assert isinstance(bruto, list)
    return frozenset(bruto)


def _janela_nova_divida(bruto: object) -> JANELA_NOVA_DIVIDA | None:
    if bruto is None:
        return None
    assert isinstance(bruto, str)
    return JANELA_NOVA_DIVIDA(bruto)


def _dinheiro_talvez_ou_none(bruto: object) -> Any:
    """RF-56, R4.6.1 — `RENDA_RECORRENTE_ATIVO: DinheiroTalvez | None` tem um
    TERCEIRO estado além de `Dinheiro`/`DESCONHECIDO`: `None` é o sentinela
    ESTRUTURAL de ausência (veículo, `OQ-38`), nunca confundido com
    `DESCONHECIDO`. `_dinheiro_talvez` sozinho não distingue os dois — este
    wrapper checa `None` primeiro, antes de delegar."""
    if bruto is None:
        return None
    return _dinheiro_talvez(bruto)


def _oportunidade(bruto: object) -> Oportunidade | None:
    if bruto is None:
        return None
    assert isinstance(bruto, dict)
    prazo = bruto["prazo"]
    return Oportunidade(
        beneficio=_dinheiro_talvez(bruto["beneficio"]),
        recurso_disponivel=bruto["recurso_disponivel"],
        prazo=date.fromisoformat(prazo) if prazo is not None else None,
        sustentavel=bruto["sustentavel"],
    )


def _divida(bruto: dict[str, Any]) -> Divida:
    return Divida(
        DIVIDA_ID=bruto["DIVIDA_ID"],
        TIPO_DIVIDA=TIPO_DIVIDA(bruto["TIPO_DIVIDA"]),
        STATUS_DIVIDA=STATUS_DIVIDA(bruto["STATUS_DIVIDA"]),
        SALDO_DEVEDOR_ATUAL=_dinheiro_talvez(bruto["SALDO_DEVEDOR_ATUAL"]),
        VALOR_QUITACAO_HOJE=_dinheiro_talvez(bruto["VALOR_QUITACAO_HOJE"]),
        QUITACAO_CONSULTADA=SimNaoTalvez(bruto["QUITACAO_CONSULTADA"]),
        STATUS_VALIDADE_PROPOSTA=STATUS_VALIDADE_PROPOSTA(bruto["STATUS_VALIDADE_PROPOSTA"]),
        TAXA_EFETIVA_MENSAL_NORMALIZADA=_taxa_talvez(bruto["TAXA_EFETIVA_MENSAL_NORMALIZADA"]),
        CET=_taxa_talvez(bruto["CET"]),
        PARCELA_CONTRATUAL=_dinheiro_talvez(bruto["PARCELA_CONTRATUAL"]),
        PAGAMENTO_MENSAL_EFETIVO=_dinheiro_talvez(bruto["PAGAMENTO_MENSAL_EFETIVO"]),
        SEGURO_INCLUIDO_PARCELA=bruto["SEGURO_INCLUIDO_PARCELA"],
        CUSTO_SEGURO=_dinheiro_talvez(bruto["CUSTO_SEGURO"]),
        PESO_EMOCIONAL=_int_ou_desconhecido(bruto["PESO_EMOCIONAL"]),
        RENEGOCIACAO_PENDENTE=bruto["RENEGOCIACAO_PENDENTE"],
        TROCA_PENDENTE=bruto["TROCA_PENDENTE"],
        RISCO_MATERIAL_IMINENTE=bruto["RISCO_MATERIAL_IMINENTE"],
        OPORTUNIDADE_VIGENTE=_oportunidade(bruto["OPORTUNIDADE_VIGENTE"]),
    )


def _item_investimento(bruto: dict[str, Any]) -> ItemInvestimento:
    """`ItemInvestimento` (`engine/estado.py`, RF-53, RF-59, T-125) — mesmo
    padrão simétrico de `_divida` acima: campo a campo, `Decimal`
    reconstruído por `_decimal` (nunca via `float`, RF-12) e `Enum` recriado
    pelo `.value` que `_serializar_canonico` gravou.

    `CLASSIFICACAO_MOBILIZACAO` NÃO é mais lido do dicionário serializado
    (`RF-59`): os campos BRUTOS abaixo (§14.3.1) é que chegam do disco;
    `classificar_investimento(item)` deriva a classificação sob demanda, sem
    round-trip de um campo armazenado."""
    return ItemInvestimento(
        ITEM_ID=bruto["ITEM_ID"],
        VALOR_LIQUIDO_REALIZAVEL=_decimal(bruto["VALOR_LIQUIDO_REALIZAVEL"]),
        POSSUI_LIQUIDEZ=bruto["POSSUI_LIQUIDEZ"],
        LIQUIDEZ_INVESTIMENTOS=LIQUIDEZ_INVESTIMENTOS(bruto["LIQUIDEZ_INVESTIMENTOS"]),
        DISPOSICAO_USO_INVESTIMENTO=DISPOSICAO_USO_INVESTIMENTO(
            bruto["DISPOSICAO_USO_INVESTIMENTO"]
        ),
        VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL=_decimal(
            bruto["VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL"]
        ),
        TEM_CUSTO_CONHECIDO=bruto["TEM_CUSTO_CONHECIDO"],
        SEM_CUSTO_PERDA_RELEVANTE=bruto["SEM_CUSTO_PERDA_RELEVANTE"],
    )


def _item_ativo(bruto: dict[str, Any]) -> ItemAtivo:
    """`ItemAtivo` (`engine/estado.py`, RF-54, RF-56, RF-57, RF-59, T-125) —
    sem `POSSUI_LIQUIDEZ`: "com liquidez" é condição que a §13.3 impõe
    apenas a `INVESTIMENTOS_RECOMENDADOS`.

    `CLASSIFICACAO_MOBILIZACAO` e `VALOR_LIQUIDO_REALIZAVEL_ATIVO_DISPONIVEL`
    NÃO são mais lidos do dicionário serializado (`RF-59`): os campos BRUTOS
    abaixo (§14.4-§14.9, §14.12) chegam do disco; `classificar_ativo_fisico`/
    `derivar_VALOR_LIQUIDO_REALIZAVEL_ATIVO*` derivam sob demanda.
    `RENDA_RECORRENTE_ATIVO` usa `_dinheiro_talvez_ou_none` (não
    `_dinheiro_talvez`): o campo é `DinheiroTalvez | None`, e `None` é o
    sentinela ESTRUTURAL de veículo (`RF-56`, `OQ-38`), distinto de
    `DESCONHECIDO`."""
    return ItemAtivo(
        ITEM_ID=bruto["ITEM_ID"],
        TIPO_ATIVO_FISICO=TIPO_ATIVO_FISICO(bruto["TIPO_ATIVO_FISICO"]),
        POSSIBILIDADE_VENDA=POSSIBILIDADE_VENDA(bruto["POSSIBILIDADE_VENDA"]),
        ESSENCIALIDADE=ESSENCIALIDADE(bruto["ESSENCIALIDADE"]),
        VALOR_ESTIMADO_ATIVO=_dinheiro_talvez(bruto["VALOR_ESTIMADO_ATIVO"]),
        POSSUI_PASSIVO_VINCULADO=bruto["POSSUI_PASSIVO_VINCULADO"],
        SALDO_PASSIVO_VINCULADO=_dinheiro_talvez(bruto["SALDO_PASSIVO_VINCULADO"]),
        POSSUI_CUSTO_DESMOBILIZACAO=bruto["POSSUI_CUSTO_DESMOBILIZACAO"],
        CUSTOS_ESTIMADOS_DESMOBILIZACAO=_dinheiro_talvez(
            bruto["CUSTOS_ESTIMADOS_DESMOBILIZACAO"]
        ),
        RENDA_RECORRENTE_ATIVO=_dinheiro_talvez_ou_none(bruto["RENDA_RECORRENTE_ATIVO"]),
        CUSTO_RECORRENTE_ATIVO=_dinheiro_talvez(bruto["CUSTO_RECORRENTE_ATIVO"]),
    )


def _recurso_extraordinario(bruto: dict[str, Any]) -> RecursoExtraordinario:
    """`RecursoExtraordinario` (`engine/estado.py`, T-95) — janela e certeza
    são os dois `Enum` que qualificam o recurso na §13.3, e não
    `CLASSIFICACAO_MOBILIZACAO` (que a §13 não aplica a este tipo de item)."""
    return RecursoExtraordinario(
        ITEM_ID=bruto["ITEM_ID"],
        VALOR_RECURSO_EXTRAORDINARIO=_decimal(bruto["VALOR_RECURSO_EXTRAORDINARIO"]),
        JANELA_RECURSO_EXTRAORDINARIO=JANELA_RECURSO_EXTRAORDINARIO(
            bruto["JANELA_RECURSO_EXTRAORDINARIO"]
        ),
        CERTEZA_RECURSO_EXTRAORDINARIO=CERTEZA_RECURSO_EXTRAORDINARIO(
            bruto["CERTEZA_RECURSO_EXTRAORDINARIO"]
        ),
    )


def _perfil_comportamental(bruto: dict[str, Any]) -> PerfilComportamental:
    return PerfilComportamental(
        REGISTRO_GASTOS=REGISTRO_GASTOS(bruto["REGISTRO_GASTOS"]),
        FREQUENCIA_REGISTRO=FREQUENCIA_REGISTRO(bruto["FREQUENCIA_REGISTRO"]),
        DEFASAGEM_REGISTRO=DEFASAGEM_REGISTRO(bruto["DEFASAGEM_REGISTRO"]),
        COBERTURA_PEQUENOS_GASTOS=COBERTURA_PEQUENOS_GASTOS(bruto["COBERTURA_PEQUENOS_GASTOS"]),
        COBERTURA_MEIOS_PAGAMENTO=COBERTURA_MEIOS_PAGAMENTO(bruto["COBERTURA_MEIOS_PAGAMENTO"]),
        CONHECIMENTO_GASTO=CONHECIMENTO_GASTO(bruto["CONHECIMENTO_GASTO"]),
        GASTOS_NAO_IDENTIFICADOS=GASTOS_NAO_IDENTIFICADOS(bruto["GASTOS_NAO_IDENTIFICADOS"]),
        REVISAO_SEMANAL=REVISAO_SEMANAL(bruto["REVISAO_SEMANAL"]),
    )


def _sinais_comportamentais(bruto: dict[str, Any]) -> SinaisComportamentais:
    return SinaisComportamentais(
        NOVA_DIVIDA_PREVISTA=SimNaoTalvez(bruto["NOVA_DIVIDA_PREVISTA"]),
        MECANISMO_DEFICIT=_mecanismo_deficit(bruto["MECANISMO_DEFICIT"]),
        HISTORICO_RECAIDA=SimNaoTalvez(bruto["HISTORICO_RECAIDA"]),
        NOVO_PARCELAMENTO_PREVISTO=SimNaoTalvez(bruto["NOVO_PARCELAMENTO_PREVISTO"]),
        PACTO=bruto["PACTO"],
        RISCO_IMPULSO=bruto["RISCO_IMPULSO"],
        LINHA_CONTINUA_SENDO_UTILIZADA=bruto["LINHA_CONTINUA_SENDO_UTILIZADA"],
        NECESSIDADE_VITORIA=_int_ou_desconhecido(bruto["NECESSIDADE_VITORIA"]),
        HISTORICO_ABANDONO=SimNaoTalvez(bruto["HISTORICO_ABANDONO"]),
        JANELA_NOVA_DIVIDA=_janela_nova_divida(bruto["JANELA_NOVA_DIVIDA"]),
    )


def _estado_financeiro(bruto: dict[str, Any]) -> EstadoFinanceiro:
    return EstadoFinanceiro(
        DATA_REFERENCIA=date.fromisoformat(bruto["DATA_REFERENCIA"]),
        RENDA_TOTAL_RECORRENTE=_decimal(bruto["RENDA_TOTAL_RECORRENTE"]),
        TIPO_RENDA=TIPO_RENDA(bruto["TIPO_RENDA"]),
        DESPESAS_OPERACIONAIS_ATUAIS=_decimal(bruto["DESPESAS_OPERACIONAIS_ATUAIS"]),
        DESPESAS_NAO_MENSAIS_NORMALIZADAS=_decimal(bruto["DESPESAS_NAO_MENSAIS_NORMALIZADAS"]),
        CAPACIDADE_ATAQUE_DECLARADA=_dinheiro_talvez(bruto["CAPACIDADE_ATAQUE_DECLARADA"]),
        ECONOMIA_POTENCIAL_IMEDIATA=_decimal(bruto["ECONOMIA_POTENCIAL_IMEDIATA"]),
        INVENTARIO_COMPLETO=bruto["INVENTARIO_COMPLETO"],
        dividas=tuple(_divida(d) for d in bruto["dividas"]),
        perfil_comportamental=_perfil_comportamental(bruto["perfil_comportamental"]),
        sinais_comportamentais=_sinais_comportamentais(bruto["sinais_comportamentais"]),
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS(bruto["CONFIABILIDADE_DADOS"]),
        AUTOPERCEPCAO_CONTROLE=_int_ou_desconhecido(bruto["AUTOPERCEPCAO_CONTROLE"]),
        # --- Rodada 3 (T-96/T-97) · reserva, caixa e patrimônio por item ---
        # `RESERVA_TOTAL`/`VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO` são
        # `DinheiroTalvez` (§13.1 Regra 3) e por isso passam por
        # `_dinheiro_talvez`; `DINHEIRO_DISPONIVEL` é `Dinheiro` SEMPRE
        # presente (`AC-63`) e por isso passa por `_decimal`.
        RESERVA_EXISTE=RESERVA_EXISTE(bruto["RESERVA_EXISTE"]),
        RESERVA_TOTAL=_dinheiro_talvez(bruto["RESERVA_TOTAL"]),
        DISPOSICAO_USO_RESERVA=DISPOSICAO_USO_RESERVA(bruto["DISPOSICAO_USO_RESERVA"]),
        VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO=_dinheiro_talvez(
            bruto["VALOR_MAXIMO_RESERVA_INFORMADO_USUARIO"]
        ),
        DINHEIRO_DISPONIVEL=_decimal(bruto["DINHEIRO_DISPONIVEL"]),
        investimentos=tuple(_item_investimento(i) for i in bruto["investimentos"]),
        ativos=tuple(_item_ativo(a) for a in bruto["ativos"]),
        recursos_extraordinarios=tuple(
            _recurso_extraordinario(r) for r in bruto["recursos_extraordinarios"]
        ),
    )


def _sinal_d4(bruto: dict[str, Any]) -> SinalD4:
    return SinalD4(
        nome=bruto["nome"],
        ativo=bruto["ativo"],
        desconhecido=bruto["desconhecido"],
    )


def _classificacao_risco(bruto: dict[str, Any]) -> ClassificacaoRisco:
    return ClassificacaoRisco(
        sinais=tuple(_sinal_d4(item) for item in bruto["sinais"]),
        contagem=bruto["contagem"],
        nivel=NIVEL_RISCO(bruto["nivel"]),
    )


def _diagnostico(bruto: dict[str, Any]) -> Diagnostico:
    """`Diagnostico` (`engine/diagnostico.py`, T-24) — campos escalares
    (`Decimal`/`bool`/`Enum`) mais dois `ClassificacaoRisco` aninhados
    (`engine/risco.py`, regra D.4). Espelha, explicitamente campo a campo,
    o mesmo padrão de `_estado_financeiro`/`_divida` acima — sem reflexão
    sobre anotação de tipo em runtime, para permanecer verificável por
    `mypy --strict` e por leitura direta."""
    return Diagnostico(
        PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES=_decimal(bruto["PAGAMENTOS_MENSAIS_DEVIDOS_VIGENTES"]),
        PAGAMENTOS_EFETIVOS_DIVIDAS=_decimal(bruto["PAGAMENTOS_EFETIVOS_DIVIDAS"]),
        RESULTADO_CAIXA_OBSERVADO=_decimal(bruto["RESULTADO_CAIXA_OBSERVADO"]),
        RESULTADO_MENSAL_ATUAL=_decimal(bruto["RESULTADO_MENSAL_ATUAL"]),
        GAP_CAIXA_VS_ESTRUTURAL=_decimal(bruto["GAP_CAIXA_VS_ESTRUTURAL"]),
        DEFICIT_MENSAL=_decimal(bruto["DEFICIT_MENSAL"]),
        PISO_CAPACIDADE=_decimal(bruto["PISO_CAPACIDADE"]),
        STATUS_FINANCEIRO=STATUS_FINANCEIRO(bruto["STATUS_FINANCEIRO"]),
        MODO_ESTABILIZACAO=bruto["MODO_ESTABILIZACAO"],
        GAP_AUTOPERCEPCAO=bruto["GAP_AUTOPERCEPCAO"],
        BASE_CONSERVADORA=_decimal(bruto["BASE_CONSERVADORA"]),
        FATOR_SEGURANCA=_decimal(bruto["FATOR_SEGURANCA"]),
        CAPACIDADE_ATAQUE_ATUAL=_decimal(bruto["CAPACIDADE_ATAQUE_ATUAL"]),
        CAPACIDADE_ATAQUE_CONSERVADORA=_decimal(bruto["CAPACIDADE_ATAQUE_CONSERVADORA"]),
        CAPACIDADE_ATAQUE_POTENCIAL=_decimal(bruto["CAPACIDADE_ATAQUE_POTENCIAL"]),
        NIVEL_CONTROLE=NIVEL_CONTROLE(bruto["NIVEL_CONTROLE"]),
        CONFIABILIDADE_DADOS=CONFIABILIDADE_DADOS(bruto["CONFIABILIDADE_DADOS"]),
        RISCO_RECAIDA=NIVEL_RISCO(bruto["RISCO_RECAIDA"]),
        RISCO_COMPORTAMENTAL_GERAL=NIVEL_RISCO(bruto["RISCO_COMPORTAMENTAL_GERAL"]),
        INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE=bruto["INCOMPATIBILIDADE_COMPORTAMENTAL_GRAVE"],
        classificacao_risco_recaida=_classificacao_risco(bruto["classificacao_risco_recaida"]),
        classificacao_risco_comportamental_geral=_classificacao_risco(
            bruto["classificacao_risco_comportamental_geral"]
        ),
        # T-90/OQ-23: campos de contrato (RF-35) — sem cálculo real ainda,
        # ver `engine/diagnostico.py`. Lidos aqui como qualquer outro campo
        # monetário para não quebrar o round-trip de snapshots já gravados.
        #
        # T-98 (RF-41, AC-68): `RESERVA_MOBILIZAVEL` é `DinheiroTalvez` e
        # por isso passa por `_dinheiro_talvez`, que devolve o sentinela
        # `DESCONHECIDO` quando a linha gravada traz a string
        # `"DESCONHECIDO"` (§13.1 Regra 3). Ler com `_decimal` aqui
        # levantaria `AssertionError` na volta — e "consertar" convertendo
        # para `0` apagaria a pendência, que é justamente o que a §13.1
        # proíbe. `ATAQUE_IMEDIATO_RECOMENDADO` continua `Dinheiro`
        # (plano R3.4.6) e segue em `_decimal`.
        RESERVA_MOBILIZAVEL=_dinheiro_talvez(bruto["RESERVA_MOBILIZAVEL"]),
        ATAQUE_IMEDIATO_RECOMENDADO=_decimal(bruto["ATAQUE_IMEDIATO_RECOMENDADO"]),
    )


def _resultado_mes(bruto: dict[str, Any]) -> ResultadoMes:
    estado_final_bruto = bruto["estado_final"]
    estado_final = EstadoSimulacao(
        mes=estado_final_bruto["mes"],
        saldos={chave: _decimal(valor) for chave, valor in estado_final_bruto["saldos"].items()},
        quitadas=frozenset(estado_final_bruto["quitadas"]),
        DIVIDA_ALVO_ATUAL=estado_final_bruto["DIVIDA_ALVO_ATUAL"],
        CAPACIDADE_ATAQUE_M=_decimal(estado_final_bruto["CAPACIDADE_ATAQUE_M"]),
        ATAQUE_NAO_UTILIZADO_ACUMULADO=_decimal(
            estado_final_bruto["ATAQUE_NAO_UTILIZADO_ACUMULADO"]
        ),
        DESEMBOLSO_ACUMULADO=_decimal(estado_final_bruto["DESEMBOLSO_ACUMULADO"]),
    )
    return ResultadoMes(
        estado_final=estado_final,
        quitacoes=tuple(bruto["quitacoes"]),
        RESIDUO_ATAQUE_M=_decimal(bruto["RESIDUO_ATAQUE_M"]),
        aplicacoes_residuo=tuple(
            AplicacaoResiduo(
                DIVIDA_ID=item["DIVIDA_ID"],
                valor_aplicado=_decimal(item["valor_aplicado"]),
                ordem_aplicacao=item["ordem_aplicacao"],
            )
            for item in bruto["aplicacoes_residuo"]
        ),
        ATAQUE_NAO_UTILIZADO=_decimal(bruto["ATAQUE_NAO_UTILIZADO"]),
        VALOR_FLUXO_LIBERADO=_decimal(bruto["VALOR_FLUXO_LIBERADO"]),
        reranqueamentos=tuple(
            Reranqueamento(mes=item["mes"], motivo=item["motivo"], novo_alvo=item["novo_alvo"])
            for item in bruto["reranqueamentos"]
        ),
    )


def _cenario(bruto: dict[str, Any]) -> Cenario:
    return Cenario(
        metodo=METODO(bruto["metodo"]) if bruto["metodo"] is not None else None,
        classificacao=(
            CLASSIFICACAO_CENARIO(bruto["classificacao"])
            if bruto["classificacao"] is not None
            else None
        ),
        ORDEM_QUITACAO=tuple(bruto["ORDEM_QUITACAO"]),
        PRAZO_TOTAL=bruto["PRAZO_TOTAL"],
        CUSTO_FUTURO_TOTAL=_decimal(bruto["CUSTO_FUTURO_TOTAL"]),
        MESES_PRIMEIRA_VITORIA=bruto["MESES_PRIMEIRA_VITORIA"],
        meses=tuple(_resultado_mes(item) for item in bruto["meses"]),
        ESTOUROU_HORIZONTE=bruto["ESTOUROU_HORIZONTE"],
        MESES_ATE_ALERTA_HORIZONTE=bruto["MESES_ATE_ALERTA_HORIZONTE"],
    )


def _comparacao(bruto: dict[str, Any]) -> ComparacaoCenarios:
    return ComparacaoCenarios(
        CENARIO_ECONOMICAMENTE_SUPERIOR=METODO(bruto["CENARIO_ECONOMICAMENTE_SUPERIOR"]),
        empatados_materialmente=tuple(
            METODO(item) for item in bruto["empatados_materialmente"]
        ),
        DIFERENCA_PERCENTUAL={
            METODO(chave): _decimal(valor) for chave, valor in bruto["DIFERENCA_PERCENTUAL"].items()
        },
        PENALIDADE_CUSTO={
            METODO(chave): _decimal(valor) for chave, valor in bruto["PENALIDADE_CUSTO"].items()
        },
        ATRASO_PRAZO={METODO(chave): valor for chave, valor in bruto["ATRASO_PRAZO"].items()},
        ECONOMICAMENTE_PROXIMO={
            METODO(chave): valor for chave, valor in bruto["ECONOMICAMENTE_PROXIMO"].items()
        },
    )


def _posicao_ordem(bruto: dict[str, Any]) -> PosicaoOrdem:
    valores_de_apoio = {
        chave: _decimal(valor) for chave, valor in bruto["valores_de_apoio"].items()
    }
    return PosicaoOrdem(
        posicao=bruto["posicao"],
        DIVIDA_ID=bruto["DIVIDA_ID"],
        JUSTIFICATIVA_POSICAO=bruto["JUSTIFICATIVA_POSICAO"],
        valores_de_apoio=valores_de_apoio,
    )


def _acao_requerida(bruto: dict[str, Any]) -> AcaoRequerida:
    """`AcaoRequerida` (`engine/gates.py`, T-79/T-83/T-84/T-87) — T-92
    corrige esta desserialização para o contrato estendido da Rodada 2:
    `ACAO_ID`/`TIPO_ACAO` (obrigatórios, ausentes antes desta tarefa) e
    `CAMPO_PENDENTE` (opcional, só preenchido em `TIPO_ACAO="INFORMACAO"`).
    `_serializar_canonico` (`engine/snapshot.py`) já serializa TODOS os
    campos da dataclass genericamente por nome — nenhuma mudança necessária
    do lado da serialização; só a leitura de volta (`_acao_requerida`)
    ficou desatualizada em relação ao shape novo, e é corrigida aqui.
    `bruto["CAMPO_PENDENTE"]` é `None` quando o campo não se aplica (mesmo
    valor que `_serializar_canonico` produz para `None`, ver seu ramo
    `valor is None`).

    T-133 (RF-61 · §14.2.1/§14.2.2): `VALOR_ACAO_FINANCEIRA_IMEDIATA`
    (campo novo, sem default) é lido via `_dinheiro_talvez` — mesmo helper
    já usado para os demais campos `DinheiroTalvez` deste módulo, preserva
    `Decimal` exato e o sentinela `DESCONHECIDO` no round-trip.
    `_serializar_canonico` já grava o campo automaticamente por nome; só a
    leitura de volta precisava do campo novo."""
    return AcaoRequerida(
        ACAO_ID=bruto["ACAO_ID"],
        DIVIDA_ID=bruto["DIVIDA_ID"],
        TIPO_ACAO=bruto["TIPO_ACAO"],
        descricao=bruto["descricao"],
        gate_origem=bruto["gate_origem"],
        VALOR_ACAO_FINANCEIRA_IMEDIATA=_dinheiro_talvez(bruto["VALOR_ACAO_FINANCEIRA_IMEDIATA"]),
        prioridade_excepcional=bruto["prioridade_excepcional"],
        CAMPO_PENDENTE=bruto["CAMPO_PENDENTE"],
    )


def _desserializar_snapshot(bruto: dict[str, Any]) -> SnapshotOrdem:
    """Reconstrói um `SnapshotOrdem` completo a partir do dict já decodificado
    de uma linha `snapshots.jsonl` (`json.loads` já aplicado). Espelha campo
    a campo `SnapshotOrdem` (`engine/snapshot.py`), reconstruindo cada
    `Decimal` a partir de sua string (RF-12: round-trip exato, nunca via
    `float`) e cada `Enum`/`dataclass` aninhado a partir do seu `.value`/dict.
    """
    cenarios = {
        METODO(chave): _cenario(valor) for chave, valor in bruto["cenarios"].items()
    }
    return SnapshotOrdem(
        SNAPSHOT_ID=bruto["SNAPSHOT_ID"],
        versao=bruto["versao"],
        snapshot_anterior_id=bruto["snapshot_anterior_id"],
        DATA_REFERENCIA=date.fromisoformat(bruto["DATA_REFERENCIA"]),
        MOTIVO_RECALCULO=bruto["MOTIVO_RECALCULO"],
        EVENTO_RECALCULO=(
            EVENTO_RECALCULO(bruto["EVENTO_RECALCULO"])
            if bruto["EVENTO_RECALCULO"] is not None
            else None
        ),
        hash_inputs=bruto["hash_inputs"],
        estado_inputs=_estado_financeiro(bruto["estado_inputs"]),
        diagnostico=_diagnostico(bruto["diagnostico"]),
        cenarios=cenarios,
        comparacao=_comparacao(bruto["comparacao"]),
        METODO_RECOMENDADO_PIQ=METODO(bruto["METODO_RECOMENDADO_PIQ"]),
        STATUS_METODO=STATUS_METODO(bruto["STATUS_METODO"]),
        ORDEM_STATUS=ORDEM_STATUS(bruto["ORDEM_STATUS"]),
        REVISAO_HUMANA_OBRIGATORIA=bruto["REVISAO_HUMANA_OBRIGATORIA"],
        DIVIDA_ALVO_ATUAL=bruto["DIVIDA_ALVO_ATUAL"],
        PROXIMA_DIVIDA=bruto["PROXIMA_DIVIDA"],
        ORDEM_QUITACAO=tuple(_posicao_ordem(item) for item in bruto["ORDEM_QUITACAO"]),
        ORDEM_ACOES=tuple(_acao_requerida(item) for item in bruto["ORDEM_ACOES"]),
        ENGINE_VERSION=bruto["ENGINE_VERSION"],
        PARAMETROS_VERSION=bruto["PARAMETROS_VERSION"],
    )
